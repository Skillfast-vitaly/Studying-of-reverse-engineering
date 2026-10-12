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

written = {int(p.name[:2]) for p in COURSE.glob("*.md") if p.name[:2].isdigit()}
problems = 0

for f in sorted(COURSE.glob("*.md")):
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

# Ссылки на разделы: «глава 12.5», «(16.5)», «П9.10» должны вести на
# существующий заголовок «## 12.5.» Битая ссылка на раздел — ученик ищет
# то, чего нет. Номера версий («rustc 1.99», «версия 3.21») пропускаем.
heads = set()
for f in sorted(COURSE.glob("*.md")):
    for l in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"## (П?\d+)\.(\d+)\.", l)
        if m:
            heads.add(m.group(1) + "." + m.group(2))
ref = re.compile(r"(?<![\d.\w/])(П\d+|[1-4]?\d)\.([1-9]\d?)(?![\d.]*\d)(?=[\s,)–—:;»]|\.\s|$)")
version = re.compile(r"(rustc|python|py|версия|версии|v|под|ida|ghidra|wireshark|npcap|gcc)[\s:-]*$", re.I)
bad_sections = 0
for f in sorted(COURSE.glob("*.md")) + [ROOT / "ANSWERS.md", ROOT / "PRACTICE.md", ROOT / "CAREER.md"]:
    if not f.exists():
        continue
    incode = False
    for n, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if l.startswith("```"):
            incode = not incode
            continue
        if incode:
            continue
        for m in ref.finditer(l):
            before = l[max(0, m.start() - 30):m.start()]
            if not (m.group(1).startswith("П") or re.search(r"(глав|раздел|\()", before)):
                continue
            if version.search(before.rstrip("— ").rstrip()):
                continue
            if not m.group(1).startswith("П") and int(m.group(1)) > 40:
                continue
            key = m.group(1) + "." + m.group(2)
            if key not in heads:
                bad_sections += 1
                print(f"  НЕТ РАЗДЕЛА {key}: {f.relative_to(ROOT)}:{n}  …{l[max(0, m.start() - 25):m.end() + 5].strip()}…")
print(f"Ссылок на несуществующие разделы: {bad_sections}")
sys.exit(1 if problems or bad_sections else 0)
