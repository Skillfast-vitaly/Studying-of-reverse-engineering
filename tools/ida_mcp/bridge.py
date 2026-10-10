#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
«Наставник IDA» — MCP-сервер курса (мост между Claude Code и IDA Pro 9.2).

Claude Code запускает этот файл и говорит с ним по протоколу MCP через
stdin/stdout (JSON-RPC, по строке на сообщение). Мост передаёт вопросы
плагину nastavnik_ida.py внутри IDA по адресу 127.0.0.1:47920–47929.

Нужен только Python 3.8+ — сторонних библиотек нет.
Подключение к Claude Code — tools/ida_mcp/README.md.

Чем отличается от других MCP для IDA:
  * работает с IDA 9.2 (официальный сервер Hex-Rays требует 9.4+);
  * объясняет инструкции по-русски словами курса (база tools/hints);
  * учебный режим: по умолчанию только чтение; править базу можно, лишь
    когда ученик сам разрешит это в IDA;
  * выполнить произвольный код через сервер нельзя — такой команды нет.
"""
import importlib.util
import json
import os
import sys
import types
import urllib.error
import urllib.request

NAME, VERSION = "nastavnik-ida", "1.0"
PORTS = range(47920, 47930)
HERE = os.path.dirname(os.path.abspath(__file__))
# версии протокола с рукопожатием initialize, от старых к новым
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")

INSTRUCTIONS = """\
Это «Наставник IDA» из курса реверс-инжиниринга. Ученику 18 лет, он
учится с нуля, английский A2, отвечай по-русски. Работай в учебном
режиме (скилл ida-mcp в репозитории курса):
1. Сначала спроси, что думает он сам, и только потом смотри в базу.
2. Проверяй его догадки, переименования и комментарии (инструмент
   annotations), а не решай задачу за него. Подсказывай ступенями.
   Готовый ответ — только если он прямо попросит после своей попытки.
3. Базу не меняй без его просьбы (rename и comment по умолчанию
   выключены в самой IDA).
4. Объясняя строку, бери explain: там русская подсказка и номер
   раздела курса — отправляй его туда.
