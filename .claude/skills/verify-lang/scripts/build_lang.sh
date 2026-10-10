#!/usr/bin/env bash
# Проверка примера на C++, Rust или Python для приложений П6–П8:
# настоящий компилятор под Windows x64, а не память модели.
#
#   bash .claude/skills/verify-lang/scripts/build_lang.sh файл.cpp|.rs|.py
#        [--fn часть_имени] [--opt 0|1|2] [--run "ввод"] [--out папка]
#
# C++    объектный файл в стиле MSVC: clang --target=x86_64-pc-windows-msvc
#        (те же искажённые имена, таблицы vtable и соглашение о вызовах,
#        что у программ, собранных Visual Studio). Если есть main —
#        ещё .exe через x86_64-w64-mingw32-g++ и прогон логики под Linux.
# Rust   объектный файл под x86_64-pc-windows-msvc (rustc --emit=obj).
#        Если есть main — прогон логики под Linux.
# Python проверка синтаксиса и запуск.
set -u
src="" fn="" opt=1 input="" out=build-check
while [ $# -gt 0 ]; do
  case "$1" in
    --fn) fn=$2; shift 2 ;;
    --opt) opt=$2; shift 2 ;;
    --run) input=$2; shift 2 ;;
    --out) out=$2; shift 2 ;;
    -*) echo "неизвестный ключ $1" >&2; exit 2 ;;
    *) src=$1; shift ;;
  esac
done
[ -n "$src" ] && [ -f "$src" ] || { sed -n '2,16p' "$0"; exit 2; }
mkdir -p "$out"
name=$(basename "$src"); name=${name%.*}

need_apt() {  # поставить пакет, если нет команды (только облако)
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "== Ставлю $2"
  apt-get install -y -q $2 >/dev/null 2>&1 ||
    { apt-get update -q >/dev/null 2>&1 && apt-get install -y -q $2 >/dev/null 2>&1; }
  command -v "$1" >/dev/null 2>&1 || { echo "   не удалось поставить $2" >&2; return 1; }
}

show_obj() {  # дизассемблер (Intel) и имена из объектного файла
  local obj=$1
  echo
  echo "== Функции и данные в $(basename "$obj"): имя в файле → по-человечески"
  paste -d'\t' <(llvm-nm --defined-only "$obj" | awk '{print $3}') \
                <(llvm-nm --defined-only -C "$obj" | cut -d' ' -f3-) |
    grep -v -P '^\.|^\$|^@feat' | head -40 |
    awk -F'\t' '{ if ($1 == $2) printf "   %s\n", $1; else printf "   %-44s %s\n", $1, $2 }'
  echo
  echo "== Машинный код${fn:+ (только «$fn»)}, синтаксис Intel"
  llvm-objdump -d -C --x86-asm-syntax=intel --no-show-raw-insn "$obj" |
    awk -v f="$fn" '/^[0-9a-f]+ </ {p = (f == "" || index($0, f) > 0)} p' |
    grep -v -E '^\s*$|file format|Disassembly of' | head -120
}

case "$src" in
  *.cpp|*.cc|*.cxx)
    need_apt clang "clang llvm" || exit 1
    echo "== $(clang --version | head -1)"
    obj="$out/$name.msvc.obj"
    if clang --target=x86_64-pc-windows-msvc -O"$opt" -fno-rtti -c "$src" -o "$obj" 2>"$out/$name.msvc.log"; then
      echo "   объектный файл в стиле MSVC: $obj (-O$opt, без RTTI)"
      echo "   примечание: заголовков Visual Studio (STL) в облаке нет — std::string"
      echo "   и std::vector бери из исходников microsoft/STL (SKILL.md)"
      show_obj "$obj"
    else
      echo "   сборка в стиле MSVC не удалась:"; sed 's/^/   /' "$out/$name.msvc.log" | head -6
      if grep -q "file not found" "$out/$name.msvc.log"; then
        echo "   Заголовков Visual Studio в облаке нет. Для разбора в стиле MSVC пиши"
        echo "   пример без #include: объяви нужное сам, например"
        echo '   extern "C" int printf(const char *, ...);'
      fi
    fi
    if grep -qE '\bint\s+main\s*\(' "$src"; then
      echo
      if need_apt x86_64-w64-mingw32-g++ "g++-mingw-w64-x86-64"; then
        x86_64-w64-mingw32-g++ -O"$opt" -static -o "$out/$name.exe" "$src" 2>&1 | head -10 &&
          echo "== .exe (MinGW, другие имена и своя STL): $out/$name.exe, $(wc -c < "$out/$name.exe") байт"
      fi
      if g++ -O"$opt" -o "$out/$name.linux" "$src" 2>"$out/$name.linux.log"; then
        echo "== Прогон логики под Linux, вход: ${input:-(пусто)}"
        printf '%s\n' "$input" | timeout 10 "$out/$name.linux"; echo "   код возврата: $?"
      else
        echo "== Под Linux не собралось (код завязан на Windows?):"; head -5 "$out/$name.linux.log"
      fi
    fi
    ;;
  *.rs)
    command -v rustc >/dev/null || { echo "rustc не найден (rustup: static.rust-lang.org)" >&2; exit 1; }
    if ! rustup target list --installed 2>/dev/null | grep -q x86_64-pc-windows-msvc; then
      echo "== Ставлю цель x86_64-pc-windows-msvc (официально, через rustup)"
      rustup target add x86_64-pc-windows-msvc >/dev/null 2>&1 || { echo "   не удалось" >&2; exit 1; }
    fi
    need_apt llvm-objdump llvm || exit 1
    echo "== $(rustc --version)"
    obj="$out/$name.win.obj"
    kind=lib; grep -qE '\bfn\s+main\s*\(' "$src" && kind=bin
    rustc --target x86_64-pc-windows-msvc --crate-type $kind --emit=obj -C opt-level="$opt" \
      --edition 2021 -A dead_code "$src" -o "$obj" 2>"$out/$name.rs.log" ||
      { echo "   сборка не удалась:"; sed 's/^/   /' "$out/$name.rs.log" | head -20; exit 1; }
    echo "   объектный файл под Windows: $obj ($kind, -C opt-level=$opt)"
    show_obj "$obj"
    if [ -n "$fn" ] && ! llvm-nm -C --defined-only "$obj" | grep -qF "$fn"; then
      echo "   Функции «$fn» в файле нет: компилятор её выкинул или встроил."
      echo "   Помечай учебные функции pub и #[inline(never)]."
    fi
    if grep -qE '\bfn\s+main\s*\(' "$src"; then
      rustc --edition 2021 -C opt-level="$opt" "$src" -o "$out/$name.linux" 2>"$out/$name.linux.log" &&
        { echo; echo "== Прогон логики под Linux, вход: ${input:-(пусто)}";
          printf '%s\n' "$input" | timeout 10 "$out/$name.linux"; echo "   код возврата: $?"; }
    fi
    ;;
  *.py)
    py=python3; command -v $py >/dev/null || py=python
    echo "== $($py --version 2>&1)"
    $py -m py_compile "$src" && echo "   синтаксис в порядке"
    echo "== Запуск, вход: ${input:-(пусто)}"
    printf '%s\n' "$input" | timeout 20 $py "$src"; echo "   код возврата: $?"
    ;;
  *) echo "поддерживаются .cpp, .rs, .py; для C — verify-example" >&2; exit 2 ;;
esac
