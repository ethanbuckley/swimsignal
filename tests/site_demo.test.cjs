// The organisers' demonstration (demo.html, src/dipcast/site/demo.js): one invented activity centre's session on four real
// Windermere bathing waters, drawn with the sites view's and the spot page's own rules. The briefing carries
// scripts/briefing.py's words; the page says the tools are free, that paid terms are only being explored, and
// claims no customer.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const D = require('../src/dipcast/site/demo.js');
const S = require('../src/dipcast/site/sites.js');
const N = require('../src/dipcast/site/since.js');

const ROOT = path.join(__dirname, '..');
const GEN = '2026-11-05T06:10:00+00:00', PREV = '2026-11-05T00:20:00+00:00', NOW = Date.parse(GEN) + 3600e3;
const DAYS = ['2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09'];   // Thursday to Monday
const day = (date, label, risk, e) => ({date, label, risk, expected_spilling_overflows: e, p_ecoli_gt900: 0.05, in_validated_season: false, rain_48h_mm: 6});
const spot = (id, name, labels) => ({id, name, kind: 'lake', source: 'designated', location: {mode: 'lake'},
  now: {label: 'low', discharging_upstream: 0, monitored_upstream: 5}, upstream_summary: {overflows: 5},
  days: DAYS.map((d, i) => labels[i] === 'high' ? day(d, 'high', 0.5, 4) : day(d, 'low', 0.02, 0.2))});
const ALL = ['low', 'low', 'low', 'low', 'low'];
const DATA = {generated_at: GEN, commit: 'abc1234', spots: [
  spot('bw-ukd1203-45650', 'Windermere, Millerground Landing', ['low', 'low', 'high', 'low', 'low']),
  spot('bw-ukd1203-45675', 'Windermere, Rayrigg Meadow', ALL),
  spot('bw-ukd1203-45700', 'Windermere, Fellfoot', ALL),
]};   // Lakeside YMCA is left out, to show a venue the forecast no longer has
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/\s+/g, ' ');

test("the briefing's limits and who decides are scripts/briefing.py's, word for word", () => {
  const py = fs.readFileSync(path.join(ROOT, 'scripts', 'briefing.py'), 'utf8');
  const constant = name => [...py.match(new RegExp(`^${name} = \\(([\\s\\S]*?)\\)\\n`, 'm'))[1].matchAll(/"((?:[^"\\]|\\.)*)"/g)].map(m => m[1]).join('');
  assert.equal(D.LIMITS, constant('LIMITS'));
  assert.equal(D.DECIDES, constant('DECIDES'));
});

test("the session is on the forecast's first Saturday, else tomorrow, else today", () => {
  assert.equal(D.sessionDay(DATA), '2026-11-07');
  const noSat = {spots: [{id: 'bw-ukd1203-45650', days: [{date: '2026-11-02'}, {date: '2026-11-03'}, {date: '2026-11-04'}]}]};
  assert.equal(D.sessionDay(noSat), '2026-11-03');
  assert.equal(D.sessionDay({spots: [{id: 'bw-ukd1203-45650', days: [{date: '2026-11-02'}]}]}), '2026-11-02');
  assert.equal(D.sessionDay({spots: [{id: 'bw-ukd1203-45650', days: []}]}), null);
  assert.equal(D.draw({generated_at: GEN, spots: []}), null);
});

