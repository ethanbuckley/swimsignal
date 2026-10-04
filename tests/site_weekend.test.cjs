// The weekend's words in the best-day line (levels.js, weekendWords; index.html, bestDayNote), with
// the forecast's own date fixed (setToday) on each kind of day: a Thursday, a Friday, a Saturday, a
// Sunday, a Tuesday (Saturday is the fifth day), and a Monday, whose five days reach no weekend.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');

const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const fiveFrom = iso => [0, 1, 2, 3, 4].map(k => addDays(iso, k));
// A spot with monitored overflows upstream, so its forecast changes from day to day, one level a day from `start`.
const spot = (start, labels) => ({upstream_summary: {overflows: 1}, location: {mode: 'lake'}, now: {label: labels[0]},
  days: labels.map((l, i) => ({date: addDays(start, i), label: l, risk: l === 'low' ? 0.01 : 0.5}))});
const clear = {days: [], upstream_summary: {overflows: 0}};   // no overflows: never counted, on any day
const at = (iso, f) => { L.setToday(iso); try { return f(fiveFrom(iso)); } finally { L.setToday(null); } };

test('on a Thursday the weekend is Saturday and Sunday, and the better one is named in full', () => {
  const thu = '2026-10-08';   //        Thu     Fri     Sat     Sun     Mon
  const spots = [spot(thu, ['high', 'high', 'low', 'high', 'low']),
                 spot(thu, ['high', 'high', 'low', 'low', 'low']),
                 spot(thu, ['high', 'high', 'high', 'high', 'low']), clear];
  at(thu, dates => {
    assert.equal(L.bestDay(spots, dates).date, '2026-10-12');   // Monday is the week's best
    assert.equal(L.weekendWords(spots, dates), 'Best this weekend: Saturday, 2 spots at low risk.');
    assert.equal(L.weekendWords(spots, dates, true), 'Best this weekend: Saturday, 2 of your 3 spots at low risk.');
  });
});
test('when the week’s best day is a weekend day, the weekend is not said again', () => {
  const thu = '2026-10-08';
  const spots = [spot(thu, ['high', 'high', 'low', 'high', 'high']), spot(thu, ['high', 'high', 'low', 'low', 'low'])];
  at(thu, dates => {
    assert.equal(L.bestDay(spots, dates).date, '2026-10-10');   // Saturday
    assert.equal(L.weekendWords(spots, dates), '');
    assert.equal(L.weekendWords(spots, dates, true), '');
  });
});
test('equal weekend days are said together, and none at low risk is said plainly', () => {
  const thu = '2026-10-08';
  const even = [spot(thu, ['high', 'high', 'low', 'low', 'low']), spot(thu, ['high', 'high', 'high', 'high', 'low'])];
  const none = [spot(thu, ['high', 'high', 'high', 'high', 'low']), spot(thu, ['high', 'high', 'high', 'high', 'high'])];
  at(thu, dates => {
    assert.equal(L.weekendWords(even, dates), 'This weekend: 1 spot at low risk on Saturday and Sunday.');
    assert.equal(L.weekendWords(none, dates), 'This weekend: no spots at low risk on Saturday or Sunday.');
    assert.equal(L.weekendWords(none, dates, true), 'This weekend: none of your 2 spots at low risk on Saturday or Sunday.');
  });
});
test('a weekend day with no level anywhere is left out, as the best day leaves it out', () => {
  const thu = '2026-10-08';
  const short = [spot(thu, ['high', 'low', 'high']), spot(thu, ['high', 'low', 'low'])];   // Thursday to Saturday only
  at(thu, dates => assert.equal(L.weekendWords(short, dates), 'This weekend: 1 spot at low risk on Saturday.'));
});
test('on a Friday Saturday is tomorrow', () => {
  const fri = '2026-10-09';   //        Fri     Sat     Sun     Mon     Tue
  const spots = [spot(fri, ['high', 'low', 'high', 'low', 'low']), spot(fri, ['high', 'high', 'low', 'low', 'low'])];
  at(fri, dates => assert.equal(L.weekendWords(spots, dates), 'This weekend: 1 spot at low risk tomorrow and Sunday.'));
  spots.push(spot(fri, ['high', 'low', 'high', 'low', 'low']));
  at(fri, dates => assert.equal(L.weekendWords(spots, dates), 'Best this weekend: tomorrow, 2 spots at low risk.'));
});
test('on a Saturday the weekend is today and tomorrow', () => {
  const sat = '2026-10-10';   //        Sat     Sun     Mon     Tue     Wed
  const spots = [spot(sat, ['high', 'low', 'high', 'low', 'high']),
                 spot(sat, ['low', 'low', 'high', 'low', 'high']),
                 spot(sat, ['high', 'high', 'high', 'low', 'high'])];
  at(sat, dates => {
    assert.equal(L.bestDay(spots, dates).date, '2026-10-13');   // Tuesday
    assert.equal(L.weekendWords(spots, dates), 'Best this weekend: tomorrow, 2 spots at low risk.');
  });
  const now = [spot(sat, ['low', 'high', 'high', 'high', 'high']), spot(sat, ['low', 'low', 'high', 'high', 'high'])];
  at(sat, dates => assert.equal(L.weekendWords(now, dates), ''));   // today is the week's best: said once
  const even = [spot(sat, ['low', 'low', 'low', 'low', 'high']), spot(sat, ['high', 'high', 'high', 'low', 'high'])];
  at(sat, dates => assert.equal(L.weekendWords(even, dates), 'This weekend: 1 spot at low risk today and tomorrow.'));
});
test('on a Sunday the weekend is today, which the list already shows, so nothing is added', () => {
  const sun = '2026-10-11';   //        Sun     Mon     Tue     Wed     Thu
  const spots = [spot(sun, ['low', 'low', 'high', 'high', 'high']), spot(sun, ['high', 'low', 'high', 'high', 'high'])];
  at(sun, dates => {
    assert.equal(L.bestDay(spots, dates).date, '2026-10-12');   // Monday is the week's best, and Sunday is in range
    assert.equal(L.weekendWords(spots, dates), '');
    assert.equal(L.weekendWords(spots, dates, true), '');
  });
  const now = [spot(sun, ['low', 'low', 'high', 'high', 'high']), spot(sun, ['low', 'high', 'high', 'high', 'high'])];
  at(sun, dates => assert.equal(L.weekendWords(now, dates), ''));   // today is the week's best
});
test('on a Tuesday the fifth day is Saturday, and Sunday is past the forecast', () => {
  const tue = '2026-10-13';   //        Tue     Wed     Thu     Fri     Sat
  const spots = [spot(tue, ['high', 'low', 'high', 'high', 'low']), spot(tue, ['high', 'low', 'high', 'high', 'high'])];
  at(tue, dates => assert.equal(L.weekendWords(spots, dates), 'This weekend: 1 spot at low risk on Saturday.'));
});
test('on a Monday the five days reach no weekend, and nothing is added', () => {
  const mon = '2026-10-12';   //        Mon     Tue     Wed     Thu     Fri
  const spots = [spot(mon, ['high', 'low', 'high', 'high', 'low']), spot(mon, ['high', 'low', 'low', 'high', 'high'])];
  at(mon, dates => {
    assert.equal(L.bestDay(spots, dates).date, '2026-10-13');
    assert.equal(L.weekendWords(spots, dates), '');
    assert.equal(L.weekendWords(spots, dates, true), '');
  });
  at(mon, dates => assert.equal(L.weekendWords([], dates), ''));
});

