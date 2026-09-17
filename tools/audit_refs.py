#!/usr/bin/env python3
"""
Аудит перекрёстных ссылок курса.

Курс писался частями, карта глав по дороге расширялась с 25 до 40 глав.
Отсылки вида «разберём в главе N» при этом легко разъезжаются с картой.
Скрипт сверяет каждую такую отсылку с README и показывает контекст,
чтобы можно было глазами проверить осмысленность.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COURSE = ROOT / "course"

# карта глав из README: номер -> название
readme = (ROOT / "README.md").read_text(encoding="utf-8")
chapters = {}
for m in re.finditer(r"\|\s*(?:✅|🚧|⬜)\s*\|\s*(?:\[)?(\d+)\.\s*([^\]|]+?)(?:\]\([^)]+\))?\s*\|", readme):
    chapters[int(m.group(1))] = m.group(2).strip()

# карта частей
parts = {}
for m in re.finditer(r"### Часть ([IVX]+)\.\s*(.+)", readme):
    parts[m.group(1)] = m.group(2).strip()

print(f"В карте курса: {len(chapters)} глав, {len(parts)} частей\n")

written = {int(p.name[:2]) for p in COURSE.glob("*.md")}
problems = 0

for f in sorted(COURSE.glob("*.md")):
    own = int(f.name[:2])
    text = f.read_text(encoding="utf-8")
    rows = []
    for m in re.finditer(r"глав[а-яё]*\s+(\d+)", text, re.I):
        n = int(m.group(1))
        line = text[:m.start()].count("\n") + 1
        ctx = text[max(0, m.start()-60):m.end()+50].replace("\n", " ")
        status = "написана" if n in written else "будущая"
        if n not in chapters:
            status = "НЕТ В КАРТЕ"
            problems += 1
        rows.append((line, n, chapters.get(n, "?"), status, ctx.strip()))
    if rows:
        print(f"── {f.name}")
        for line, n, name, status, ctx in rows:
            mark = "!" if status == "НЕТ В КАРТЕ" else " "
            print(f" {mark} :{line:<4} глава {n:<2} = {name[:38]:<38} [{status}]")
            print(f"      …{ctx[:100]}…")
        print()

print(f"Отсылок на главы, отсутствующие в карте: {problems}")
sys.exit(1 if problems else 0)
