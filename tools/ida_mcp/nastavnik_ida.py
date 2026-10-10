# -*- coding: utf-8 -*-
"""
«Наставник IDA» — сторона IDA для MCP-сервера курса. IDA Pro 9.2.

Плагин поднимает маленький сервер на 127.0.0.1 (порт 47920, при занятом —
следующие до 47929). Его слушает только этот компьютер. Мост bridge.py,
который запускает Claude Code, спрашивает через него IDA: что открыто,
где курсор, дизассемблер, псевдокод, строки, импорт, ссылки, твои
переименования и комментарии.

Учебный режим по умолчанию: менять базу нельзя. Разрешить правки
(переименовать, поставить комментарий) можно только из самой IDA:
Edit → Plugins → «Наставник IDA: разрешить правки в базе».
Выполнить произвольный код через сервер нельзя вообще — такой команды нет.

Установка — tools/ida_mcp/README.md. Плагин кладут в
%APPDATA%\\Hex-Rays\\IDA Pro\\plugins рядом с русским подсказчиком.
"""

import http.server
import json
import threading

import ida_idaapi
import ida_kernwin
import ida_bytes
import ida_funcs
import ida_lines
import ida_nalt
import ida_name
import idautils
import idc

try:
    import ida_hexrays
except ImportError:          # декомпилятора может не быть
    ida_hexrays = None

VERSION = "1.0"
PORTS = range(47920, 47930)
MAX_LINES = 2000             # больше строк за раз Claude всё равно не прочтёт с пользой


class TutorError(Exception):
    """Ошибка, которую надо показать как есть, по-русски."""


class _state:
    write_allowed = False
    port = None


# ---------------------------------------------------------------------
# Вызовы IDA. Сервер работает в отдельном потоке, а API IDA можно звать
# только из главного — поэтому каждый запрос идёт через execute_sync.
# ---------------------------------------------------------------------

def on_main_thread(fn, write=False):
    box = {}

    def run():
        try:
            box["ok"] = fn()
        except TutorError as e:
            box["err"] = str(e)
        except Exception as e:     # не роняем IDA из-за одного запроса
            box["err"] = "%s: %s" % (type(e).__name__, e)
        return 1

    ida_kernwin.execute_sync(run, ida_kernwin.MFF_WRITE if write else ida_kernwin.MFF_READ)
    if "err" in box:
        raise TutorError(box["err"])
    return box.get("ok")


def hx(ea):
    return "0x%X" % ea


def parse_ea(target):
    """Адрес из числа, '0x140001000', '140001000h' или имени ('main')."""
    if target is None or target == "":
        return ida_kernwin.get_screen_ea()
    if isinstance(target, int):
        return target
    t = str(target).strip()
    low = t.lower()
    hexdigits = set("0123456789abcdef")
    if low.startswith("0x") and low[2:] and set(low[2:]) <= hexdigits:
        return int(low, 16)
    if low.endswith("h") and low[:-1] and set(low[:-1]) <= hexdigits:
        return int(low[:-1], 16)
    # Сначала имя: функция может называться, например, «fade» — это не число.
    ea = ida_name.get_name_ea(ida_idaapi.BADADDR, t)
    if ea != ida_idaapi.BADADDR:
        return ea
    if low and set(low) <= hexdigits:
        return int(low, 16)
    raise TutorError("Не нашёл адрес или имя %r." % t)


def line_at(ea):
    text = idc.GetDisasm(ea)
    cmt = ida_bytes.get_cmt(ea, False) or ida_bytes.get_cmt(ea, True)
    return "%s  %s%s" % (hx(ea), text, "  ; " + cmt if cmt and cmt not in text else "")


def func_or_error(ea):
    f = ida_funcs.get_func(ea)
    if f is None:
        raise TutorError("По адресу %s нет функции." % hx(ea))
    return f


# ---------------------------------------------------------------------
# Инструменты. Каждый получает словарь аргументов и возвращает то, что
# уйдёт в Claude (переводится в JSON).
# ---------------------------------------------------------------------

def t_status(a):
    decomp = bool(ida_hexrays and ida_hexrays.init_hexrays_plugin())
    return {
        "ida": ida_kernwin.get_kernel_version(),
        "file": ida_nalt.get_root_filename(),
        "path": ida_nalt.get_input_file_path(),
        "imagebase": hx(ida_nalt.get_imagebase()),
        "functions": ida_funcs.get_func_qty(),
        "decompiler": decomp,
        "write_allowed": _state.write_allowed,
        "plugin": VERSION,
    }


def t_current(a):
    ea = ida_kernwin.get_screen_ea()
    f = ida_funcs.get_func(ea)
    res = {"ea": hx(ea), "line": line_at(ea) if ida_bytes.is_code(ida_bytes.get_flags(ea)) else None,
           "function": None}
    if f:
        res["function"] = ida_funcs.get_func_name(f.start_ea)
        res["function_start"] = hx(f.start_ea)
        res["offset_in_function"] = hx(ea - f.start_ea)
    return res


