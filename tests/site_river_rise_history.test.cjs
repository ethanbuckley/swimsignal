// The River level tile's history line (index.html, riseHistoryLine and riverTile; build_site.attach_rise_history;
// docs/RIVER-RISE-HISTORY-CONTRACT-v1.md), run in Node beside levels.js as in the browser: a river spot whose tile shows
// a gauge of the history says, for the device's month, how often an hour there was followed by a quick rise in that
// month of 2024 to 2026, in words; nothing for a month the export leaves out, a spot with no history, or a lake.
// On its own: node --test tests/site_river_rise_history.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

// Top-level definitions taken from index.html's script, as site_water_temp.test.cjs takes them.
const pageSrc = (() => { const html = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(join(__dirname, '../src/dipcast/site/levels.js'), 'utf8'), ctx);
vm.runInContext(pageDefs(['esc', 'fmt', 'glyph', 'ICON', 'rangeBar', 'RISE_MONTHS', 'riseOneIn', 'riseHistoryLine', 'RISE_MORE', 'riverTile']), ctx);
const [riverTile, riseHistoryLine, setToday] = ['riverTile', 'riseHistoryLine', 'setToday'].map(n => vm.runInContext(n, ctx));

// Ilkley on the Wharfe (bw-uke4100-08901), as attach_rise_history writes it from the committed export: November
// 929 hours, 12 followed by a quick rise, 4 rises; December 1,429, 37 and 13; April 1,438 and none. Months the
// display rule leaves out are null (here July, as if it had too few hours).
const months = Array(12).fill(null);
months[3] = { hours: 1438, rise_hours: 0, rises: 0, years: [2025, 2026] };
months[5] = { hours: 1409, rise_hours: 22, rises: 8, years: [2025, 2026] };
months[10] = { hours: 929, rise_hours: 12, rises: 4, years: [2024, 2025] };
months[11] = { hours: 1429, rise_hours: 37, rises: 13, years: [2024, 2025] };
const ilkley = { gauge: 'F1902', station: 'Ilkley', river: 'River Wharfe', period: { first: '2024-11-21', last: '2026-10-24' }, months };
const reading = { station: 'Ilkley', river: 'River Wharfe', level_m: 0.41, typical_low_m: 0.09, typical_high_m: 1.8, label: 'normal',
  observed_at: '2026-11-06T10:00:00Z', distance_km: 0.4, same_river: true, measure: 'F1902-level-stage-i-15_min-m', stale: false };
const FORBIDDEN = /forecast(?!:)|warn|danger|unsafe|safe|risk|will rise|expect|likely|chance/i;

test('one spot in two months: the month and its years, how often, and the rises behind it', () => {
  setToday('2026-11-06');
  const nov = riverTile(reading, ilkley), plain = riverTile(reading);
  assert.match(plain.say, /^Not part of the pollution level\. Gauge at Ilkley on the River Wharfe, 0\.4&nbsp;km away, [^.]+\.$/);
  assert.equal(nov.say, plain.say + ' In November 2024 and 2025, about 1 hour in 80 at this gauge was '
    + 'followed within 3&nbsp;hours by a rise of more than a fifth of its usual range (4 rises in all).');
  setToday('2026-12-14');
  assert.equal(riseHistoryLine(ilkley), 'In December 2024 and 2025, about 1 hour in 40 at this gauge was followed within '
    + '3&nbsp;hours by a rise of more than a fifth of its usual range (13 rises in all).');
  assert.match(riverTile(reading, ilkley).say, /In December 2024 and 2025, about 1 hour in 40 /);
  setToday(null);
});

test('the line is history: no forecast, warning or safety words, no colour, and the figure and word stay the level\'s', () => {
  for (const iso of ['2026-11-06', '2026-12-14', '2027-04-02', '2027-06-20']) {
    setToday(iso);
    const t = riverTile(reading, ilkley), plain = riverTile(reading);
    const line = t.say.slice(plain.say.length);
    assert.ok(line.length > 0, iso);
    assert.doesNotMatch(line, FORBIDDEN, iso);
    assert.doesNotMatch(line, /<(?!\/?[a-z]+&)|class=|style=/, iso);   // words only: no element, class or colour
    assert.equal(t.fig, plain.fig); assert.equal(t.word, plain.word); assert.equal(t.wordTone, plain.wordTone); assert.equal(t.vis, plain.vis);
    assert.match(t.more, /not already high or rising fast/);
    assert.match(t.more, /It is history, not a forecast: <a href="research\.html#river-rises">/);
  }
  setToday('2027-04-02');
  assert.equal(riseHistoryLine(ilkley), 'In April 2025 and 2026, no hour at this gauge was followed within 3&nbsp;hours by a rise of more than a fifth of its usual range.');
  setToday('2027-06-20');
  assert.match(riseHistoryLine(ilkley), /^In June 2025 and 2026, about 1 hour in 60 at this gauge/);   // 1,409 / 22 = 64: tens past 20
  setToday(null);
});

test('nothing for a month the export leaves out, a spot with no history, or a lake', () => {
  setToday('2027-07-10');   // July is null: too few hours, or one year only
  assert.equal(riseHistoryLine(ilkley), '');
  assert.equal(riverTile(reading, ilkley).say, riverTile(reading).say);
  assert.equal(riverTile(reading, ilkley).more, riverTile(reading).more);
  setToday('2026-11-06');
  for (const h of [null, undefined, {}, { months: [] }, { months: Array(12).fill(null) }]) {
    assert.equal(riseHistoryLine(h), '');
    assert.equal(riverTile(reading, h).say, riverTile(reading).say);
  }
  // A month with one year only, or no hours, is never worded, even if a file carried it.
  const one = { months: Array(12).fill(null) };
  one.months[10] = { hours: 900, rise_hours: 3, rises: 1, years: null };
  assert.equal(riseHistoryLine(one), '');
  one.months[10] = { hours: 0, rise_hours: 0, rises: 0, years: [2024, 2025] };
  assert.equal(riseHistoryLine(one), '');
  // A lake's own gauge says no river history.
  assert.doesNotMatch(riverTile({ ...reading, water: 'lake' }, ilkley).say, /In November/);
  setToday(null);
});

test('an old reading keeps the history line: it does not depend on the level now', () => {
  setToday('2026-11-06');
  const t = riverTile({ ...reading, stale: true, level_m: null, age_hours: 30 }, ilkley);
  assert.equal(t.fig, '–');
  assert.match(t.say, /not shown as current\. Not part of the pollution level\. Gauge at Ilkley .*\. In November 2024 and 2025, about 1 hour in 80 /);
  setToday(null);
});

test('the tile list passes the spot\'s history to the River level tile', () => {
  assert.ok(pageSrc.some(l => l.includes('riverTile(d.river_state, d.rise_history)')));
});
