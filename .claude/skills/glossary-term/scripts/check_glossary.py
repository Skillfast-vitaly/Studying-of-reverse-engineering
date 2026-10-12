#!/usr/bin/env python3
"""Проверка словаря по правилу «один термин — одно введение».

    python3 .claude/skills/glossary-term/scripts/check_glossary.py [--all]

1. Термин записан в GLOSSARY.md дважды — с каким переводом каждый раз.
2. Запись словаря без произношения `[…]`.
3. Термины, которые главы вводят с произношением (**term** `[…]`),
   а в словаре их нет. По умолчанию первые 40, с --all — все.
Разный перевод одного термина — повод посмотреть глазами: омонимы
(flag — флаг процессора и флаг CTF) законны, а «летучий» и «изменчивый»
для volatile — нет.
"""
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
if not (ROOT / "GLOSSARY.md").exists():
    ROOT = pathlib.Path.cwd()
show_all = "--all" in sys.argv

gloss = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
norm = lambda t: re.sub(r"\s+", " ", t.strip().strip("`").lower())

entries = collections.defaultdict(list)   # термин → [(строка, раздел, перевод)]
no_pron, section, known = [], "", set()
for n, line in enumerate(gloss.splitlines(), 1):
    if line.startswith("## "):
        section = line[3:].strip()
        continue
    if not line.startswith("**"):
        continue
    head, sep, tail = line.partition(" — ")
    bold = re.findall(r"\*\*([^*]+)\*\*", head)
    if not bold:
        continue
    if "`[" not in head:
        no_pron.append((n, bold[0]))
    # «opcode (operation code)», «cross-reference, XREF», «kernel mode / user mode» —
    # в одной записи несколько написаний одного или пары терминов
    terms = [x for b in bold for x in re.split(r"\s*(?:/|,|\(|\))\s*", b) if x.strip()]
    entries[norm(terms[0])].append((n, section, tail.strip()))   # главное написание записи
    known.update(norm(t) for t in terms)                          # все написания — «уже есть»

# слова из таблицы «Слова из интерфейса инструментов»: | Undo | `[андý]` | Отменить |
for line in gloss.splitlines():
    m = re.match(r"\|\s*([A-Za-z][^|]*?)\s*\|\s*`\[", line)
    if m:
        known.add(norm(m.group(1)))

def is_known(t):
    """Есть ли термин в словаре — с поправкой на множественное число
    («writeups» при записи «writeup») и на «Process IDentifier» при записи
    «PID (Process IDentifier)»."""
    if t in known:
        return True
    for v in (t[:-1] if t.endswith("s") else None, t[:-2] if t.endswith("es") else None):
        if v and v in known:
            return True
    return any(t in k for k in known if len(t) > 6)

conflicts = 0
dups = {t: v for t, v in entries.items() if len(v) > 1}
print(f"Записей в словаре: {sum(len(v) for v in entries.values())}, написаний терминов: {len(known)}")
if dups:
    print(f"\nЗаписаны больше одного раза: {len(dups)}")
    for t, v in sorted(dups.items()):
        # сравниваем первое слово перевода: «флаг» и «флаг (второе значение)» — один перевод
        translations = {(re.findall(r"[а-яёa-z]+", x[2].lower()) or [""])[0] for x in v if x[2]}
        mark = "проверь: разный перевод" if len(translations) > 1 else "повтор"
        conflicts += len(translations) > 1
        print(f"  [{mark}] {t}: " + "; ".join(f"стр. {n} ({s}) — {tr[:50]}" for n, s, tr in v))
if no_pron:
    print(f"\nБез произношения: {len(no_pron)}")
    for n, t in no_pron:
        print(f"  стр. {n}: {t}")

# термины, введённые в главах с произношением
INTRO = re.compile(r"(?:\*\*)?\b([A-Za-z][A-Za-z0-9 .+#/'-]{1,40}?)(?:\*\*)?\s*`\[[^\]`]+\]`")
missing = collections.OrderedDict()
for f in sorted((ROOT / "course").glob("*.md")):
    text = re.sub(r"```.*?```", "", f.read_text(encoding="utf-8"), flags=re.S)
    for m in INTRO.finditer(text):
        t = norm(m.group(1))
        if len(t) < 2 or is_known(t) or t in missing:
            continue
        missing[t] = f.name
if missing:
    items = list(missing.items())
    print(f"\nВведены в главах, но нет в словаре: {len(items)}"
          + ("" if show_all or len(items) <= 40 else " (первые 40, все — с --all)"))
    for t, f in items if show_all else items[:40]:
        print(f"  {t}  ← {f}")

# произношение — русскими буквами (ударение — á, é, ó, ú…). Знаки МФА вроде «ə»
# ученик с A2 не прочитает: 12.10.2026 так нашлись [кəмáнд] и [кəмпóунент].
IPA = re.compile(r"[əɪʊɔʌæθðʃʒŋɑɛɜː]")
ipa = []
for f in [ROOT / "GLOSSARY.md"] + sorted((ROOT / "course").glob("*.md")):
    for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        for m in re.finditer(r"`\[([^\]`]+)\]`", line):
            if IPA.search(m.group(1)):
                ipa.append(f"{f.name}:{n}: [{m.group(1)}]")
if ipa:
    print(f"\nЗнаки МФА в произношении (пиши русскими буквами): {len(ipa)}")
    for x in ipa:
        print("  " + x)

print("\nИтог:", f"записей с разным переводом одного термина: {conflicts} — посмотри глазами "
      "(омонимы вроде flag или PE законны)" if conflicts else "разных переводов одного термина нет")
