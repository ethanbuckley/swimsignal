// The note beside an overflow its company says it has upgraded or is upgrading (index.html, upgradeNote,
// from build_site.attach_upgrades and data/raw/overflow_upgrades.csv). Rows as Ilkley's list had them:
// Middleton, Low Mill Lane 179 and the Addingham 3xDWF overflow listed, Beamsley not.
// node --test tests/site_upgrade_notes.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const NOW = Date.parse('2026-10-24T12:00:00+01:00');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
class FixedDate extends Date { constructor(...a) { if (!a.length) super(NOW); else super(...a); } static now() { return NOW; } }

function page() {
  const ctx = vm.createContext({ Date: FixedDate, L: { circleMarker: () => ({ bindTooltip: () => ({ addTo() {} }) }) }, contribLayer: null });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8') + '\nsetToday("2026-10-24");', ctx);
  vm.runInContext(pageDefs(['esc', 'fmt', 'feedTime', 'endedOn', 'runningAtLastAnswer', 'statusText', 'colourFor', 'drawnStatus', 'sinceTime',
    'spillFor', 'statusSaid', 'glyph', 'ICON', 'PAGE_ID', 'upgradeDay', 'upgradeNote', 'overflowTile']), ctx);
  return ctx;
}
const text = h => h.replace(/<\/?a\b[^>]*>/g, '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;| /g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
const rowsOf = h => h.split(/<li[^>]*>/).slice(1).map(text);

const URL_ = 'https://www.yorkshirewater.com/about-us/what-we-do/making-yorkshire-brilliant/addingham-and-ilkley';
const up = extra => ({ company: 'Yorkshire Water', stage: 'upgrading', match: 'name', source_name: 'Middleton SPS CSO', url: URL_,
  checked: '2026-10-24', returns_to: 2025, ...extra });
const row = extra => ({ company: 'Yorkshire Water', receiving_watercourse: 'River Wharfe', lat: 53.93, lon: -1.82, status: 0, has_live: true,
  data_state: 'live', latest_event_start: '2026-03-30T20:00:00+00:00', latest_event_end: '2026-03-31T04:18:39+00:00', lta_spills: 36,
  snap_confidence: 'high', position_source: 'live', distance_km: 0.4, lake_distance_km: 0, travel_h: 0.0, weight: 0.998,
  p_spill_today: 0.05, p_spill_days: [0.05, 0.1, 0.2, 0.3, 0.1], now_contribution: 0, ...extra });
const middleton = row({ site_id: 'YWS00176', site_name: 'ILKLEY MIDDLETON/CSO', upgrade: up() });
const beamsley = row({ site_id: 'YWS01340', site_name: 'BEAMSLEY/STW', distance_km: 12, travel_h: 11.9, weight: 0.157 });
const lowMill = row({ site_id: 'YWS00191', site_name: 'LOW MILL LANE 179/CSO', distance_km: 7, travel_h: 6.9, weight: 0.105,
  latest_event_start: '2026-02-07T18:00:00+00:00', latest_event_end: '2026-02-07T21:27:00+00:00',
  upgrade: up({ match: 'shared name', source_name: 'Low Mill Lane CSO' }) });
const addingham = row({ site_id: 'YWS00144', site_name: 'ADDINGHAM/NO 1 SPS/PRELIMINARY TREATMENT-STW/3XDWF OVERFLOW', status: -1,
  distance_km: 6, travel_h: 5.7, weight: 0.812, latest_event_start: '2026-05-22T10:00:00+00:00', latest_event_end: '2026-05-22T12:27:05+00:00',
  upgrade: up({ match: 'shared name', source_name: 'Addingham SPS CSO' }) });

const UPGRADING = "Yorkshire Water says it is upgrading this overflow (its page, read 24 Oct 2026).";
const COUNTS = 'The forecast still uses its spill counts for 2020 to 2025, so it may overstate the risk from it.';

test('the note sits under the listed overflow only, with the source linked and the day it was read', () => {
  const h = vm.runInContext('overflowTile', page())({ id: 'x', contributors: [middleton, beamsley, lowMill, addingham] }, 16);
  const rows = rowsOf(h);
  assert.equal(rows.length, 4);
  assert.match(rows[0], /^Ilkley Middleton storm overflow/);
  assert.ok(rows[0].includes(`${UPGRADING} Its monitor has shown no discharge since 31 Mar. ${COUNTS}`), rows[0]);
  assert.match(rows[1], /^Beamsley/);
  assert.doesNotMatch(rows[1], /upgrad|overstate|no discharge since/, 'an overflow not in the file gets no note');
  assert.equal((h.match(/yorkshirewater\.com/g) || []).length, 3, 'one link per listed overflow');
  assert.ok(h.includes(`(<a href="${URL_}">its page</a>, read 24 Oct 2026)`));
  // The note is inside its own row's block, after the row's status line, not in another row.
  const li = h.split('<li').slice(1);
  assert.ok(li[0].indexOf('class="ov-meta">Yorkshire Water says') > li[0].indexOf('not discharging'));
  assert.doesNotMatch(li[1], /ov-meta">Yorkshire Water says/);
});

test('a name the company shares with another overflow nearby is said to be a match by name', () => {
  const rows = rowsOf(vm.runInContext('overflowTile', page())({ id: 'x', contributors: [lowMill] }, 1));
  assert.ok(rows[0].includes('Yorkshire Water says it is upgrading its Low Mill Lane CSO, a name that could also mean another overflow nearby '
    + '(its page, read 24 Oct 2026). Its monitor has shown no discharge since 7 Feb. ' + COUNTS), rows[0]);
});

test('no "no discharge since" unless the live feed says "not discharging" now', () => {
  const ctx = page(), note = c => text(vm.runInContext('upgradeNote', ctx)(c));
  // Addingham 3xDWF's monitor was offline on 21 Oct 2026: silence from it is not a quiet overflow.
  assert.equal(note(addingham), 'Yorkshire Water says it is upgrading its Addingham SPS CSO, a name that could also mean another overflow nearby '
    + `(its page, read 24 Oct 2026). ${COUNTS}`);
  assert.doesNotMatch(note({ ...middleton, data_state: 'stale' }), /no discharge/);   // a frozen feed
  assert.doesNotMatch(note({ ...middleton, status: 1, latest_event_start: '2026-10-24T08:00:00+00:00' }), /no discharge/);
  assert.doesNotMatch(note({ ...middleton, latest_event_end: null }), /no discharge/);   // no date to give
  assert.doesNotMatch(note({ ...middleton, latest_event_start: '2026-04-02T00:00:00+00:00' }), /no discharge/);   // a later start not ended
});

test('the verb follows the source: "has upgraded" with its finish date only when the source says it is done', () => {
  const ctx = page(), note = c => text(vm.runInContext('upgradeNote', ctx)(c));
  assert.match(note({ ...middleton, upgrade: up({ stage: 'upgraded', completed: '2026-07-31' }) }),
    /^Yorkshire Water says it has upgraded this overflow, finished 31 Jul 2026 \(its page, read 24 Oct 2026\)\./);
  assert.match(note({ ...middleton, upgrade: up({ completed: '2026-07-31' }) }), /^Yorkshire Water says it is upgrading this overflow \(its page/);
  // Without the return year, the counts are not dated.
  assert.match(note({ ...middleton, upgrade: up({ returns_to: undefined }) }), /The forecast still uses its past spill counts, so it may overstate the risk from it\.$/);
});

test('no note without an upgrade, or with a source that is not https; names are escaped', () => {
  const ctx = page(), note = c => vm.runInContext('upgradeNote', ctx)(c);
  assert.equal(note(beamsley), '');
  assert.equal(note({ ...middleton, upgrade: up({ url: 'javascript:alert(1)' }) }), '');
  assert.match(note({ ...lowMill, upgrade: up({ match: 'shared name', source_name: '<b>X</b>' }) }), /its &lt;b&gt;X&lt;\/b&gt;, a name/);
});

test('the note is plain sentences in the list\'s own style: no box, pill or label of its own', () => {
  const n = vm.runInContext('upgradeNote', page())(middleton);
  assert.match(n, /^<div class="ov-meta">[^<]*<a href="[^"]+">its page<\/a>[^<]*<\/div>$/);
});