// ------------------------------------------------------------------------------ the page's line
// bestDayNote from index.html's script, run beside levels.js as in the browser (as site_planner does).
const pageSrc = (() => { const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function noteOn(iso) {
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8') + `\nsetToday("${iso}");`, ctx);
  vm.runInContext(pageDefs(['VIEW', 'dateLabel', 'bestDayNote']), ctx);
  return vm.runInContext('bestDayNote', ctx);
}
const text = html => html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
test('the list and the Saved page put the weekend first, so Show stays beside the best day', () => {
  const thu = '2026-10-08';
  const spots = [spot(thu, ['high', 'high', 'low', 'high', 'low']), spot(thu, ['high', 'high', 'low', 'low', 'low']),
                 spot(thu, ['high', 'high', 'high', 'high', 'low'])];
  const note = noteOn(thu);
  assert.equal(text(note(spots)), 'Best this weekend: Saturday, 2 spots at low risk. Lowest pollution risk this week: Monday · Show');
  assert.equal(text(note(spots, true)), 'Best this weekend: Saturday, 2 of your 3 spots at low risk. '
    + 'Lowest pollution risk this week: Monday, when 3 of your 3 spots are at low risk. Show');
  // The button still picks the day, and its label is the day picker's name for it, where the focus goes.
  assert.match(note(spots), /<button[^>]*data-pick-day="2026-10-12" aria-label="Show Mon 12 Oct">Show<\/button><\/span>$/);
  // No low day anywhere: the list says nothing of the best day, so nothing of the weekend either.
  assert.equal(note([spot(thu, ['high', 'high', 'high', 'high', 'high'])]), '');
});
test('the week’s best day is in words, lower case mid-sentence, on any day', () => {
  const mon = '2026-10-12';   // no weekend in range: only the best day's words changed
  assert.equal(text(noteOn(mon)([spot(mon, ['high', 'low', 'high', 'high', 'high'])])), 'Lowest pollution risk this week: tomorrow · Show');
  assert.equal(text(noteOn(mon)([spot(mon, ['low', 'high', 'high', 'high', 'high'])])), 'Lowest pollution risk this week: today · Show');
  const sun = '2026-10-11';   // a Sunday: nothing of the weekend
  const spots = [spot(sun, ['low', 'low', 'high', 'high', 'high']), spot(sun, ['high', 'low', 'high', 'high', 'high'])];
  assert.equal(text(noteOn(sun)(spots)), 'Lowest pollution risk this week: tomorrow · Show');
  assert.equal(text(noteOn(sun)(spots, true)), 'Lowest pollution risk this week: tomorrow, when 2 of your 2 spots are at low risk. Show');
  const sat = '2026-10-10';   // a Saturday: today and tomorrow, then a later day by its full name
  const sats = [spot(sat, ['high', 'low', 'high', 'low', 'high']), spot(sat, ['low', 'low', 'high', 'low', 'high']),
                spot(sat, ['high', 'high', 'high', 'low', 'high'])];
  assert.equal(text(noteOn(sat)(sats)), 'Best this weekend: tomorrow, 2 spots at low risk. Lowest pollution risk this week: Tuesday · Show');
});
