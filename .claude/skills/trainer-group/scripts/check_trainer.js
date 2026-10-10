#!/usr/bin/env node
// Прогон всех генераторов тренажёра перед публикацией.
//
//   node .claude/skills/trainer-group/scripts/check_trainer.js [tools/trainer.html]
//        [--n 300] [--mode имя] [--seed число] [--timeout мс]
//
// Каждый режим генерирует N вопросов внутри vm с тайм-аутом: зависший
// генератор (однажды так и было — цикл добора вариантов) ловится, а не
// вешает прогон. Проверяется, что правильный ответ среди вариантов,
// варианты не повторяются, разбор why есть, свободный ответ right
// проходит собственную проверку check, все режимы из GROUPS существуют,
// а у каждой главы курса есть группа. Код выхода 1 — есть ошибки.
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');

let file = 'tools/trainer.html', N = 300, only = null, TIMEOUT = 3000;
let seed = (Date.now() ^ (process.pid << 8)) >>> 0;
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--n') N = +argv[++i];
  else if (a === '--mode') only = argv[++i];
  else if (a === '--seed') seed = (+argv[++i]) >>> 0;
  else if (a === '--timeout') TIMEOUT = +argv[++i];
  else file = a;
}

const errors = [], warns = [];
const err = (m) => errors.push(m), warn = (m) => warns.push(m);

