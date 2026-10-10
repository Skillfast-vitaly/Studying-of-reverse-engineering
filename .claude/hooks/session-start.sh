#!/bin/bash
# Хук начала сессии курса (.claude/settings.json → hooks → SessionStart).
# Работает в облачной сессии (Linux) и на ПК ученика (Claude Code
# на Windows запускает хуки через Git Bash). Печатает сводку — Claude
# видит её в начале разговора. В курсе ничего не меняет.
# В облаке ещё ставит кросс-компилятор: состояние контейнера
# сохраняется, и в следующих сессиях он уже на месте.
set -u
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) where="pc" ;;
  *) if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then where="cloud"; else where="local"; fi ;;
esac

echo "== Сводка начала сессии (хук .claude/hooks/session-start.sh)"
case "$where" in
  pc)    echo "   Где мы: ПК ученика, Windows. Правила — CLAUDE.md, раздел «На ПК ученика»." ;;
  cloud) echo "   Где мы: облачная сессия (Linux, контейнер)." ;;
  *)     echo "   Где мы: $(uname -s 2>/dev/null), локальная машина." ;;
esac

if [ "$where" = cloud ] && ! command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1; then
  pkgs="gcc-mingw-w64-x86-64 binutils-mingw-w64-x86-64"
  if apt-get install -y -q $pkgs >/dev/null 2>&1 ||
     { apt-get update -q >/dev/null 2>&1 && apt-get install -y -q $pkgs >/dev/null 2>&1; }; then
    echo "   Кросс-компилятор x86_64-w64-mingw32-gcc поставлен."
  else
    echo "   Кросс-компилятор поставить не удалось — verify-example попробует сам."
  fi
fi

if ! command -v git >/dev/null 2>&1 || ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "   Git не найден, или папка курса скачана без git (архивом ZIP)."
  echo "   Помоги ученику поставить Git for Windows и клонировать курс:"
  echo "   README, раздел «Курс у тебя на ПК»."
  exit 0
fi

echo
FRESHEST_QUICK=1 bash .claude/skills/start-session/scripts/freshest_branch.sh 2>&1 | head -60
echo
echo "== Дальше — скилл start-session: первым делом спроси ученика, где он"
echo "   и что было трудно. Новые главы — только после этого."
exit 0
