#!/bin/bash
# Хук UserPromptSubmit: передаёт сообщение ученика маршрутизатору скиллов
# (skill_router.py), а тот печатает подсказку, какой скилл курса подходит.
# Claude видит её и сам вызывает скилл — ученику не нужно набирать /команды.
# На Windows Claude Code запускает хуки через Git Bash; python ищем сам,
# потому что python3 там бывает заглушкой Microsoft Store.
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true
for c in python3 python py; do
  if "$c" -c "import sys" >/dev/null 2>&1; then
    exec "$c" .claude/hooks/skill_router.py
  fi
done
echo "Подсказка хука: подбери скилл курса к этой просьбе (CLAUDE.md, раздел 7) и вызови его сам."