def t_functions(a):
    flt = str(a.get("filter") or "").lower()
    limit = min(int(a.get("limit") or 200), 1000)
    offset = int(a.get("offset") or 0)
    out = []
    for ea in idautils.Functions():
        name = ida_funcs.get_func_name(ea)
        if flt and flt not in name.lower():
            continue
        f = ida_funcs.get_func(ea)
        out.append({"name": name, "start": hx(ea), "size": f.end_ea - f.start_ea if f else None,
                    "user_name": ida_bytes.has_user_name(ida_bytes.get_flags(ea))})
    return {"total": len(out), "items": out[offset:offset + limit]}


def t_disasm(a):
    ea = parse_ea(a.get("target"))
    count = min(int(a.get("count") or 0), MAX_LINES)
    f = ida_funcs.get_func(ea)
    lines = []
    if f is not None and not count:
        lines.append("; функция %s, %s–%s" % (ida_funcs.get_func_name(f.start_ea),
                                             hx(f.start_ea), hx(f.end_ea)))
        for item in idautils.FuncItems(f.start_ea):
            lines.append(line_at(item))
            if len(lines) > MAX_LINES:
                lines.append("; … обрезано: функция длиннее %d строк" % MAX_LINES)
                break
    else:
        count = count or 40
        cur = ea
        for _ in range(count):
            if cur == ida_idaapi.BADADDR:
                break
            lines.append(line_at(cur))
            cur = ida_bytes.next_head(cur, ida_idaapi.BADADDR)
    return "\n".join(lines)


def t_decompile(a):
    if not (ida_hexrays and ida_hexrays.init_hexrays_plugin()):
        raise TutorError("Декомпилятор Hex-Rays недоступен в этой IDA.")
    f = func_or_error(parse_ea(a.get("target")))
    cfunc = ida_hexrays.decompile(f)
    if cfunc is None:
        raise TutorError("Не удалось декомпилировать функцию.")
    return "\n".join(ida_lines.tag_remove(sl.line) for sl in cfunc.get_pseudocode())


def t_xrefs_to(a):
    ea = parse_ea(a.get("target"))
    limit = min(int(a.get("limit") or 100), 1000)
    out = []
    for x in idautils.XrefsTo(ea, 0):
        f = ida_funcs.get_func(x.frm)
        out.append({"from": hx(x.frm), "type": idautils.XrefTypeName(x.type),
                    "function": ida_funcs.get_func_name(f.start_ea) if f else None})
        if len(out) >= limit:
            break
    return {"to": hx(ea), "name": ida_name.get_name(ea), "items": out}


def t_strings(a):
    flt = str(a.get("filter") or "").lower()
    limit = min(int(a.get("limit") or 200), 2000)
    s = idautils.Strings(False)
    s.setup(strtypes=[ida_nalt.STRTYPE_C, ida_nalt.STRTYPE_C_16])
    out = []
    for v in s:
        if v is None:
            continue
        text = str(v)
        if flt and flt not in text.lower():
            continue
        out.append({"ea": hx(v.ea), "text": text[:300]})
        if len(out) >= limit:
            break
    return out


def t_imports(a):
    flt = str(a.get("filter") or "").lower()
    out = {}
    for i in range(ida_nalt.get_import_module_qty()):
        mod = ida_nalt.get_import_module_name(i) or "?"
        names = []

        def cb(ea, name, ordinal):
            n = name or "#%d" % ordinal
            if not flt or flt in n.lower():
                names.append({"name": n, "ea": hx(ea)})
            return True

        ida_nalt.enum_import_names(i, cb)
        if names:
            out[mod] = names
    return out


def t_annotations(a):
    """Что ученик уже сделал в функции: свои имена и комментарии."""
    f = func_or_error(parse_ea(a.get("target")))
    res = {"function": ida_funcs.get_func_name(f.start_ea), "start": hx(f.start_ea),
           "function_renamed": ida_bytes.has_user_name(ida_bytes.get_flags(f.start_ea)),
           "names": [], "comments": []}
    for ea in idautils.FuncItems(f.start_ea):
        fl = ida_bytes.get_flags(ea)
        if ea != f.start_ea and ida_bytes.has_user_name(fl):
            res["names"].append({"ea": hx(ea), "name": ida_name.get_name(ea)})
        for rpt in (False, True):
            c = ida_bytes.get_cmt(ea, rpt)
            if c:
                res["comments"].append({"ea": hx(ea), "repeatable": rpt, "text": c,
                                        "line": idc.GetDisasm(ea)})
    return res


def t_read_bytes(a):
    ea = parse_ea(a.get("target"))
    size = max(1, min(int(a.get("size") or 16), 256))
    data = ida_bytes.get_bytes(ea, size) or b""
    return {"ea": hx(ea), "hex": " ".join("%02X" % b for b in data)}


def _need_write():
    if not _state.write_allowed:
        raise TutorError("Учебный режим: правки в базе выключены. Ученик может "
                         "разрешить их в IDA: Edit → Plugins → «Наставник IDA: "
                         "разрешить правки в базе».")


