#!/usr/bin/env python3
"""Проверка целостности курса. Ловит дефекты, реально встречавшиеся при работе."""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COURSE = ROOT / "course"
problems = []

def add(kind, where, what):
    problems.append((kind, where, what))

md_files = sorted(COURSE.glob("*.md")) + [ROOT / f for f in
    ("README.md", "GLOSSARY.md", "ANSWERS.md", "CLAUDE.md") if (ROOT / f).exists()]

# готовые главы = те, что реально существуют
existing = {p.name for p in COURSE.glob("*.md")}

for f in md_files:
    text = f.read_text(encoding="utf-8")
    rel = f.relative_to(ROOT)

    # 1. парность блоков кода
    if text.count("```") % 2:
        add("КОД", rel, "нечётное число ``` — блок кода не закрыт")

    # 2. Склейка markdown-маркера со словом: «…данными**и его можно…».
    # Выделение части слова — законный приём объяснения английских
    # сокращений (**j**ump, **comp**are). Отличаем по расстоянию до
    # открывающего маркера: у внутрисловного выделения он рядом,
    # у слипшейся фразы — далеко.
    for m in re.finditer(r"[а-яёa-z]\*\*[а-яёa-zА-ЯЁ]", text):
        if "**" in text[max(0, m.start() - 8):m.start()]:
            continue
        line = text[:m.start()].count("\n") + 1
        add("ВЁРСТКА", f"{rel}:{line}", "слипшийся маркер ** после фразы")

    # 3. битые ссылки на .md
    for m in re.finditer(r"\]\(([^)#]+\.md)[^)]*\)", text):
        target = m.group(1)
        line = text[:m.start()].count("\n") + 1
        resolved = (f.parent / target).resolve()
        if not resolved.exists():
            name = pathlib.Path(target).name
            # ссылка на будущую главу — это план, не ошибка
            if re.match(r"^\d\d-", name) and name not in existing:
                continue
            add("ССЫЛКА", f"{rel}:{line}", f"нет файла {target}")

    # 4. остатки Linux-инструментов в главах
    if f.parent == COURSE:
        for m in re.finditer(r"\b(objdump|readelf|strace|ltrace)\b", text):
            line = text[:m.start()].count("\n") + 1
            add("LINUX", f"{rel}:{line}", f"инструмент {m.group(1)} — курс под Windows")

    # 5. дубли подряд (артефакт склейки кусков).
    # Схемы и таблицы дают ложные срабатывания, поэтому блоки кода вырезаем,
    # а повтор считаем значимым, только если в нём есть настоящие буквы.
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    for m in re.finditer(r"(.{15,}?)\1", prose):
        frag = m.group(1)
        if len(re.findall(r"[А-Яа-яёA-Za-z]", frag)) < 5:
            continue
        line = prose[:m.start()].count("\n") + 1
        add("ДУБЛЬ", f"{rel}:~{line}", f"повтор: {frag[:40]!r}")

# 6. упражнения глав покрыты ответами
answers = (ROOT / "ANSWERS.md").read_text(encoding="utf-8") if (ROOT / "ANSWERS.md").exists() else ""
for f in sorted(COURSE.glob("*.md")):
    num = f.name[:2].lstrip("0") or "0"
    if num == "0":
        continue
    if "## Упражнения" in f.read_text(encoding="utf-8"):
        if not re.search(rf"^## Глава {num}\.", answers, re.M):
            add("ОТВЕТЫ", f.name, f"нет раздела «Глава {num }» в ANSWERS.md")

if problems:
    print(f"Найдено проблем: {len(problems)}\n")
    for kind, where, what in problems:
        print(f"  [{kind}] {where}\n      {what}")
    sys.exit(1)
print("Курс чист: проблем не найдено.")
