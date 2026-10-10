#!/usr/bin/env python3
"""Сводка по курсу для проверки на полноту: что готово по карте README,
сколько в главах упражнений и из них практики, есть ли ответы и группа
тренажёра, что отметил ученик. Только читает файлы.

    python3 .claude/skills/course-audit/scripts/course_stats.py
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[4]
if not (ROOT / "README.md").exists():
    ROOT = pathlib.Path.cwd()


def read(name):
    p = ROOT / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


readme, answers, progress = read("README.md"), read("ANSWERS.md"), read("PROGRESS.md")
trainer = read("tools/trainer.html")

# группы тренажёра: ch:"3", ch:"13–15", ch:"П1"
groups = re.findall(r'\bch:"([^"]+)"', trainer)


def in_trainer(key):
    for ch in groups:
        if ch == key:
            return True
        m = re.fullmatch(r"(\d+)[–-](\d+)", ch)
        if m and not key.startswith("П") and int(m[1]) <= int(key) <= int(m[2]):
            return True
    return False


done = set(re.findall(r"^- \[x\] (П?\d+)\.", progress, re.M))

ROW = re.compile(r"^\|\s*(✅|🚧|⬜)\s*\|\s*\[?(П?\d+)\.\s*([^\]|]+?)(?:\]\(([^)]+)\))?\s*\|", re.M)
rows = []
for status, key, title, link in ROW.findall(readme):
    r = dict(status=status, key=key, title=title.strip(), lines=0, ex=0, prac=0,
             ans=False, tr=False, para=False, done=key in done)
    f = ROOT / link if link else None
    if f and f.exists():
        text = f.read_text(encoding="utf-8")
        r["lines"] = text.count("\n")
        ex = text.split("## Упражнения", 1)[1].split("\n## ", 1)[0] if "## Упражнения" in text else ""
        items = re.findall(r"^\*\*П?\d+\.\d+[а-я]?\.(?:\*\*|\s)(.*)$", ex, re.M)
        r["ex"], r["prac"] = len(items), sum("практика" in s for s in items)
        head = f"Приложение {key}" if key.startswith("П") else f"Глава {key}"
        r["ans"] = bool(re.search(rf"^## {head}\.", answers, re.M)) or not items
        r["tr"] = in_trainer(key)
        r["para"] = bool(re.search(r"[Тт]ренаж[её]р", text))
    rows.append(r)

yes = lambda b: "да" if b else "—"
print("| № | | Глава | Строк | Упр. | Практ. | Ответы | Тренажёр | Пройдено |")
print("|---|---|---|---|---|---|---|---|---|")
for r in rows:
    if r["status"] == "✅":
        print(f"| {r['key']} | ✅ | {r['title'][:40]} | {r['lines']} | {r['ex']} | {r['prac']} | "
              f"{yes(r['ans'])} | {yes(r['tr'] and r['para'])} | {yes(r['done'])} |")
    else:
        print(f"| {r['key']} | {r['status']} | {r['title'][:40]} | | | | | | |")

ready = [r for r in rows if r["status"] == "✅"]
print()
print(f"Готово по карте: {len(ready)} из {len(rows)}; строк в готовых: {sum(r['lines'] for r in ready)}")
print(f"Упражнений: {sum(r['ex'] for r in ready)}, из них с пометкой «практика»: {sum(r['prac'] for r in ready)}")
print("Не написаны:", ", ".join(r["key"] for r in rows if r["status"] != "✅") or "—")
gaps = [r["key"] for r in ready if not r["ans"]]
print("Готовы, но без ответов в ANSWERS.md:", ", ".join(gaps) or "—")
gaps = [r["key"] for r in ready if not (r["tr"] and r["para"])]
print("Готовы, но без тренажёра или абзаца о нём:", ", ".join(gaps) or "—")
print(f"Ученик отметил пройденными: {len(done)}" + (f" ({', '.join(sorted(done))})" if done else ""))
