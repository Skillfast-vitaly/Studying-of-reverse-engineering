#!/usr/bin/env bash
# Проверка примера для курса: собрать под Windows настоящим кросс-компилятором,
# снять факты о .exe, прогнать ту же логику под Linux.
#
#   bash .claude/skills/verify-example/scripts/build_win.sh файл.c [ещё.c|.s ...]
#        [--out папка] [--run "ввод"] [--flags "-DX -lm"] [--asm функция]
#
# --out    куда класть сборку (по умолчанию ./build-check, её не коммитим)
# --run    что подать на вход программе при прогоне под Linux
# --flags  дополнительные флаги gcc для обеих сборок
# --asm    показать ассемблер этой функции (-O0, синтаксис Intel)
set -u
srcs=() out=build-check input="" flags="" asmfn=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) out=$2; shift 2 ;;
    --run) input=$2; shift 2 ;;
    --flags) flags=$2; shift 2 ;;
    --asm) asmfn=$2; shift 2 ;;
    -*) echo "неизвестный ключ $1" >&2; exit 2 ;;
    *) srcs+=("$1"); shift ;;
  esac
done
[ ${#srcs[@]} -gt 0 ] || { sed -n '2,13p' "$0"; exit 2; }
CC=x86_64-w64-mingw32-gcc
if ! command -v $CC >/dev/null; then
  echo "== Ставлю кросс-компилятор (раздел 4 CLAUDE.md)"
  apt-get install -y -q gcc-mingw-w64-x86-64 binutils-mingw-w64-x86-64 >/dev/null 2>&1 ||
    { apt-get update -q >/dev/null 2>&1 && apt-get install -y -q gcc-mingw-w64-x86-64 binutils-mingw-w64-x86-64 >/dev/null 2>&1; } ||
    { echo "не удалось поставить $CC" >&2; exit 1; }
fi
OBJDUMP=x86_64-w64-mingw32-objdump
mkdir -p "$out"
name=$(basename "${srcs[0]}"); name=${name%.*}
csrcs=(); for s in "${srcs[@]}"; do case "$s" in *.c) csrcs+=("$s") ;; esac; done

echo "== Компилятор: $($CC --version | head -1)"
echo "   (у ученика w64devkit с другой версией gcc: листинг может отличаться в мелочах)"
echo
echo "== Привычные ловушки курса"
trap_found=0
for s in "${srcs[@]}"; do
  if grep -n '%zu' "$s"; then
    echo "   $s: %zu — w64devkit печатает через msvcrt.dll, там %zu нет; пиши %llu и (unsigned long long)"; trap_found=1; fi
  if grep -nP '"[^"]*[^\x00-\x7F][^"]*"' "$s" | head -3 | grep -q .; then
    grep -nP '"[^"]*[^\x00-\x7F][^"]*"' "$s" | head -3
    echo "   $s: не-ASCII в строке — консоль Windows покажет кракозябры; сообщения пиши транслитом"; trap_found=1; fi
  if grep -nP '(?<!long )\blong\b(?! long)' "$s" | grep -v '^\s*//' | head -3 | grep -q .; then
    grep -nP '(?<!long )\blong\b(?! long)' "$s" | head -3
    echo "   $s: long — на Windows 32 бита, на Linux 64: прогон под Linux может разойтись с Windows; бери uint32_t/uint64_t (П1)"; trap_found=1; fi
  if grep -nE '__readgsqword|__readfsdword|gs:\[' "$s" | head -3 | grep -q .; then
    echo "   $s: прямое чтение структур процесса через gs: — в примерах курса держимся документированных функций WinAPI"; trap_found=1; fi
done
[ $trap_found = 0 ] && echo "   не найдено"

echo
echo "== Сборка под Windows"
ok=1
$CC -O0 -Wall -Wextra $flags -o "$out/$name.O0.exe" "${srcs[@]}" 2>"$out/$name.O0.log" || ok=0
$CC -O2 -s -Wall -Wextra $flags -o "$out/$name.O2s.exe" "${srcs[@]}" 2>"$out/$name.O2s.log" || ok=0
cat "$out/$name.O0.log"
if [ $ok = 0 ]; then echo "   СБОРКА НЕ УДАЛАСЬ — смотри сообщения выше и $out/$name.O2s.log"; exit 1; fi
[ -s "$out/$name.O0.log" ] || echo "   -O0: без предупреждений"
for v in O0 O2s; do
  f="$out/$name.$v.exe"
  printf '   %-22s %7d байт  %s\n' "$name.$v.exe" "$(stat -c %s "$f")" "$(file -b "$f" | cut -d, -f1-2)"
done

echo
echo "== Факты о $name.O0.exe (настоящие, их можно брать в главу)"
$OBJDUMP -p "$out/$name.O0.exe" | grep -E '^(ImageBase|AddressOfEntryPoint|SizeOfImage|Subsystem|DllCharacteristics)' | sed 's/^/   /'
echo "   секции:"
$OBJDUMP -h "$out/$name.O0.exe" | awk '/^ *[0-9]+ /{printf "     %-8s VMA %s  размер %s\n", $2, $4, $3}'
echo "   импорт:"
$OBJDUMP -p "$out/$name.O0.exe" | awk '
  /DLL Name:/ {dll=$3; printf "     %s:", dll; n=0; next}
  dll && /^\t[0-9a-f]+\t *[0-9]+ +[A-Za-z_?]/ {if (n<12) printf " %s", $3; n++; next}
  dll && /^$/ {if (n>12) printf " … (всего %d)", n; if (n) print ""; dll=""}'

if [ ${#csrcs[@]} -gt 0 ]; then
  $CC -S -O0 -masm=intel $flags -o "$out/$name.O0.s" "${csrcs[0]}" 2>/dev/null &&
    echo "   ассемблер -O0 (Intel): $out/$name.O0.s"
fi
if [ -n "$asmfn" ]; then
  echo
  echo "== Машинный код $asmfn в $name.O0.exe (-O0, Intel; адреса — от ImageBase)"
  $OBJDUMP -d -M intel --no-show-raw-insn --disassemble="$asmfn" "$out/$name.O0.exe" |
    awk '/^[0-9a-f]+ </{p=1} p && !/\tnop *$/' | head -80
fi

echo
echo "== Прогон логики под Linux"
if grep -qE '#include *<(windows|winternl|intrin|conio)\.h>' "${srcs[@]}"; then
  echo "   Пример завязан на Windows-заголовки — так не прогнать."
  echo "   Варианты: прокладка windows.h в scratchpad (см. SKILL.md) или пометка «примерно так»."
else
  if gcc -O0 -w $flags -o "$out/$name.linux" "${srcs[@]}" 2>"$out/$name.linux.log"; then
    echo "   вход: ${input:-(пусто)}"
    printf '%s\n' "$input" | timeout 10 "$out/$name.linux"; echo "   код возврата: $?"
  else
    echo "   под Linux не собралось:"; sed 's/^/   /' "$out/$name.linux.log" | head -10
  fi
fi