def t_rename(a):
    _need_write()
    ea = parse_ea(a.get("target"))
    name = str(a.get("new_name") or "").strip()
    if not name:
        raise TutorError("Пустое имя.")
    if not ida_name.set_name(ea, name, ida_name.SN_CHECK | ida_name.SN_NOWARN):
        raise TutorError("IDA не приняла имя %r (недопустимые символы или уже занято)." % name)
    return "Переименовано: %s → %s" % (hx(ea), name)


def t_comment(a):
    _need_write()
    ea = parse_ea(a.get("target"))
    text = str(a.get("text") or "")
    ida_bytes.set_cmt(ea, text, False)
    return "Комментарий у %s: %s" % (hx(ea), text or "(удалён)")


TOOLS = {
    "status": (t_status, False), "current": (t_current, False),
    "functions": (t_functions, False), "disasm": (t_disasm, False),
    "decompile": (t_decompile, False), "xrefs_to": (t_xrefs_to, False),
    "strings": (t_strings, False), "imports": (t_imports, False),
    "annotations": (t_annotations, False), "read_bytes": (t_read_bytes, False),
    "rename": (t_rename, True), "comment": (t_comment, True),
}


def dispatch(tool, args):
    if tool not in TOOLS:
        raise TutorError("Нет такого инструмента: %s" % tool)
    fn, write = TOOLS[tool]
    return on_main_thread(lambda: fn(args or {}), write)


# ---------------------------------------------------------------------
# Сервер. Слушает только 127.0.0.1. Браузер к нему не достучится: нужен
# заголовок X-Nastavnik и Content-Type application/json, а такие запросы
# браузер с чужой страницы без разрешения CORS не отправит.
# ---------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "nastavnik-ida/" + VERSION

    def _reply(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if (self.path != "/call" or self.headers.get("X-Nastavnik") != "1"
                or not (self.headers.get("Content-Type") or "").startswith("application/json")):
            return self._reply(403, {"error": "запрос не от моста Наставника"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            res = dispatch(req.get("tool"), req.get("args"))
            self._reply(200, {"ok": res})
        except TutorError as e:
            self._reply(200, {"error": str(e)})
        except Exception as e:
            self._reply(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def do_GET(self):
        self._reply(405, {"error": "только POST /call"})

    do_OPTIONS = do_PUT = do_DELETE = do_GET

    def log_message(self, fmt, *args):     # не засорять окно Output
        pass


def start_server():
    for port in PORTS:
        try:
            srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        _state.port = port
        return srv
    return None


# ---------------------------------------------------------------------
# Плагин
# ---------------------------------------------------------------------

class _toggle_ah(ida_kernwin.action_handler_t):
    def __init__(self):
        ida_kernwin.action_handler_t.__init__(self)

    def activate(self, ctx):
        _state.write_allowed = not _state.write_allowed
        print("Наставник IDA: правки в базе %s" %
              ("РАЗРЕШЕНЫ" if _state.write_allowed else "запрещены (учебный режим)"))
        return 1

    def update(self, ctx):
        return ida_kernwin.AST_ENABLE_ALWAYS


TOGGLE = "nastavnik:toggle_write"


class nastavnik_ctx_t(ida_idaapi.plugmod_t):
    def __init__(self):
        # Базовый __init__ не вызываем — так в примерах Hex-Rays для 9.2.
        self.srv = start_server()
        ida_kernwin.unregister_action(TOGGLE)
        ida_kernwin.register_action(ida_kernwin.action_desc_t(
            TOGGLE, "Наставник IDA: разрешить или запретить правки в базе", _toggle_ah()))
        ida_kernwin.attach_action_to_menu("Edit/Plugins/", TOGGLE, ida_kernwin.SETMENU_APP)
        if self.srv is None:
            print("Наставник IDA: все порты 47920–47929 заняты, сервер не запущен.")
        else:
            print("Наставник IDA %s слушает 127.0.0.1:%d (только этот компьютер). "
                  "Учебный режим: правки в базе выключены." % (VERSION, _state.port))

    def run(self, arg):
        print("Наставник IDA: порт %s, правки %s" % (
            _state.port, "разрешены" if _state.write_allowed else "запрещены"))
        return True

    def __del__(self):
        try:
            if self.srv is not None:
                self.srv.shutdown()
                self.srv.server_close()
            ida_kernwin.unregister_action(TOGGLE)
        except Exception:
            pass


class nastavnik_plugin_t(ida_idaapi.plugin_t):
    flags = ida_idaapi.PLUGIN_MULTI
    comment = "MCP-сервер курса: Claude смотрит в IDA в учебном режиме"
    help = "Порт 47920; правки в базе — только с разрешения"
    wanted_name = "Наставник IDA: состояние"
    wanted_hotkey = ""

    def init(self):
        return nastavnik_ctx_t()


def PLUGIN_ENTRY():
    return nastavnik_plugin_t()
