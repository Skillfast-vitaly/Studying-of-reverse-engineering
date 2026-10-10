#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка «Наставника IDA» без IDA.

    python3 tools/ida_mcp/test_nastavnik.py

1. Плагин nastavnik_ida.py загружается с пустышками вместо модулей IDA.
   Поднимается его настоящий HTTP-сервер, а вызовы IDA подменяются
   подставными ответами.
2. Мост bridge.py запускается так, как его запустит Claude Code, и с ним
   идёт разговор по протоколу MCP (JSON-RPC по stdin/stdout).
3. Проверяется: рукопожатие, список инструментов, вызовы, учебный режим
   (правки запрещены), ответ при выключенной IDA, защита сервера от
   запросов не от моста.
4. Если установлен официальный MCP SDK (pip install mcp), тот же сервер
   проверяется ещё и его клиентом.
"""
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import types
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, "bridge.py")
FAILS = []


def check(cond, what):
    print(("   ok   " if cond else "   ОШИБКА ") + what)
    if not cond:
        FAILS.append(what)


# ---------------------------------------------------------------------
# 1. Плагин IDA с пустышками и подставными ответами
# ---------------------------------------------------------------------

def load_plugin():
    for m in ("ida_idaapi", "ida_kernwin", "ida_bytes", "ida_funcs", "ida_lines",
              "ida_nalt", "ida_name", "idautils", "idc"):
        sys.modules[m] = types.ModuleType(m)
    k = sys.modules["ida_kernwin"]
    k.action_handler_t = type("action_handler_t", (), {"__init__": lambda self: None})
    i = sys.modules["ida_idaapi"]
    i.plugmod_t, i.plugin_t, i.PLUGIN_MULTI = type("p", (), {}), type("q", (), {}), 0x100
    spec = importlib.util.spec_from_file_location("nastavnik_test",
                                                  os.path.join(HERE, "nastavnik_ida.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FAKE = {
    "status": {"ida": "9.2", "file": "01_strings.exe", "imagebase": "0x140000000",
               "functions": 120, "decompiler": True, "write_allowed": False, "plugin": "1.0"},
    "current": {"ea": "0x140001460", "line": "0x140001460  test    eax, eax",
                "function": "main", "function_start": "0x140001450",
                "offset_in_function": "0x10"},
}


def make_dispatch(mod):
    def dispatch(tool, args):
        if tool in ("rename", "comment"):
            mod._need_write()            # настоящая проверка учебного режима
            return "правка сделана"
        if tool == "disasm":
            if args.get("target") == "0x140001500":
                return "0x140001500  rep movsb"
            return "0x140001460  jnz     short loc_140001490  ; рус: свой комментарий"
        if tool in FAKE:
            return FAKE[tool]
        raise mod.TutorError("подставной ответ не задан для %s" % tool)
    return dispatch


# ---------------------------------------------------------------------
# 2–3. Разговор с мостом «как Claude Code»: JSON-RPC по строкам
# ---------------------------------------------------------------------

class Bridge:
    def __init__(self, port):
        env = dict(os.environ, NASTAVNIK_PORT=str(port), PYTHONIOENCODING="utf-8")
        self.p = subprocess.Popen([sys.executable, BRIDGE], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.n = 0

    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self.n += 1
            msg["id"] = self.n
        self.p.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        self.p.stdin.flush()
        if notify:
            return None
        return json.loads(self.p.stdout.readline().decode("utf-8"))

    def call(self, name, args=None):
        r = self.send("tools/call", {"name": name, "arguments": args or {}})
        res = r["result"]
        return res["content"][0]["text"], res["isError"]

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


def test_raw(port):
    print("== Мост по протоколу MCP (как его зовёт Claude Code)")
    b = Bridge(port)
    r = b.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "0"}})
    res = r.get("result", {})
    check(res.get("protocolVersion") == "2025-06-18", "initialize: версия протокола клиента принята")
    check(res.get("serverInfo", {}).get("name") == "nastavnik-ida", "initialize: имя сервера")
    check("учебном" in res.get("instructions", ""), "initialize: инструкции про учебный режим")
    r = b.send("initialize", {"protocolVersion": "1999-01-01"})
    check(r["result"]["protocolVersion"] == "2025-11-25", "незнакомая версия → последняя своя")
    check(b.send("notifications/initialized", notify=True) is None, "уведомление без ответа")
    check(b.send("ping")["result"] == {}, "ping")
    tools = {t["name"]: t for t in b.send("tools/list")["result"]["tools"]}
    check({"status", "current", "disasm", "decompile", "annotations", "explain",
           "rename", "comment"} <= set(tools), "tools/list: все инструменты на месте")
    check(all(t["inputSchema"]["type"] == "object" for t in tools.values()),
          "у каждого инструмента схема аргументов")
    check(not any("eval" in n or "exec" in n or "python" in n for n in tools),
          "нет инструмента «выполнить код»")
    text, err = b.call("status")
    check(not err and '"01_strings.exe"' in text, "status доходит до IDA и обратно")
    text, err = b.call("current")
    check(not err and "main" in text, "current")
    text, err = b.call("explain", {"target": "0x140001460"})
    check(not err and "jnz — jump if not zero" in text and "9.8" in text,
          "explain: русская подсказка и раздел курса")
    text, err = b.call("explain", {"target": "0x140001500"})
    check(not err and "movsb — move string" in text and "Префикс rep" in text,
          "explain: префикс rep разобран")
    text, err = b.call("rename", {"target": "main", "new_name": "check"})
    check(err and "Учебный режим" in text, "учебный режим: rename запрещён")
    text, err = b.call("no_such_tool")
    check(err and "Нет такого инструмента" in text, "неизвестный инструмент — ошибка, мост жив")
    r = b.send("resources/list")
    check(r.get("error", {}).get("code") == -32601, "неизвестный метод — ошибка -32601")
    b.close()
    check(b.p.returncode == 0, "мост закрылся сам, когда закрыли stdin")


def test_no_ida():
    print("== IDA не запущена")
    b = Bridge(1)                        # порт, где никто не слушает
    b.send("initialize", {"protocolVersion": "2025-11-25"})
    text, err = b.call("status")
    check(err and "IDA не отвечает" in text and "nastavnik_ida.py" in text,
          "понятная русская ошибка с подсказкой, что сделать")
    b.close()


def test_security(port):
    print("== Защита сервера в IDA")
    url = "http://127.0.0.1:%d/call" % port
    body = json.dumps({"tool": "status", "args": {}}).encode()

    def code(req):
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    check(code(urllib.request.Request(url, data=body, headers={
        "Content-Type": "text/plain"}, method="POST")) == 403,
        "запрос без заголовка моста (как из браузера) — 403")
    check(code(urllib.request.Request(url, data=body, headers={
        "Content-Type": "text/plain", "X-Nastavnik": "1"}, method="POST")) == 403,
        "Content-Type не JSON — 403")
    check(code(urllib.request.Request(url, method="GET")) == 405, "GET — 405")
    check(code(urllib.request.Request(url, method="OPTIONS")) == 405,
          "OPTIONS (предзапрос браузера) — 405, без разрешений CORS")


# ---------------------------------------------------------------------
# 4. Официальный клиент MCP SDK, если он есть
# ---------------------------------------------------------------------

async def sdk_session(port):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[BRIDGE],
                                   env=dict(os.environ, NASTAVNIK_PORT=str(port)))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            tools = await s.list_tools()
            res = await s.call_tool("explain", {"target": "0x140001460"})
            return init, tools, res


def test_sdk(port):
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("== Официальный MCP SDK не установлен — эту часть пропускаю")
        return
    import importlib.metadata as md
    print("== Официальный клиент MCP SDK %s" % md.version("mcp"))
    init, tools, res = asyncio.run(sdk_session(port))
    check(init.server_info.name == "nastavnik-ida", "SDK: рукопожатие прошло, версия %s"
          % init.protocol_version)
    check(len(tools.tools) >= 13, "SDK: список инструментов (%d)" % len(tools.tools))
    text = res.content[0].text
    check(not res.is_error and "jnz — jump if not zero" in text, "SDK: вызов explain")


def main():
    mod = load_plugin()
    mod.dispatch = make_dispatch(mod)
    srv = mod.start_server()
    check(srv is not None, "сервер плагина поднялся на 127.0.0.1:%s" % mod._state.port)
    try:
        test_raw(mod._state.port)
        test_no_ida()
        test_security(mod._state.port)
        test_sdk(mod._state.port)
    finally:
        srv.shutdown()
        srv.server_close()
    print("== Итог: %s" % ("всё прошло" if not FAILS else "ошибок: %d" % len(FAILS)))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
