// A comparison opens on its answer on a phone (6 Nov 2026, item 5 of PR #633's audit). At 375 x 812 the three spot
// selects, the status line and the issue note put the first day's row at 660 to 745 px, against the tab bar at 748.
// The selects now fold under "Choose the spots" once two spots are chosen, and the row starts at 470 px (Saved) or
// 509 px (the planner). Wider screens keep the selects shown, with no line over them.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = page.slice(page.indexOf('<script>\n') + 9, page.lastIndexOf('</script>')).split('\n');
// Top-level definitions from index.html's script, as site_phone_wording.test.cjs takes them.
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
const spots = [{id: 'a', name: 'Grasmere'}, {id: 'b', name: 'Rydal Water'}, {id: 'c', name: 'Brothers Water'}];
function section(phone, ids) {
  const ctx = vm.createContext({PHONE: {matches: phone}, COMPARING: null});
  vm.runInContext(pageDefs(['esc', 'compareOffered', 'compareSection']), ctx);
  return vm.runInContext('compareSection', ctx)({title: 'Compare your spots', sub: 'Up to three.', groups: [['', spots]], ids, open: true});
}
const pickTag = html => html.match(/<details class="more compare-pick"[^>]*>/)[0];

test('the selects sit in a fold named "Choose the spots", before the status line and the table', () => {
  const html = section(true, ['a', 'b']);
  assert.match(html, /<details class="more compare-pick"[^>]*><summary>Choose the spots<\/summary><div class="compare-fields">(<label>Spot \d[^]*?<\/label>){3}<\/div><\/details><p class="small muted" id="compare-status" role="status"><\/p><div id="compare-result"><\/div><\/details>$/);
});
test('on a phone with two spots chosen the fold is closed; with fewer it is open, marked as opened for that', () => {
  assert.equal(pickTag(section(true, ['a', 'b'])), '<details class="more compare-pick">');
  assert.equal(pickTag(section(true, ['a', 'b', 'c'])), '<details class="more compare-pick">');
  assert.equal(pickTag(section(true, ['a'])), '<details class="more compare-pick" open data-auto="1">');
  assert.equal(pickTag(section(true, [])), '<details class="more compare-pick" open data-auto="1">');
});
test('wider than a phone the fold is always open, and its line is not drawn while open', () => {
  assert.equal(pickTag(section(false, ['a', 'b'])), '<details class="more compare-pick" open>');
  assert.equal(pickTag(section(false, [])), '<details class="more compare-pick" open>');
  // More specific than details.more > summary, which draws a fold's line as flex.
  assert.match(page, /@media \(min-width: 801px\) \{ details\[open\]\.compare-pick > summary \{ display:none; \} \}/);
});

// comparePick, run against a stand-in fold: what it does as spots are ticked, chosen and taken out.
function picker(phone, open, auto) {
  const pick = {open, dataset: auto ? {auto: '1'} : {}, inside: new Set(), contains(el) { return this.inside.has(el); }};
  const ctx = vm.createContext({PHONE: {matches: phone}, document: {querySelector: q => (q === '.compare-pick' ? pick : null)}});
  vm.runInContext(pageDefs(['comparePick']), ctx);
  return {pick, run: vm.runInContext('comparePick', ctx)};
}
test('the fold opens itself when fewer than two spots are chosen, and closes again on a phone once two are', () => {
  const {pick, run} = picker(true, false, false);
  run(1); assert.deepEqual([pick.open, pick.dataset.auto], [true, '1']);
  run(2); assert.deepEqual([pick.open, pick.dataset.auto], [false, undefined]);
});
test('a fold someone is using stays open: a change from its own selects, or one they opened', () => {
  const sel = {}, a = picker(true, true, true);
  a.pick.inside.add(sel);
  a.run(2, {target: sel}); assert.deepEqual([a.pick.open, a.pick.dataset.auto], [true, undefined]);
  a.run(3); assert.equal(a.pick.open, true);   // a later tick, or the redraw when a guide's file comes, leaves it open
  const b = picker(true, true, false);   // opened by its summary: not marked auto (bindComparison)
  b.run(2); assert.equal(b.pick.open, true);
  assert.match(page, /pick\.addEventListener\('click', \(\) => delete pick\.parentElement\.dataset\.auto\)/);
});
test('wider than a phone, it never closes the fold', () => {
  const {pick, run} = picker(false, true, true);
  run(2); assert.equal(pick.open, true);
});
test('drawComparison sets the fold after drawing, and is given the change that called it', () => {
  const fn = page.slice(page.indexOf('function drawComparison('), page.indexOf('function comparePin('));
  assert.match(fn, /^function drawComparison\(e\) \{/);
  assert.match(fn, /box\.innerHTML = spots\.length < 2 \? '' : compareTable\(spots, c\.day, c\.meta\);\n  comparePick\(spots\.length, e\);/);
  assert.match(page, /document\.querySelectorAll\('\[data-compare\]'\)\.forEach\(el => el\.addEventListener\('change', drawComparison\)\);/);
});
test('the issue time and the caveat stay above the table, outside the box that scrolls sideways', () => {
  const fn = page.slice(page.indexOf('function compareTable('), page.indexOf('function compareWater('));
  assert.match(fn, /return `<p class="small muted compare-note">Issued \$\{issued\(\)\} \(\$\{agoSpan\(\)\} ago\)\. A lower forecast level does not mean safe water: check the signs at the water\.<\/p>`\n    \+ pin \+ `<div class="compare-scroll"/);
});
