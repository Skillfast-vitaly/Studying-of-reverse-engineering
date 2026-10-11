#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собрать все полные программы на C из глав курса (блоки ```c с main)
настоящим компилятором под Windows. Пример в главе, который не
собирается, — первое место, где ученик упрётся.

    python3 tools/check_examples.py

Компилятор: x86_64-w64-mingw32-gcc (облако; ставит хук начала сессии)
или gcc из w64devkit (ПК ученика). Блоки, которые не должны собираться
сами по себе (вывод декомпилятора, фрагмент упражнения, часть проекта
из нескольких файлов), перечислены в SKIP с причиной. Новый такой блок
добавляй туда же, с причиной.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (файл главы, номер блока ```c в этой главе) → почему не собирается сам
SKIP = {
    ("14-ghidra.md", 1): "кусок исходника главы 13 рядом с выводом Ghidra",
    ("14-ghidra.md", 5): "вывод декомпилятора Ghidra (типы uint, FUN_…)",
    ("26-processy-i-potoki.md", 3): "фрагмент упражнения 26.7 «найди ошибку»",
    ("p1-si-pishem-sami.md", 18): "проект из трёх файлов: нужен pte.h из П1",
    ("p2-assembler-pishem-sami.md", 1): "C-часть; функция add3 — в файле .s",
    ("p2-assembler-pishem-sami.md", 3): "C-часть; функция — в файле .s",
    ("p2-assembler-pishem-sami.md", 4): "C-часть; функция — в файле .s",
    ("p2-assembler-pishem-sami.md", 7): "проект: нужен cpu.h и файлы .s из П2",
}


def compiler():
    for cc in ("x86_64-w64-mingw32-gcc", "gcc"):
        path = shutil.which(cc)
        if not path:
            continue
        r = subprocess.run([path, "-dumpmachine"], capture_output=True, text=True)
        if "mingw" in r.stdout:
            return path
    return None


GODBOLT_CC = "cmingw64_ucrt_gcc_1620"   # MinGW gcc 16.2 — та же версия, что в w64devkit 2.10.0


def godbolt(code):
    """Компиляция без компоновки настоящим MinGW gcc через API godbolt.org
    (режим --godbolt: на макбуке ученика кросс-компилятора нет)."""
    import json
    body = json.dumps({"source": code, "options": {"userArguments": "-O0 -w",
                       "filters": {"intel": True, "directives": True, "labels": True}}}).encode()
    out = subprocess.run(["curl", "-sS", "-m", "120", "-X", "POST",
                          "-H", "Content-Type: application/json", "-H", "Accept: application/json",
                          "--data-binary", "@-",
                          "https://godbolt.org/api/compiler/%s/compile" % GODBOLT_CC],
                         input=body, capture_output=True, check=True).stdout
    d = json.loads(out)
    err = "\n".join(e.get("text", "") for e in d.get("stderr", []))
    return d.get("code") == 0, err


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    use_godbolt = "--godbolt" in sys.argv
    cc = None if use_godbolt else compiler()
    if not cc and not use_godbolt:
        print("Нет компилятора под Windows (x86_64-w64-mingw32-gcc или gcc из w64devkit).")
        print("Без него: python3 tools/check_examples.py --godbolt (MinGW gcc 16.2 через godbolt.org)")
        sys.exit(2)
    if use_godbolt:
        print("Режим --godbolt: %s, только компиляция, без компоновки" % GODBOLT_CC)
    built, skipped, failed = 0, 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for f in sorted(glob.glob(os.path.join(ROOT, "course", "*.md"))):
            name = os.path.basename(f)
            text = open(f, encoding="utf-8").read()
            for i, m in enumerate(re.finditer(r"```c\n(.*?)```", text, re.S)):
                code = m.group(1)
                if not re.search(r"\bint\s+main\s*\(", code):
                    continue
                if (name, i) in SKIP:
                    skipped += 1
                    continue
                line = text[:m.start()].count("\n") + 1
                if use_godbolt:
                    ok, stderr = godbolt(code)
                else:
                    src = os.path.join(tmp, "ex.c")
                    open(src, "w", encoding="utf-8").write(code)
                    r = subprocess.run([cc, "-O0", "-w", "-o", os.path.join(tmp, "ex.exe"), src],
                                       capture_output=True, text=True)
                    ok, stderr = r.returncode == 0, r.stderr
                if ok:
                    built += 1
                else:
                    err = next((l for l in stderr.splitlines() if "error" in l), stderr[:200])
                    failed.append("%s:%d (блок %d): %s" % (name, line, i, err.strip()[:160]))
    print("Полных программ на C в главах: %d собрано, %d пропущено по списку SKIP, %d не собралось"
          % (built, skipped, len(failed)))
    for x in failed:
        print("   НЕ СОБРАЛОСЬ " + x)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