test('the briefing gives each venue its level on the session day, in the sites view\'s words, with a record for the centre', () => {
  const out = D.draw(DATA, null, NOW, 'https://swimsignal.co.uk/');
  const b = text(out.brief);
  assert.ok(b.includes('SwimSignal briefing for Example centre (invented for this demonstration): Saturday 7 November, 10:00'));
  assert.ok(b.includes(D.LIMITS) && b.includes('Example centre (invented for this demonstration) makes the decision about this session'));
  // The main spot first, then the backups, in VENUES's order; the level is dayWords's, the same as the sites view's row.
  const main = DATA.spots[0], w = S.dayWords(main, '2026-11-07');
  assert.equal(w.head, 'High risk on Sat 7 Nov');
  assert.ok(b.indexOf(`Main spot, Windermere, Millerground Landing: ${w.head}.`) >= 0);
  assert.ok(b.indexOf('Main spot') < b.indexOf('Backup spot, Windermere, Rayrigg Meadow') && b.indexOf('Rayrigg Meadow') < b.indexOf('Fellfoot'));
  assert.ok(b.includes('Backup spot: bw-ukd1203-45625 is not in this forecast.'));
  assert.ok(out.brief.includes('href="record.html#spot=bw-ukd1203-45650&amp;day=2026-11-07&amp;org=Example%20centre%20(invented%20for%20this%20demonstration)"'));
  assert.ok(out.brief.includes('Issue id <b>abc1234-20261105T0610Z</b>.'));
  // The sites view for the same day, inside the page: no print button of its own, the missing venue named.
  assert.ok(out.sites.includes('data-day="2026-11-07"') && !out.sites.includes('id="print"'));
  assert.ok(text(out.sites).includes('Not found in this forecast: bw-ukd1203-45625'));
  assert.ok(out.kept.includes('abc1234-20261105T0610Z') && out.kept.includes('href="sites.html#spots=bw-ukd1203-45650,bw-ukd1203-45675,bw-ukd1203-45700,bw-ukd1203-45625&amp;name=Example%20centre%2C%202026-11-07&amp;day=2026-11-07"'));
});

test('what changed is the spot page\'s comparison, and only against a file for this issue', () => {
  assert.ok(D.since(DATA, null, NOW).includes('could not be loaded'));
  assert.ok(D.since(DATA, {issued_at: PREV, spots: {}}, NOW).includes('from a different update'));
  // The previous issue had Millerground Landing low on Saturday; this one has it high. The others did not move.
  const was = {...DATA.spots[0], days: DATA.spots[0].days.map(d => d.date === '2026-11-07' ? day(d.date, 'low', 0.02, 0.2) : d)};
  const file = {issued_at: GEN, issue_id: 'abc1234-20261105T0610Z', previous: {issue_id: 'abc1234-20261105T0020Z', issued_at: PREV},
    spots: {'bw-ukd1203-45650': N.seenRecord(was, PREV, NOW), 'bw-ukd1203-45675': N.seenRecord(DATA.spots[1], PREV, NOW)}};
  const t = text(D.since(DATA, file, NOW));
  assert.match(t, /Windermere, Millerground Landing\. Since the update issued .*, 5 h 50 min before this one: Saturday: low risk then, high risk now\./);
  assert.match(t, /Windermere, Rayrigg Meadow\. Since the update .*: no level changed\./);
  assert.ok(t.includes('Windermere, Fellfoot. Since the update') && t.includes('this spot was not in that update'));
});

test('the page loads its scripts in order, says the tools are free today, and claims no customer', () => {
  const html = fs.readFileSync(path.join(ROOT, 'src', 'dipcast', 'site', 'demo.html'), 'utf8');
  const order = ['levels.js', 'experience.js', 'lists.js', 'organisers.js', 'printed.js', 'eatoday.js', 'since.js', 'sites.js', 'demo.js']
    .map(f => html.indexOf(`<script src="${f}"></script>`));
  assert.ok(order.every(i => i > 0) && order.every((i, k) => !k || i > order[k - 1]));
  const words = text(html);
  for (const say of ['Every tool on this page is free', 'No price is set. No organisation pays for SwimSignal or has agreed to.',
    'The public forecasts and everything for swimmers stay free, whatever is decided.', 'The activity centre is invented for the example.'])
    assert.ok(words.includes(say), say);
  assert.doesNotMatch(words, /\b(customers?|clients?|trusted by|used by)\b/i);
  for (const id of ['d-session', 'd-brief', 'd-sites', 'd-since', 'd-kept']) assert.ok(html.includes(`id="${id}"`), id);
});
