#!/usr/bin/env python3
"""Компиляция примера курса настоящим MinGW gcc (gcc под Windows) через API
Compiler Explorer (godbolt.org) — без установки компилятора.

Когда нужен: на макбуке ученика (кросс-компилятора там нет и ставить его
нельзя без согласия) и как второе мнение рядом с build_win.sh в облаке.

    python3 godbolt_mingw.py пример.c                       # ошибки и предупреждения
    python3 godbolt_mingw.py пример.c --flags=-O1 --asm check     # ассемблер функции
    python3 godbolt_mingw.py пример.c "--flags=-O2 -s"              # флаги через =, иначе
                                                                    # argparse примет -O2 за свой ключ
    python3 godbolt_mingw.py пример.c --compiler cmingw64_ucrt_gcc_1520
    python3 godbolt_mingw.py пример.c --crt ucrt                   # как на сайте godbolt
    python3 godbolt_mingw.py пример.c --compiler vc_v19_latest_x64 --flags=/O2 --asm vuln
                                                                    # настоящий Visual Studio

Режим библиотеки. godbolt собран с UCRT, а w64devkit ученика — с msvcrt-os.
По умолчанию (--crt msvcrt) скрипт добавляет -D__MSVCRT_VERSION__=0x700,
и заголовки MinGW ведут себя как у ученика: printf в листинге зовётся
__mingw_printf. --crt ucrt — как на самом сайте godbolt (глава 5).

Что умеет: компиляция с заголовками Windows (windows.h, winsock2.h),
предупреждения -Wall -Wextra, ассемблер в синтаксисе Intel — тот самый,
что ученик увидит на godbolt в главе 5. Чего НЕ умеет: собрать .exe
целиком (компоновка с библиотеками) и запустить его — это build_win.sh
в облаке или ученик на ПК. Числа в листинге gcc печатает десятичными
(7777, 90), а IDA и x64dbg покажут их в hex (1E61h, 5Ah).

Список MinGW-компиляторов: curl https://godbolt.org/api/compilers/c | grep -i mingw
(11.10.2026 свежий — MinGW gcc 16.2.0, id cmingw64_ucrt_gcc_1620).
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request

API = 'https://godbolt.org/api/compiler/%s/compile'


def post(url, payload):
    data = json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        return json.load(urllib.request.urlopen(req, timeout=120))
    except Exception:
        # у Python с python.org на macOS бывают не настроены корневые
        # сертификаты — тогда через curl, он берёт системные
        out = subprocess.run(['curl', '-sS', '-m', '120', '-X', 'POST',
                              '-H', 'Content-Type: application/json',
                              '-H', 'Accept: application/json',
                              '--data-binary', '@-', url],
                             input=data, capture_output=True, check=True).stdout
        return json.loads(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('source')
    ap.add_argument('--compiler', default='cmingw64_ucrt_gcc_1620')
    ap.add_argument('--flags', default='-O0')
    ap.add_argument('--asm', metavar='ФУНКЦИЯ', help='показать ассемблер этой функции')
    ap.add_argument('--crt', choices=['msvcrt', 'ucrt'], default='msvcrt',
                    help='msvcrt — как w64devkit ученика (по умолчанию), ucrt — как сайт godbolt')
    a = ap.parse_args()
    src = open(a.source, encoding='utf-8').read()
    msvc = a.compiler.startswith('vc_')          # Visual Studio: свои ключи, листинг MASM
    if msvc:
        flags = '/O2' if a.flags == '-O0' else a.flags
    else:
        flags = '-Wall -Wextra -masm=intel ' + a.flags
        if a.crt == 'msvcrt':
            flags += ' -D__MSVCRT_VERSION__=0x700'
    d = post(API % a.compiler, {'source': src, 'options': {'userArguments': flags,
             'filters': {'intel': True, 'labels': True, 'directives': True,
                         'commentOnly': True, 'demangle': True, 'libraryCode': True}}})
    print('== %s, флаги: %s' % (a.compiler, flags))
    for e in d.get('stderr', []):
        print(e.get('text', ''))
    print('код возврата компилятора: %s' % d.get('code'))
    if a.asm:
        on = False
        offsets = []                               # у MSVC перед PROC: «buf$ = 32»
        for line in d.get('asm', []):
            t = line.get('text', '')
            if msvc:                               # «имя PROC» … «имя ENDP»
                if not on and re.match(r'\S+\$ = \d+$', t.strip()):
                    offsets.append(t)
                    continue
                if t.split()[:2] == [a.asm, 'PROC']:
                    on = True
                    print('\n'.join(offsets))
                elif not on:
                    offsets = []
                if on:
                    print(t)
                if on and t.split()[:2] == [a.asm, 'ENDP']:
                    break
                continue
            if t.rstrip(':').strip('"') == a.asm:
                on = True
            elif on and t and not t.startswith((' ', '\t', '.')):
                break
            if on:
                print(t)
        if not on:
            print('функция %s в листинге не найдена' % a.asm)
    return 0 if d.get('code') == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
