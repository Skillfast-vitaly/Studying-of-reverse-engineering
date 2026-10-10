#!/usr/bin/env bash
# Сводка для начала сессии: какая ветка курса самая свежая, как её влить,
# что лежит в других ветках, где ученик и какие главы заняты другими сессиями.
# Ничего не меняет — только читает. Запуск из любой папки репозитория:
#   bash .claude/skills/start-session/scripts/freshest_branch.sh
# Работает и в облаке (Linux), и на ПК ученика (Git Bash на Windows).
# FRESHEST_QUICK=1 — одна попытка git fetch без ожиданий (так зовёт хук
# начала сессии, чтобы не задерживать старт).
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1

if [ "${FRESHEST_QUICK:-}" = 1 ]; then
  git fetch origin --prune -q 2>/dev/null ||
    echo "git fetch не удался — сводка по тому, что уже скачано" >&2
else
  for i in 1 2 3 4; do
    git fetch origin --prune -q 2>/dev/null && break
    echo "git fetch не удался (попытка $i), жду $((2 ** i)) с" >&2
    sleep $((2 ** i))
  done
fi

# Python: на Windows вместо python3 обычно python или py, а python3 бывает
# заглушкой Microsoft Store, которая только печатает ошибку.
PY=""
for c in python3 python py; do
  if "$c" -c "import sys" >/dev/null 2>&1; then PY=$c; break; fi
done

# обрезать длинные строки по символам (cut -c режет байты и ломает кириллицу)
trunc() {
  if [ -n "$PY" ]; then
    PYTHONIOENCODING=utf-8 "$PY" -c 'import sys
sys.stdin.reconfigure(encoding="utf-8")
for l in sys.stdin: print(l.rstrip("\n")[:150])'
  else
    cut -c1-300
  fi
}

branches() {
  git for-each-ref --sort=-committerdate --format='%(refname:short)' refs/remotes/origin |
    grep -vx 'origin/HEAD' | grep -vx 'origin'
}

cur=$(git branch --show-current)
echo "== Твоя ветка: $cur"
git log -1 --format='   %h  %ad  %s' --date=format:'%Y-%m-%d %H:%M' HEAD | trunc
echo "   сегодня: $(date -u +%Y-%m-%d)"
echo
echo "== Самые свежие ветки на сервере:"
git for-each-ref --sort=-committerdate refs/remotes/origin \
  --format='   %(committerdate:format:%Y-%m-%d %H:%M)  %(refname:short)  %(subject)' |
  grep -v ' origin/HEAD ' | head -6 | trunc

newest=$(branches | head -1)
echo
echo "== Самая свежая: $newest"
if git merge-base --is-ancestor "$newest" HEAD; then
  echo "   Уже в твоей ветке — вливать нечего."
elif git merge-base --is-ancestor HEAD "$newest"; then
  echo "   Можно влить перемоткой:  git merge --ff-only $newest"
else
  echo "   Ветки разошлись. Обычное слияние:  git merge $newest"
  echo "   При конфликте в CLAUDE.md сохраняй записи обеих сессий."
fi

echo
echo "== Ветки, которых нет в $newest:"
found=0
for b in $(branches); do
  git merge-base --is-ancestor "$b" "$newest" && continue
  found=1
  if [ -z "$(git merge-base "$b" "$newest" 2>/dev/null)" ]; then
    added=$(git diff --name-only --diff-filter=A "$newest" "$b" | wc -l)
    echo "   $b — несвязанная старая история; файлов, которых нет в свежей: $added"
  else
    echo "   $b — своих коммитов: $(git rev-list --count "$newest..$b")" \
         "(смотри: git log --oneline $newest..$b)"
  fi
done
[ "$found" = 0 ] && echo "   таких нет — свежая ветка содержит всё."

echo
echo "== Ученик (PROGRESS.md):"
if [ -f PROGRESS.md ]; then
  echo "   отмечено пунктов [x]: $(grep -c '^- \[x\]' PROGRESS.md)"
  awk '/^## Затыки/{f=1; next} /^## /{f=0}
       f && /^\|/ && !/^\|[ -]*\|[ -]*\|[ -]*\|$/ {n++}
       END{print "   записей в «Затыки»: " (n > 0 ? n - 1 : 0)}' PROGRESS.md
else
  echo "   файла нет"
fi

echo
echo "== Заявки на главы (последние в CLAUDE.md; «снята» — свободна):"
grep -nE 'берёт главу|[Зз]аявка .*снята' CLAUDE.md | tail -4 | trunc
echo
echo "== Обрывы фильтром (последние упоминания):"
grep -nE 'оборвал' CLAUDE.md | tail -4 | trunc