5. Числа между системами счисления не переводи в уме: проверь
   инструментом или кодом."""


# ---------------------------------------------------------------------
# Русские подсказки: берём из плагина подсказчика (tools/hints), подменив
# модули IDA пустышками — нужна только его чистая логика describe().
# ---------------------------------------------------------------------

_hints = None


def hints():
    global _hints
    if _hints is None:
        path = os.path.join(os.path.dirname(HERE), "hints", "ida", "ru_hints.py")
        saved = {}
        for mod in ("ida_idaapi", "ida_kernwin", "ida_bytes", "ida_funcs", "idc", "idautils"):
            saved[mod] = sys.modules.get(mod)
            sys.modules[mod] = types.ModuleType(mod)
        k = sys.modules["ida_kernwin"]
        k.action_handler_t = type("action_handler_t", (), {"__init__": lambda self: None})
        k.UI_Hooks = type("UI_Hooks", (), {"__init__": lambda self: None})
        i = sys.modules["ida_idaapi"]
        i.plugmod_t, i.plugin_t, i.PLUGIN_MULTI = type("p", (), {}), type("q", (), {}), 0x100
        try:
            spec = importlib.util.spec_from_file_location("ru_hints_for_bridge", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _hints = mod
        finally:
            for m, v in saved.items():
                if v is None:
                    sys.modules.pop(m, None)
                else:
                    sys.modules[m] = v
    return _hints


# ---------------------------------------------------------------------
# Связь с IDA
# ---------------------------------------------------------------------

class IdaError(Exception):
    pass


_port = None


def _post(port, tool, args, timeout):
    req = urllib.request.Request(
        "http://127.0.0.1:%d/call" % port,
        data=json.dumps({"tool": tool, "args": args}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Nastavnik": "1"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ida(tool, args=None):
    """Вызвать инструмент в IDA. Ищем порт, если ещё не нашли."""
    global _port
    ports = [_port] if _port else []
    ports += [p for p in PORTS if p != _port]
    env_port = os.environ.get("NASTAVNIK_PORT")
    if env_port:
        ports = [int(env_port)]
    last = None
    for p in ports:
        try:
            res = _post(p, tool, args or {}, timeout=60 if p == _port else 3)
        except urllib.error.HTTPError as e:
            last = "IDA ответила ошибкой %s" % e.code
            continue
        except (urllib.error.URLError, OSError) as e:
            last = str(e)
            if p == _port:
                _port = None
            continue
        _port = p
        if "error" in res:
            raise IdaError(res["error"])
        return res.get("ok")
    raise IdaError(
        "IDA не отвечает (%s). Нужно: открыть IDA Pro 9.2 с программой; плагин "
        "nastavnik_ida.py лежит в %%APPDATA%%\\Hex-Rays\\IDA Pro\\plugins; в окне "
        "Output есть строка «Наставник IDA … слушает 127.0.0.1:47920»." % last)


# ---------------------------------------------------------------------
# Инструменты MCP
# ---------------------------------------------------------------------

def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


TARGET = {"type": "string",
          "description": "Адрес (0x140001000 или 140001000h) или имя (main). "
                         "Пусто — там, где курсор ученика."}

TOOLS = [
    ("status", "Что открыто в IDA: версия IDA, файл, ImageBase, число функций, "
     "есть ли декомпилятор, разрешены ли правки.", _obj({})),
    ("current", "Где сейчас курсор ученика: адрес, строка, функция и смещение в ней. "
     "Начинай с этого, когда он спрашивает «что это тут?».", _obj({})),
    ("functions", "Список функций: имя, адрес, размер, переименовал ли её ученик.",
     _obj({"filter": {"type": "string", "description": "часть имени"},
           "limit": {"type": "integer"}, "offset": {"type": "integer"}})),
    ("disasm", "Дизассемблер: вся функция по адресу или count строк начиная с адреса. "
     "В строках видны и комментарии ученика.",
     _obj({"target": TARGET, "count": {"type": "integer",
                                       "description": "сколько строк; 0 — вся функция"}})),
    ("decompile", "Псевдокод Hex-Rays для функции (если декомпилятор есть в IDA).",
     _obj({"target": TARGET})),
    ("xrefs_to", "Кто ссылается на адрес или имя: откуда, тип ссылки, из какой функции.",
     _obj({"target": TARGET, "limit": {"type": "integer"}})),
    ("strings", "Строки в программе (как окно Strings), с фильтром.",
     _obj({"filter": {"type": "string"}, "limit": {"type": "integer"}})),
    ("imports", "Импорт: какие функции DLL зовёт программа (глава 8, 12).",
     _obj({"filter": {"type": "string"}})),
    ("annotations", "Что ученик уже сделал в функции: свои имена и комментарии. "
     "Главный инструмент проверки его работы.", _obj({"target": TARGET})),
    ("read_bytes", "Байты по адресу в шестнадцатеричном виде (до 256).",
     _obj({"target": TARGET, "size": {"type": "integer"}})),
    ("explain", "Русская подсказка к инструкции по адресу: что делает, флаги, "
     "раздел курса. Подсказка из базы курса tools/hints.", _obj({"target": TARGET})),
    ("rename", "Переименовать адрес. Работает, только если ученик разрешил правки "
     "в IDA. Без его просьбы не вызывать.",
     _obj({"target": TARGET, "new_name": {"type": "string"}}, ["new_name"])),
    ("comment", "Поставить комментарий к строке (пустой текст — убрать). Только "
     "с разрешения ученика в IDA и по его просьбе.",
     _obj({"target": TARGET, "text": {"type": "string"}}, ["text"])),
]


def tool_explain(args):
    target = args.get("target")
    line = ida("disasm", {"target": target, "count": 1})
    # строка вида "0x140001000  mov eax, 1  ; комментарий"
    text = line.split("\n")[-1].split("  ", 1)[-1].split("  ;")[0].strip()
    first = text.split()[0] if text.split() else ""
    lines = hints().describe(first, text)
    if not lines:
        return "По этому адресу нет инструкции: " + line
    return line + "\n\n" + "\n".join(lines)


def call_tool(name, args):
    if name not in {t[0] for t in TOOLS}:
        raise IdaError("Нет такого инструмента: %s" % name)
    if name == "explain":
        return tool_explain(args)
    return ida(name, args)


def as_text(res):
    if isinstance(res, str):
        return res
    return json.dumps(res, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------
# Протокол MCP поверх stdio: JSON-RPC 2.0, по одному сообщению в строке
# ---------------------------------------------------------------------

def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    params = msg.get("params") or {}
    if mid is None:                       # уведомление — ответ не нужен
        return None
    if method == "initialize":
        asked = params.get("protocolVersion")
        result = {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[-1],
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": NAME, "version": VERSION},
                  "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": s}
                            for n, d, s in TOOLS]}
    elif method == "tools/call":
        try:
            text, err = as_text(call_tool(params.get("name"), params.get("arguments") or {})), False
        except IdaError as e:
            text, err = str(e), True
        except Exception as e:            # мост не должен падать из-за одного вызова
            text, err = "%s: %s" % (type(e).__name__, e), True
        result = {"content": [{"type": "text", "text": text}], "isError": err}
    else:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": "Method not found: %s" % method}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    # MCP требует UTF-8, а Windows по умолчанию даёт cp1251
    for s in (sys.stdin, sys.stdout):
        s.reconfigure(encoding="utf-8", newline="\n")
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None,
                   "error": {"code": -32700, "message": "Parse error"}}
        else:
            batch = msg if isinstance(msg, list) else [msg]
            replies = [r for r in (handle(m) for m in batch if isinstance(m, dict)) if r]
            if not replies:
                continue
            out = replies if isinstance(msg, list) else replies[0]
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
