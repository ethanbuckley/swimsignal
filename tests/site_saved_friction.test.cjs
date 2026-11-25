// Saved and the swim journal, with less in the way (outside audit, 17 Nov 2026; docs/DESIGN.md "Saved and the journal,
// less in the way"). The parts a page needs are also checked in a real browser (tests/browser_smoke.mjs: one, empty,
// log-cancel).
// node --test tests/site_saved_friction.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const j = require('../src/dipcast/site/journal.js');
const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const TODAY = '2026-11-17';

test('1. a first look shows no "Since you last looked" tile: the places lead', () => {
  assert.match(page, /if \(sum && sum\.state !== 'none'\) v \+= `<section class="sec tile since-sum/);
  // The summary itself still says it, for anything that asks (since.js is unchanged).
  const S = require('../src/dipcast/site/since.js');
  assert.equal(S.sinceSummary([{ s: { id: 'a', name: 'A' }, prev: null, now: {} }]).state, 'none');
});

test('2. with nothing saved and one list, where saved spots are kept is said once, by the empty tile', () => {
  assert.match(page, /\+ \(!spots\.length && !many \? '' : `<p class="lede">/);
  assert.match(page, /Saved spots stay in this browser: nothing is sent to SwimSignal\./);
});

test('3. one saved spot: no line sending to the page its name already links to; the planner stays', () => {
  assert.ok(!page.includes('Its page has why'));
  const src = page.slice(page.indexOf('const savedOneNext ='), page.indexOf('function renderSaved()'));
  const ctx = vm.createContext({ esc: x => String(x), planPath: () => '/plan/', planHereHash: s => `#spot=${s.id}`, canPlanHere: () => true });
  vm.runInContext(src.replace('const savedOneNext', 'globalThis.savedOneNext'), ctx);
  assert.equal(ctx.savedOneNext({ id: 'thames-henley' }), '<p class="small saved-one-next">Going? <a href="/plan/#spot=thames-henley" data-plan-here>Plan a swim here</a>.</p>');
  ctx.canPlanHere = () => false;
  assert.equal(ctx.savedOneNext({ id: 'thames-henley' }), '', 'nothing at all where the planner cannot take it');
  // The card's name is the link to the spot's page.
  assert.match(page, /<a class="scard-link" href="\$\{esc\(iso && iso !== today\(\) && daily\(s\) \? spotPath\(s\.id\)/);
});

test('4. Cancel goes back to the control that opened the form, else "Log a swim", else nowhere', () => {
  const el = (connected = true) => ({ isConnected: connected });
  const here = el(), swam = el();
  assert.equal(j.jnBackTo(here, swam), here, '"Log a swim here" opened it');
  assert.equal(j.jnBackTo(swam, swam), swam);
  assert.equal(j.jnBackTo(el(false), swam), swam, 'the opener was redrawn away');
  assert.equal(j.jnBackTo(el(false), el(false)), null);
  const js = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/journal.js'), 'utf8');
  assert.match(js, /\$\('#jn-cancel'\)\.addEventListener\('click', \(\) => \{ close\(\); jnFocusBack\(jnBackTo\(from, b\)\); \}\);/);
  // "Log a swim here" opens the form as itself, so Cancel knows it; it falls back to pressing "Log a swim".
  assert.match(page, /journalLogFrom\(e\.currentTarget\)\)\) document\.getElementById\('swam'\)\.click\(\);/);
});

test('5. the form: day, note and photos first, the time and minutes after, the draft notice over the buttons', () => {
  const f = j.journalFormHtml(TODAY, '17:00');
  const at = s => { const i = f.indexOf(s); assert.ok(i >= 0, s); return i; };
  const order = ['id="jn-date"', 'id="jn-note"', 'id="jn-pick"', 'id="jn-time"', 'id="jn-min"', 'id="jn-kept-host"', 'data-draft-note', 'id="jn-cancel"'].map(at);
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  // Nothing stored is dropped: every field the journal keeps is still asked for, the time still filled in.
  for (const x of [`value="${TODAY}"`, 'value="17:00"', `maxlength="${j.JOURNAL_LIMITS.note}"`, `max="${j.JOURNAL_LIMITS.minutes}"`, 'Photos']) assert.ok(f.includes(x), x);
  assert.ok(f.includes('<b>Only on this device.</b>'));
  // draftTrack puts its notice in the form's place for it, or at the top of a form without one (the reviews', unchanged).
  const src = page.slice(page.indexOf('const DRAFTS ='), page.indexOf('// Words typed into a review'));
  const ctx = vm.createContext({ Event: class { constructor(t) { this.type = t; } } });
  vm.runInContext(src, ctx);
  const track = vm.runInContext('draftTrack', ctx);
  const form = host => { const got = []; return { got, id: 'jn-form', querySelectorAll: () => [], addEventListener: () => {},
    querySelector: q => (q === '[data-draft-note]' ? host : null), insertAdjacentHTML: (w, h) => got.push(['form', w, h]) }; };
  const host = { got: [], insertAdjacentHTML(w, h) { this.got.push(['host', w, h]); } };
  const withHost = form(host); track(withHost, 'a');
  assert.equal(withHost.got.length, 0); assert.equal(host.got[0][1], 'beforeend'); assert.match(host.got[0][2], /Unsent answers/);
  const without = form(null); track(without, 'b');
  assert.equal(without.got[0][1], 'afterbegin');
});

test('6. the copy comes before the swims, Delete all after them', () => {
  const list = j.journalEntries(Array.from({ length: 7 }, (_, i) => ({ id: 'a', date: `2026-09-0${i + 1}` })));
  const h = j.journalSection(list);
  const at = s => { const i = h.indexOf(s); assert.ok(i >= 0, s); return i; };
  assert.ok(at('Only on this device.') < at('id="jn-export"') && at('id="jn-export"') < at('id="jn-list"'));
  assert.ok(at('id="jn-import"') < at('id="jn-list"') && at('id="jn-said"') < at('id="jn-list"'), 'what Save a copy says is said beside it');
  assert.ok(at('id="jn-all"') < at('id="jn-clear"'), 'Delete all at the foot, after Show all');
  assert.ok(h.includes('Clearing this browser\'s data deletes the journal, so a copy is its backup.'));
  const js = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/journal.js'), 'utf8');
  assert.match(js, /row = sec\.querySelector\('#jn-clear-row'\)/, 'Delete all asks in its own row, not the copy\'s');
  const empty = j.journalSection([]);
  assert.ok(empty.includes('id="jn-import"') && !empty.includes('jn-clear') && !empty.includes('Clearing'));
});
