// Acceptance check, 28 Oct 2026: one official notice said the same way on every surface. For each kind of notice
// (one its reviewer marked as restricting swimming, one marked not restricting, and one from a spots.json before
// the field), each surface must:
//  - show the notice's own reviewed words (eatoday.js, eaTodayBrief, or its full line on the spot's page);
//  - say "advice" or "Follow" only for the restricting one, and "against swimming" never, unless the notice's own
//    line says so;
//  - keep the level as it is.
// Surfaces: discovery (search and list rows), the map (ring, tooltip, key, small map), Saved and list cards, the
// spot's page, Plan a swim and the shared outing (spot and backup), the share picture, the calendar file, the
// embed, the sites view, the organisers' page, the record, Saved's "since you looked" and the outing's watch.
// Server texts (cards, feeds, alerts.json, the push Worker) are checked in tests/test_cards.py, tests/test_feeds.py
// and push/test/official.test.js. node --test tests/site_notice_acceptance.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const ea = require('../src/dipcast/site/eatoday.js');
const O = require('../src/dipcast/site/outing.js');
const S = require('../src/dipcast/site/since.js');
const W = require('../src/dipcast/site/outingwatch.js');
const Embed = require('../src/dipcast/site/embed.js');
const Sites = require('../src/dipcast/site/sites.js');
const Org = require('../src/dipcast/site/organisers.js');
const Rec = require('../src/dipcast/site/record.js');
const X = require('../src/dipcast/site/experience.js');

