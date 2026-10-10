#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка и проверка русского подсказчика.

    python3 tools/hints/build_hints.py          собрать и проверить
    python3 tools/hints/build_hints.py --check  только проверить, ничего не писать

Что делает:
  1. читает базу hints_data.py и разворачивает семейства (jcc, setcc,
     cmovcc, строковые, дробные);
  2. проверяет базу: имена не повторяются, нет пустых полей, нет знака
     процента, разделы курса из поля ch существуют на самом деле;
  3. собирает ida/ru_hints.py и ghidra/RuHint*.java из templates/;
  4. проверяет логику плагина IDA на примерах (с заглушками модулей IDA);
  5. если есть javac — компилирует скрипты Ghidra с заглушками API из
     test/ghidra_stubs и сверяет, что Java отвечает слово в слово как Python;
  6. если есть кросс-компилятор — собирает учебные задачи crackmes и
     считает, какие инструкции из них база не знает.

На Windows запускай через python (или py -3), а не python3.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CHECK_ONLY = "--check" in sys.argv


def load_data():
    spec = importlib.util.spec_from_file_location("hints_data",
                                                  os.path.join(HERE, "hints_data.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------
# 1. Развернуть базу
# ---------------------------------------------------------------------

# Строковые инструкции по размерам: n — сколько байт, r — какой регистр.
STRING_SIZES = [("b", "1 байт", "AL"), ("w", "2 байта", "AX"),
                ("d", "4 байта", "EAX"), ("q", "8 байт", "RAX")]
STRING_OPS = {
    "movs": ("Копирует {n} из [RSI] в [RDI] и сдвигает оба указателя. С префиксом "
             "rep повторяет RCX раз — это memcpy, встроенный прямо в код.",
             "копирует {n}: [RSI] → [RDI]"),
    "stos": ("Записывает {r} в [RDI] и сдвигает RDI на {n}. С префиксом rep "
             "заполняет RCX элементов — это memset, например обнуление массива.",
             "пишет {r} в [RDI]"),
    "lods": ("Читает {n} из [RSI] в {r} и сдвигает RSI.",
             "читает [RSI] в {r}"),
    "scas": ("Сравнивает {r} с [RDI] и сдвигает RDI. repne scasb — старый "
             "способ найти конец строки (strlen).",
             "сравнивает {r} с [RDI]"),
    "cmps": ("Сравнивает {n} в [RSI] и [RDI] и сдвигает оба указателя. "
             "repe cmpsb — сравнение двух кусков памяти (memcmp).",
             "сравнивает {n} в [RSI] и [RDI]"),
}


def expand(d):
    records, names, errors = {}, {}, []

    def add(rid, rec, all_names):
        if rid in records:
            errors.append("запись %s повторяется" % rid)
        records[rid] = rec
        for n in all_names:
            if n in names:
                errors.append("имя %s уже занято записью %s" % (n, names[n]))
            names[n] = rid

    def rec_of(e, **over):
        r = dict(en=e["en"], say=e.get("say", ""), ru=e["ru"], what=e["what"],
                 flags=e["flags"], short=e["short"], ch=list(e.get("ch", [])))
        r.update(over)
        return r

    for e in d.ENTRIES:
        own = e.get("en_for", {})
        for n in own:
            if n not in e.get("aka", []):
                errors.append("%s: en_for для %s, которого нет в aka" % (e["m"], n))
        add(e["m"], rec_of(e), [e["m"]] + [n for n in e.get("aka", []) if n not in own])
        for n, o in own.items():
            add(n, rec_of(e, **o), [n])
        if e["m"] in STRING_OPS:
            what, short = STRING_OPS[e["m"]]
            for suf, n_bytes, reg in STRING_SIZES:
                n = e["m"] + suf
                if n in ("movsd", "cmpsd"):
                    continue      # у них отдельные записи .sse и .str
                add(n, rec_of(e, what=what.format(n=n_bytes, r=reg),
                              short=short.format(n=n_bytes, r=reg)), [n])

    for op, en, say, ru in d.SSE_OPS:
        for suf, sen, ssay, sru in d.SSE_SUFFIX:
            n = op + suf
            add(n, dict(en=en + " " + sen, say=say + " " + ssay,
                        ru=ru + ": " + sru.split(" (")[0],
                        what=ru.capitalize() + " дробных чисел: " + sru + ". "
                             "Дробные вычисления в курсе пока не разбирали; "
                             "регистры xmm — 12.2.",
                        flags="не меняет", short=ru + ", " + sru.split(" (")[0],
                        ch=["12.2"]), [n])

    for c in d.CONDITIONS:
        if not (len(c["names"]) == len(c["words"]) == len(c["shorts"])):
            errors.append("условие %s: names, words и shorts разной длины" % c["names"])
        for n, word, short in zip(c["names"], c["words"], c["shorts"]):
            fl = "не меняет; смотрит на " + c["uses"]
            for kind, en, ru, what, sh, ch in (
                ("j", "jump if ", "прыгнуть, если ",
                 "Условный переход: прыгает, если {ru} ({test}); иначе "
                 "выполнение идёт дальше. Обычно стоит сразу за cmp или test (9.7).",
                 "прыжок, если {s}",
                 [c["ch"]] if c["ch"] == "9.8" else [c["ch"], "9.8"]),
                ("set", "set byte if ", "поставить 1, если ",
                 "Пишет в байт 1, если {ru} ({test}), иначе 0. Так сравнение "
                 "превращается в значение «истина/ложь» (5.11).",
                 "1, если {s}, иначе 0", ["5.11", c["ch"]]),
                ("cmov", "conditional move if ", "скопировать, если ",
                 "Копирует значение, только если {ru} ({test}); иначе ничего "
                 "не делает. Так компилятор пишет простое if без перехода (20.10).",
                 "копировать, если {s}", ["20.10", c["ch"]]),
            ):
                others = [kind + o for o in c["names"] if o != n]
                text = what.format(ru=c["ru"], test=c["test"])
                if others:
                    text += " Другие имена той же инструкции: " + ", ".join(others) + "."
                add(kind + n, dict(en=en + word, say="", ru=ru + short,
                                   what=text, flags=fl, short=sh.format(s=short),
                                   ch=ch), [kind + n])
    return records, names, errors


# ---------------------------------------------------------------------
# 2. Проверить
# ---------------------------------------------------------------------

def course_sections():
    """Номера разделов, которые есть в курсе: «10.2», «П3.4»."""
    secs = set()
    cdir = os.path.join(ROOT, "course")
    for f in os.listdir(cdir):
        if not f.endswith(".md"):
            continue
        with open(os.path.join(cdir, f), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^##+ +((?:\d+|П\d+)\.\d+)\.? ", line)
                if m:
                    secs.add(m.group(1))
    return secs


def validate(records, names, prefixes):
    errors = []
    secs = course_sections()
    for rid, r in records.items():
        for k in ("en", "ru", "what", "flags", "short"):
            if not r.get(k):
                errors.append("%s: пустое поле %s" % (rid, k))
        for k, v in r.items():
            texts = v if isinstance(v, list) else [v]
            for s in texts:
                if "%" in s:
                    errors.append("%s.%s: знак процента — окно IDA его съест" % (rid, k))
                if "\n" in s or "\t" in s:
                    errors.append("%s.%s: перевод строки или табуляция" % (rid, k))
        if len(r["short"]) > 46:
            errors.append("%s: short длиннее 46 знаков (%d)" % (rid, len(r["short"])))
        for s in r["ch"]:
            if s not in secs:
                errors.append("%s: раздела %s нет в курсе" % (rid, s))
    for n in names:
        if not re.fullmatch(r"[a-z0-9]+(\.(sse|str))?", n):
            errors.append("имя %r: только маленькие латинские буквы и цифры" % n)
    for bad in ("movsd", "cmpsd"):
        if bad in names:
            errors.append("%s без .sse/.str: у этого имени два смысла" % bad)
    for p, s in prefixes.items():
        if "%" in s:
            errors.append("префикс %s: знак процента" % p)
    return errors


# ---------------------------------------------------------------------
# 3. Собрать
# ---------------------------------------------------------------------

def py_data(records, names, prefixes):
    out = ["# --- данные: собраны из hints_data.py ---",
           "RECORDS = {"]
    for rid in sorted(records):
        out.append("    %r: %r," % (rid, records[rid]))
    out.append("}")
    out.append("NAMES = {")
    for n in sorted(names):
        out.append("    %r: %r," % (n, names[n]))
    out.append("}")
    out.append("PREFIXES = %r" % (prefixes,))
    out.append("# --- конец данных ---")
    return "\n".join(out)


def jstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def java_data(records, names, prefixes):
    out = ["\tstatic {"]
    for rid in sorted(records):
        r = records[rid]
        out.append("\t\trec(%s, %s, %s, %s, %s, %s, %s, %s);" % (
            jstr(rid), jstr(r["en"]), jstr(r["say"]), jstr(r["ru"]),
            jstr(r["what"]), jstr(r["flags"]), jstr(r["short"]),
            jstr(",".join(r["ch"]))))
    for n in sorted(names):
        out.append("\t\tname(%s, %s);" % (jstr(n), jstr(names[n])))
    for p in sorted(prefixes):
        out.append("\t\tPREFIXES.put(%s, %s);" % (jstr(p), jstr(prefixes[p])))
    out.append("\t}")
    return "\n".join(out)


def java_ascii(text):
    """Все не-ASCII символы → \\uXXXX: файл читается одинаково в любой кодировке."""
    res = []
    for ch in text:
        o = ord(ch)
        if o < 128:
            res.append(ch)
        elif o <= 0xFFFF:
            res.append("\\u%04x" % o)
        else:
            o -= 0x10000
            res.append("\\u%04x\\u%04x" % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
    return "".join(res)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text, newline="\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)


def build(records, names, prefixes, outdir):
    tpl = os.path.join(HERE, "templates")
    ida = read(os.path.join(tpl, "ida_ru_hints.py.in"))
    ida = ida.replace("#@@DATA@@", py_data(records, names, prefixes))
    write(os.path.join(outdir, "ida", "ru_hints.py"), ida)
    common = read(os.path.join(tpl, "ghidra_common.java.in"))
    common = common.replace("//@@DATA@@", java_data(records, names, prefixes))
    for cls in ("RuHintExplain", "RuHintComments"):
        src = read(os.path.join(tpl, cls + ".java.in")).replace("//@@COMMON@@", common)
        write(os.path.join(outdir, "ghidra", cls + ".java"), java_ascii(src))


# ---------------------------------------------------------------------
# 4–6. Проверки
# ---------------------------------------------------------------------

def load_ida_plugin(path):
    """Загрузить плагин IDA вне IDA: модули IDA заменяются пустышками."""
    for mod in ("ida_idaapi", "ida_kernwin", "ida_bytes", "ida_funcs", "idc",
                "idautils"):
        stub = types.ModuleType(mod)
        sys.modules[mod] = stub
    k = sys.modules["ida_kernwin"]
    k.action_handler_t = type("action_handler_t", (), {"__init__": lambda self: None})
    k.UI_Hooks = type("UI_Hooks", (), {"__init__": lambda self: None})
    sys.modules["ida_idaapi"].plugmod_t = type("plugmod_t", (), {})
    sys.modules["ida_idaapi"].plugin_t = type("plugin_t", (), {})
    sys.modules["ida_idaapi"].PLUGIN_MULTI = 0x100
    spec = importlib.util.spec_from_file_location("ru_hints_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# (как пишет инструмент, текст строки) → чего ждём в первой строке подсказки
SAMPLES = [
    ("mov", "mov     eax, [rbp+var_4]", "mov — move [мув]"),
    ("jz", "jz      short loc_140001020", "jz — jump if zero"),
    ("JZ", "JZ LAB_140001020", "jz — jump if zero"),
    ("JC", "JC LAB_140001020", "jc — jump if carry"),
    ("jnb", "jnb     short loc_1", "jnb — jump if not below"),
    ("movsb", "rep movsb", "movsb — move string"),
    ("MOVSB.REP", "MOVSB.REP RDI,RSI", "movsb — move string"),
    ("CMPXCHG.LOCK", "CMPXCHG.LOCK qword ptr [RDX],RCX", "cmpxchg — compare and exchange"),
    ("cmpxchg", "lock cmpxchg [rdx], ecx", "cmpxchg — compare and exchange"),
    ("movsd", "movsd   xmm0, cs:qword_140009000", "movsd — move scalar double"),
    ("MOVSD", "MOVSD XMM0,qword ptr [RAX]", "movsd — move scalar double"),
    ("movsd", "rep movsd", "movsd — move string doubleword"),
    ("MOVSD.REP", "MOVSD.REP RDI,RSI", "movsd — move string doubleword"),
    ("int", "int     3", "int3 — interrupt 3"),
    ("INT3", "INT3", "int3 — interrupt 3"),
    ("int", "int     29h", "int — interrupt"),
    ("retn", "retn", "retn — return"),
    ("vmovdqu", "vmovdqu ymm0, ymmword ptr [rax]", "vmovdqu — move unaligned double quadword"),
    ("vzeroupper", "vzeroupper", "vzeroupper — zero upper bits"),
    ("cvttsd2si", "cvttsd2si eax, xmm0", "cvttsd2si — convert with truncation"),
    ("addsd", "addsd   xmm0, xmm1", "addsd — add scalar double"),
    ("SETNZ", "SETNZ AL", "setnz — set byte if not zero"),
    ("cmovnz", "cmovnz  eax, ecx", "cmovnz — conditional move if not zero"),
    ("xyzzy", "xyzzy eax", "xyzzy — подсказки пока нет."),
]


def check_python(plugin):
    errors = []
    for mnem, text, want in SAMPLES:
        got = plugin.describe(mnem, text)
        if not got or not got[0].startswith(want):
            errors.append("Python: %r / %r → %r, ждали начало %r"
                          % (mnem, text, got and got[0], want))
    lines = plugin.describe("MOVSB.REP", "MOVSB.REP RDI,RSI")
    if not any(l.startswith("Префикс rep") for l in lines):
        errors.append("Python: для MOVSB.REP нет строки про префикс rep")
    c = plugin.short_comment("cmpxchg", "lock cmpxchg [rdx], ecx")
    if c != "рус: lock cmpxchg — " + plugin.RECORDS["cmpxchg"]["short"] + " (П3.5)":
        errors.append("Python: короткий комментарий %r" % c)
    return errors


def objdump_samples():
    """Инструкции из учебных задач, собранных настоящим кросс-компилятором."""
    gcc, objdump = "x86_64-w64-mingw32-gcc", "x86_64-w64-mingw32-objdump"
    if not shutil.which(gcc) or not shutil.which(objdump):
        return None
    src = os.path.join(ROOT, "crackmes", "src")
    samples = []
    with tempfile.TemporaryDirectory() as tmp:
        for f in sorted(os.listdir(src)):
            if not f.endswith(".c") or f.startswith("04"):
                continue
            for opt in (["-O0"], ["-O2", "-s"]):
                exe = os.path.join(tmp, f + opt[0] + ".exe")
                r = subprocess.run([gcc] + opt + ["-o", exe, os.path.join(src, f)],
                                   capture_output=True)
                if r.returncode:
                    continue
                dis = subprocess.run([objdump, "-d", "-M", "intel", "--no-show-raw-insn",
                                      exe], capture_output=True, text=True).stdout
                for line in dis.splitlines():
                    parts = line.split("\t")
                    if len(parts) < 2 or not re.match(r"^ *[0-9a-f]+:$", parts[0]):
                        continue
                    text = parts[1].strip()
                    words = text.split()
                    # приставки, которые пишет только objdump, а IDA и Ghidra — нет
                    while words and (words[0] in ("data16", "cs", "ds", "addr32",
                                                  "notrack", "bnd")
                                     or words[0].startswith("rex")):
                        words.pop(0)
                    if not words or words[0] in ("(bad)", ".byte", ".word"):
                        continue
                    text = " ".join(words)
                    samples.append((words[0] if words[0] not in
                                    ("rep", "repz", "repnz", "repe", "repne", "lock")
                                    else (words[1] if len(words) > 1 else ""), text))
    return samples


def check_coverage(plugin, samples):
    unknown, total = {}, 0
    for mnem, text in samples:
        total += 1
        rid, shown, _, _ = plugin.resolve(mnem, text)
        if rid is None:
            unknown[shown] = unknown.get(shown, 0) + 1
    return total, unknown


def check_java(outdir, plugin, samples):
    javac, java = shutil.which("javac"), shutil.which("java")
    if not javac or not java:
        return None, ["javac не найден — скрипты Ghidra не проверены"]
    errors = []
    stubs = os.path.join(HERE, "test", "ghidra_stubs")
    with tempfile.TemporaryDirectory() as tmp:
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(stubs) for f in fs
                 if f.endswith(".java")]
        files += [os.path.join(outdir, "ghidra", "RuHintExplain.java"),
                  os.path.join(outdir, "ghidra", "RuHintComments.java"),
                  os.path.join(HERE, "test", "HintsTest.java")]
        r = subprocess.run([javac, "-encoding", "UTF-8", "-d", tmp] + files,
                           capture_output=True, text=True)
        if r.returncode:
            return None, ["javac:\n" + r.stderr[-3000:]]
        cases = [(m, t) for m, t, _ in SAMPLES] + list(samples or [])[:4000]
        inp = os.path.join(tmp, "cases.tsv")
        with open(inp, "w", encoding="utf-8") as fh:
            for m, t in cases:
                fh.write(m + "\t" + t + "\n")
        r = subprocess.run([java, "-cp", tmp, "HintsTest", inp], capture_output=True)
        if r.returncode:
            return None, ["java HintsTest:\n" + r.stderr.decode("utf-8", "replace")[-3000:]]
        got = r.stdout.decode("utf-8").split("\n\x1e\n")
        for (m, t), j in zip(cases, got):
            p = plugin.describe(m, t)
            py = "\n".join(p) if p else "<null>"
            py += "\n" + str(plugin.short_comment(m, t) or "<null>")
            if py != j:
                errors.append("Java и Python расходятся на %r / %r:\n  py: %r\n  java: %r"
                              % (m, t, py, j))
                if len(errors) > 5:
                    break
        return len(cases), errors


def main():
    d = load_data()
    records, names, errors = expand(d)
    errors += validate(records, names, d.PREFIXES)
    print("== База: записей %d, имён %d" % (len(records), len(names)))
    if errors:
        print("== Ошибки в базе:")
        for e in errors:
            print("   " + e)
        sys.exit(1)
    outdir = tempfile.mkdtemp() if CHECK_ONLY else HERE
    build(records, names, d.PREFIXES, outdir)
    print("== Собрано: %s" % ("во временную папку (--check)" if CHECK_ONLY else
                               "ida/ru_hints.py, ghidra/RuHintExplain.java, "
                               "ghidra/RuHintComments.java"))
    plugin = load_ida_plugin(os.path.join(outdir, "ida", "ru_hints.py"))
    errs = check_python(plugin)
    print("== Логика плагина IDA на %d примерах: %s" % (len(SAMPLES),
                                                       "ошибок нет" if not errs else "ОШИБКИ"))
    samples = objdump_samples()
    if samples is None:
        print("== Покрытие: кросс-компилятора нет, пропускаю "
              "(в облаке он ставится скиллом verify-example)")
    else:
        total, unknown = check_coverage(plugin, samples)
        miss = sum(unknown.values())
        print("== Покрытие на учебных задачах: %d инструкций, без подсказки %d"
              % (total, miss))
        for n, c in sorted(unknown.items(), key=lambda x: -x[1]):
            print("   нет подсказки: %-12s %d раз" % (n, c))
    ncases, jerrs = check_java(outdir, plugin, samples)
    if ncases is None:
        for e in jerrs:
            print("== " + e)
        if any(e.startswith(("javac:", "java ")) for e in jerrs):
            errs += jerrs
    else:
        print("== Скрипты Ghidra: компилируются; Java и Python совпали на %d строках: %s"
              % (ncases, "да" if not jerrs else "НЕТ"))
        errs += jerrs
    if errs:
        print("== Ошибки:")
        for e in errs:
            print("   " + e)
        sys.exit(1)
    if CHECK_ONLY:
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    main()