const html = fs.readFileSync(file, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
if (!scripts.length) { console.error('В файле нет встроенного <script>.'); process.exit(2); }
let src = scripts[scripts.length - 1];

// Крючок: перед движком (он трогает DOM) отдать MODES и GROUPS наружу и выйти
// из обёртки (function(){ ... })(). Движок помечен комментарием «движок».
const hook = 'globalThis.__T = { MODES: MODES, GROUPS: GROUPS }; return;\n';
let at = src.search(/\/\*[^*]*движок[^*]*\*\//);
if (at < 0) at = src.search(/\bvar\s+cur\s*=/);
if (at < 0) {
  console.error('Не нашёл начало движка (комментарий «движок» или «var cur =»). ' +
    'Если движок переименовали, поправь поиск крючка в этом скрипте.');
  process.exit(2);
}
src = src.slice(0, at) + hook + src.slice(at);

// Воспроизводимый Math.random: при ошибке печатаем seed, чтобы повторить прогон.
const prng = `(function(s){ Math.random = function(){
  s |= 0; s = s + 0x6D2B79F5 | 0; var t = Math.imul(s ^ s >>> 15, 1 | s);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; })(${seed});`;

const stub = { getElementById: () => null, createElement: () => ({}), addEventListener() {} };
const ctx = vm.createContext({ console, document: stub, localStorage: { getItem: () => null, setItem() {} } });
try {
  vm.runInContext(prng, ctx);
  vm.runInContext(src, ctx, { timeout: TIMEOUT, filename: path.basename(file) });
} catch (e) {
  console.error('Скрипт тренажёра упал ещё до прогона: ' + e.message);
  process.exit(1);
}
const T = ctx.__T;
if (!T || !T.MODES || !T.GROUPS) { console.error('Не удалось достать MODES и GROUPS.'); process.exit(2); }
const MODES = T.MODES, GROUPS = T.GROUPS;

const strip = (s) => String(s).replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const KINDS = new Set(['text', 'code', 'asm']);

// ---- проверка одного вопроса (вызывается изнутри vm, тайм-аут действует) ----
const found = new Map();  // «режим|вид ошибки» → {msg, sample, count}: одна строка на вид ошибки
const stat = {};          // режим → {n, opt, free, sizes:{}}
function once(mode, key, msg, sample) {
  const k = mode + '|' + key, f = found.get(k);
  if (f) { f.count++; return; }
  found.set(k, { msg: `[${mode}] ${msg}`, sample: sample === undefined ? '' : strip(sample).slice(0, 120), count: 1 });
}
ctx.__validate = function (mode, t) {
  const s = (stat[mode] = stat[mode] || { n: 0, opt: 0, free: 0, sizes: {} });
  s.n++;
  if (!t || typeof t !== 'object') return once(mode, 'obj', 'make() вернул не объект');
  const sample = t.value !== undefined ? t.value : t.prompt;
  if (!t.prompt || !strip(t.prompt)) once(mode, 'prompt', 'пустой prompt', sample);
  if (t.value === undefined || t.value === null) once(mode, 'value', 'нет value', sample);
  if (t.kind !== undefined && !KINDS.has(t.kind)) once(mode, 'kind', `неизвестный kind «${t.kind}» (движок знает text, code, asm)`, sample);
  if (t.options) {
    s.opt++;
    const o = t.options;
    if (!Array.isArray(o) || o.length < 2) return once(mode, 'few', 'вариантов меньше двух', sample);
    s.sizes[o.length] = (s.sizes[o.length] || 0) + 1;
    if (!Number.isInteger(t.answer) || t.answer < 0 || t.answer >= o.length)
      once(mode, 'answer', `answer=${t.answer} — правильного ответа нет среди вариантов`, sample);
    const texts = o.map(strip);
    if (texts.some((x) => !x)) once(mode, 'empty', 'пустой вариант ответа', sample);
    if (new Set(texts).size !== texts.length) once(mode, 'dup', 'одинаковые варианты: ' + texts.join(' | ').slice(0, 120), sample);
    if (typeof t.why !== 'string' || !strip(t.why)) once(mode, 'why', 'нет разбора why (строка)', sample);
  } else {
    s.free++;
    if (typeof t.check !== 'function') return once(mode, 'check', 'нет ни options, ни check()', sample);
    if (t.right === undefined || !strip(t.right)) once(mode, 'right', 'нет правильного ответа right', sample);
    else {
      let ok = false;
      try { ok = t.check(strip(t.right)); } catch (e) { once(mode, 'checkthrow', 'check() падает: ' + e.message, sample); }
      if (!ok) once(mode, 'selfcheck', `правильный ответ «${strip(t.right)}» не проходит собственную check()`, sample);
    }
    if (typeof t.why !== 'function') once(mode, 'whyfn', 'why должен быть функцией у вопроса со свободным ответом', sample);
    else {
      try { if (!strip(t.why() || '')) once(mode, 'whyempty', 'why() вернул пустой разбор', sample); }
      catch (e) { once(mode, 'whythrow', 'why() падает: ' + e.message, sample); }
    }
  }
};

// ---- GROUPS и режимы ----
const ids = new Set(), chs = new Set(), inGroups = new Set();
for (const g of GROUPS) {
  if (ids.has(g.id)) err(`группа ${g.id} повторяется`);
  ids.add(g.id);
  if (chs.has(g.ch)) err(`две группы с кнопкой «${g.ch}»`);
  chs.add(g.ch);
  for (const m of g.modes || []) {
    inGroups.add(m);
    if (!MODES[m]) err(`группа ${g.id}: режима «${m}» нет в MODES`);
  }
  if (g.mix) inGroups.add(g.mix);
}
for (const m of Object.keys(MODES)) {
  if (!inGroups.has(m) && m !== 'exam') warn(`режим «${m}» не входит ни в одну группу — в тренажёре его не видно`);
  if (!MODES[m].label) err(`у режима «${m}» нет label`);
}

// ---- у каждой главы курса есть кнопка ----
const courseDir = path.resolve(path.dirname(file), '..', 'course');
function covers(ch, key) {                      // ch: «3», «13–15», «П1», «все»
  if (/^П\d+$/.test(ch)) return ch === key;
  const m = ch.match(/^(\d+)(?:[–-](\d+))?$/);
  if (!m || /^П/.test(key)) return false;
  const a = +m[1], b = m[2] ? +m[2] : a, k = +key;
  return k >= a && k <= b;
}
if (fs.existsSync(courseDir)) {
  for (const f of fs.readdirSync(courseDir).filter((x) => x.endsWith('.md')).sort()) {
    const mm = f.match(/^(\d\d)-/), pp = f.match(/^p(\d+)-/);
    const key = mm ? String(+mm[1]) : pp ? 'П' + pp[1] : null;
    if (key === null) continue;
    if (!GROUPS.some((g) => covers(g.ch, key))) err(`глава ${key} (${f}): нет группы в GROUPS`);
    const text = fs.readFileSync(path.join(courseDir, f), 'utf8');
    if (!/[Тт]ренаж[её]р/.test(text)) warn(`глава ${key} (${f}): в тексте нет абзаца «Тренажёр»`);
  }
}

// ---- прогон генераторов ----
const list = only ? [only] : Object.keys(MODES).filter((m) => m !== 'exam' && !GROUPS.some((g) => g.mix === m));
if (only && !MODES[only]) { console.error(`Режима «${only}» нет.`); process.exit(2); }
const t0 = Date.now();
for (const m of list) {
  try {
    vm.runInContext(`(function(name, n){ var M = __T.MODES[name];
      for (var i = 0; i < n; i++) __validate(name, M.make()); })(${JSON.stringify(m)}, ${N})`,
      ctx, { timeout: TIMEOUT });
  } catch (e) {
    if (/timed out/i.test(e.message)) err(`[${m}] завис дольше ${TIMEOUT} мс на ${N} вопросов — похоже на бесконечный цикл`);
    else err(`[${m}] make() падает: ${e.message}`);
  }
}
// смешанные режимы и экзамен — коротко, они собраны из уже проверенных
for (const m of Object.keys(MODES).filter((m) => m === 'exam' || GROUPS.some((g) => g.mix === m))) {
  if (only) break;
  try { vm.runInContext(`(function(){ for (var i = 0; i < 50; i++) __validate(${JSON.stringify(m)}, __T.MODES[${JSON.stringify(m)}].make()); })()`, ctx, { timeout: TIMEOUT }); }
  catch (e) { err(`[${m}] ${/timed out/i.test(e.message) ? 'завис' : 'падает: ' + e.message}`); }
}

for (const f of found.values())
  err(f.msg + (f.count > 1 ? ` (таких вопросов: ${f.count})` : '') + (f.sample ? `\n        например: ${f.sample}` : ''));
const total = Object.values(stat).reduce((a, s) => a + s.n, 0);
const few = Object.entries(stat).filter(([m, s]) => m !== 'exam' && !GROUPS.some((g) => g.mix === m) && Object.keys(s.sizes).some((k) => +k < 4)).map(([m]) => m);
console.log(`Тренажёр: ${file}`);
console.log(`Групп: ${GROUPS.length}, режимов: ${Object.keys(MODES).length}, вопросов прогнано: ${total} за ${Date.now() - t0} мс (seed ${seed})`);
if (few.length) warns.push(`меньше четырёх вариантов бывает в режимах: ${few.join(', ')} (нормально для «да/нет», иначе добери через fill4)`);
for (const w of warns) console.log('  предупреждение: ' + w);
if (errors.length) {
  console.log(`\nОшибок: ${errors.length}`);
  for (const e of errors) console.log('  ОШИБКА ' + e);
  console.log(`\nПовторить этот же прогон: --seed ${seed}`);
  process.exit(1);
}
console.log('Ошибок нет.');