const SITE = join(__dirname, '../src/dipcast/site');
const PAGE = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
const DATES = ['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31', '2026-11-01'];
L.setToday(DATES[0]);
const DATA = { generated_at: '2026-10-28T08:00:00Z', spots: [] }, NOW = Date.parse('2026-10-28T08:30:00Z');
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const AGAINST = { line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked' };
const STATUS = { line: 'City of London: swimming status notice (members only this week) since 20 Oct 2026', publisher: 'City of London',
  link: 'https://www.cityoflondon.gov.uk/', since: '2026-10-20', checked: '2026-10-26', state: 'checked' };
const spot = (id, name, official, extra = {}) => ({ id, name, kind: 'lake', source: 'designated', lat: 51.15, lon: -0.79, area: 'Surrey',
  classification: { class: 'excellent', year: 2025, url: PROFILE }, upstream_summary: { overflows: 2 }, assumptions: { max_upstream_km: 15 },
  location: { mode: 'lake' }, now: { label: 'low', discharging_upstream: 0 }, contributors: [], official,
  days: DATES.map(date => ({ date, risk: 0.01, label: 'low', expected_spilling_overflows: 0, rain_48h_mm: 1, p_ecoli_gt900: 0.02, in_validated_season: false })), ...extra });
const KINDS = [
  ['restricting', () => spot('r', 'Frensham Great Pond', [{ ...AGAINST, restricts: true }])],
  ['neutral', () => spot('n', 'Hampstead Mixed Pond', [{ ...STATUS, restricts: false }], { source: 'curated', classification: null })],
  ['legacy', () => spot('l', 'Legacy Pond', [{ ...AGAINST }])],   // no field: says the EA's words, asks nothing stronger than "read"
];
// What a surface may say for a kind: the restricting notice may ask to follow; the others never use "Official
// advice", "Follow", "follow it" or "against swimming" in the surface's own words. The notice's own brief may say
// "advice against bathing" (the EA's words), so it is taken out before the check.
function says(kind, text, brief) {
  const own = text.split(brief).join('').split(brief.replace(/&/g, '&amp;')).join('');
  if (kind === 'restricting') return;
  assert.doesNotMatch(own, /Official advice|\bFollow\b|follow it|against swimming/, `${kind}: ${own}`);
}

test('every list-like surface shows the shared tag, the notice\'s own words and no verb', () => {
  // Search and list rows, Saved cards, Plan a swim's rows, Nearby, the comparison's heads and the outing's columns
  // all draw eatoday.js's tag and nothing else for the notice.
  for (const [name, re] of [['search and list rows', /function spotItem[\s\S]*?eaTodayTag\(s\)/], ['Saved cards', /function savedCard[\s\S]*?eaTodayTag\(s, 'p'\)/],
    ['Nearby', /function nearby[\s\S]*?eaTodayTag\(s\)/], ['the comparison', /eaTodayTag\(s\) : ''\}`/],
    ['Plan a swim rows', /eaTodayTag\(s\) : ''\}<span class="hl \$\{tone\(o\.level\)\}">\$\{dayHeadline\(s, PLAN\.day\)\}/]]) assert.match(PAGE, re, name);
  for (const [kind, make] of KINDS) {
    const s = make(), brief = ea.eaTodayBrief(s), tag = ea.eaTodayTag(s);
    assert.ok(brief && tag.includes(brief.replace(/&/g, '&amp;')), kind);
    assert.doesNotMatch(tag, /Follow|Read|Official/);
  }
});

test('the map: every notice is ringed and named in the tooltip, as a cue to read it; the key says so', () => {
  assert.match(PAGE, /Ringed: an official notice; open the spot to read it/);
  assert.match(PAGE, /const mapAdvised = s => typeof eaTodayAdvice === 'function' && eaTodayAdvice\(s\)\.length > 0;/);   // every notice, not only restricting
  assert.match(PAGE, /color: mapAdvised\(s\) \? ADVICE_RING : PAPER/);   // the spot page's small map too
  assert.match(PAGE, /const markerTip = s => \{ const o = typeof eaTodayBrief === 'function' \? eaTodayBrief\(s\) : '';/);
});

test('the spot\'s page: the label, the ask under the level and the coverage line follow the kind', () => {
  for (const [kind, make] of KINDS) {
    const s = make(), brief = ea.eaTodayBrief(s);
    const block = ea.eaTodayOfficial(s);
    assert.ok(block.includes(`<p class="o-line">${s.official[0].line}</p>`), kind);   // the reviewed line, in full
    for (const t of [block, ea.eaTodayAct(s), ea.eaTodayApart(s), ea.eaTodayCover(s)]) says(kind, t, brief);
    if (kind === 'restricting') {
      assert.match(block, /<h2 id="official-h">Official advice<\/h2>/);
      assert.equal(ea.eaTodayAct(s), 'Follow the official advice above first.');
    } else {
      assert.match(block, /<h2 id="official-h">Official notice<\/h2>/);
      assert.equal(ea.eaTodayAct(s), 'Read the official notice above first.');
    }
  }
  // The "Not known here" row names the EA only where the spot has the EA's panel.
  assert.match(PAGE, /eaTodayId\(d\) \? "Today's EA advice" : 'Official notice', 'Notice shown above'/);
  assert.ok(ea.eaTodayId(KINDS[0][1]()));
  assert.equal(ea.eaTodayId(KINDS[1][1]()), null);
});

test('the outing, spot and backup: tags in both columns; one combined line naming each; "neither" only for restricting', () => {
  const col = (s, extra = {}) => ({ id: s.id, name: s.name, href: `spot/${s.id}/`, tone: 'low', headline: 'Low risk tomorrow', level: 'low',
    official: O.outingOfficial(s), notice: ea.eaTodayBrief(s), advised: ea.eaTodayRestricts(s), ...extra });
  const tile = (main, alt) => O.outingSection({ day: DATES[1], when: '', spot: main.id, groups: [], backupGroups: [], missing: [], issued: 'x', open: true, main, alt });
  const [r, n, l] = KINDS.map(([, make]) => make());
  const h = tile(col(n), col(l));
  assert.match(h, /Your spot and your backup both have an official notice\./);
  assert.ok(h.includes(`Your spot, Hampstead Mixed Pond: ${ea.eaTodayBrief(n)}`) && h.includes(`Backup, Legacy Pond: ${ea.eaTodayBrief(l)}`));
  says('neutral', h, ea.eaTodayBrief(n)); says('legacy', h.split(ea.eaTodayBrief(n)).join(''), ea.eaTodayBrief(l));
  assert.doesNotMatch(h, /outing-poor/);   // neither restricts: no "neither looks good" from the notices
  // A restricting spot with a Very high backup: "neither", naming the notice as a notice.
  assert.match(tile(col(r), col(spot('v', 'River Wey', []), { level: 'very high', tone: 'vhigh' })),
    /Neither spot looks good tomorrow\.<\/b> Frensham Great Pond has an official notice, and River Wey is at Very high risk\./);
  // The calendar file asks to check any official notice, whatever its kind.
  assert.equal(O.OUTING_CHECK, 'Check SwimSignal and any official notice before you go.');
});

test('the share picture, the embed, the sites view, the organisers\' page, the record and the comparison', () => {
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
  const src = PAGE.slice(PAGE.indexOf('<script>\n') + 9, PAGE.lastIndexOf('</script>')).split('\n');
  const i = src.findIndex(x => x.startsWith('const shareNotice ='));
  vm.runInContext(src.slice(i, i + 2).join('\n'), ctx);
  const share = vm.runInContext('shareNotice', ctx);
  for (const [kind, make] of KINDS) {
    const s = make(), brief = ea.eaTodayBrief(s);
    const texts = [share(s), Embed.card(s, DATA, NOW), Sites.row(s), Org.forecast(s, DATES[1], DATA, NOW),
      Rec.view(s, DATES[1], DATA, null, 'https://swimsignal.co.uk/', NOW), X.compareAdvice(s)];
    for (const t of texts) { assert.ok(t.includes(brief) || t.includes(brief.replace(/&/g, '&amp;')), kind); says(kind, t, brief); }
    if (kind === 'restricting') for (const t of texts) assert.match(t, /Follow|follow it/, t.slice(0, 120));
  }
});

test('Saved\'s "since you looked" and the outing\'s watch follow the kind kept in the note', () => {
  const later = { forecast: '2026-10-28T15:00:00Z', at: Date.parse('2026-10-28T15:05:00Z') };
  for (const [kind, make] of KINDS) {
    const s = make(), brief = ea.eaTodayBrief(s);
    const now = { id: s.id, level: 'low', discharging: 0, rating: null, gap: false, official: S.seenOfficial(s), ...later };
    const was = { ...now, official: null, forecast: '2026-10-28T07:00:00Z', at: Date.parse('2026-10-28T07:05:00Z') };
    const line = S.sinceLine(was, now);
    assert.ok(line.includes(brief), kind); says(kind, line, brief);
    const w = W.outingWatchLines(W.outingWatchRecord({ ...s, official: [] }, DATES[1], was.forecast, was.at), W.outingWatchRecord(s, DATES[1], now.forecast, now.at));
    assert.ok(w.lines[0].includes(brief), kind); says(kind, w.lines[0], brief);
  }
});

test('Find a window on Saved: the notice in its own words before the levels, "follow" only for a restricting one', () => {
  const FW = require('../src/dipcast/site/findwindow.js');
  for (const [kind, make] of KINDS) {
    const s = make(), brief = ea.eaTodayBrief(s), h = FW.fwSection([s], DATES, x => `spot/${x.id}/`);
    assert.ok(h.includes(`<p class="o-tag">${brief}</p>`), kind);
    says(kind, h, brief);
    if (kind === 'restricting') assert.match(h, /The official advice is not part of these levels: follow it first\./);
  }
});
