// Evidence map (src/dipcast/site/evmap.js, prototype, docs/EVIDENCE-MAP-2026-10.md): what counts as a gap,
// the words of each mark (whose, when, where from the spot), no live status told from a status showing no
// spill in words and in marks, every state from the build's own fields (never worked out from counts), and the
// page unchanged without ?evidence=1. On the live files of 30 Oct 2026, trimmed, with the trace's cut ends from
// trace.spot_trace_parts (tests/fixtures/evmap_*.json), on a fixed clock an hour after their issue time.
// node --test tests/site_evmap.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const L = require('../src/dipcast/site/levels.js');
global.overflowNames = L.overflowNames;
global.companyName = L.companyName;
const M = require('../src/dipcast/site/evmap.js');

const load = f => JSON.parse(fs.readFileSync(join(__dirname, 'fixtures', f), 'utf8'));
const CROM = load('evmap_cromwheel.json'), WYE = load('evmap_symonds_yat.json');
const NOW = Date.parse(CROM.generated_at) + 36e5;
const model = (f, now = NOW, over = {}) => M.evmapModel({ ...f.spot, ...over }, f.trace, f.upstream, now, f.generated_at);
const tile = (f, now = NOW) => M.evmapTile(f.spot, f.trace, f.upstream, now, f.generated_at, 375);
const text = html => html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');

test('no live status and a status showing no spill read differently, in words and in the head mark; counts lead', () => {
  const wye = M.evmapCoverage(WYE.spot), crom = M.evmapCoverage(CROM.spot);
  assert.equal(wye.kind, 'little');
  assert.equal(wye.head, 'Live sewage spill status unavailable.');
  assert.match(wye.said, /^None of the 14 overflows upstream reported a status: Dŵr Cymru Welsh Water has no live feed SwimSignal reads\./);
  assert.match(wye.said, /not a reading\. A quiet drawing here means not known\.$/);
  assert.equal(crom.kind, 'most');
  assert.equal(crom.head, 'Live status from 13 of 16 overflows upstream.');
  assert.match(crom.said, /^At the last poll before this update: none discharging; 2 not discharging after a spill lately whose water the model still counts\. 3 gave no current status, so could be spilling unseen\.$/);
  // A hollow dashed mark where nothing reports, a filled one where statuses came in: not colour alone.
  assert.match(M.evmapSwatch(wye.mark), /em-open em-dash/);
  assert.doesNotMatch(M.evmapSwatch(crom.mark), /em-open/);
  // Some report, but not the ones the model weighs most (Sandy Lane, Chester, 30 Oct: 1 of 13).
  const sandy = M.evmapCoverage({ upstream_summary: { overflows: 13 }, now: { monitored_upstream: 1, monitored_weight: 0.05, upstream_weight: 1.9, no_feed_upstream: 12 } });
  assert.equal(sandy.kind, 'little');
  assert.equal(sandy.head, 'Little live evidence: status from 1 of 13 overflows upstream.');
  const full = M.evmapCoverage({ upstream_summary: { overflows: 4 }, now: { monitored_upstream: 4, monitored_weight: 1, upstream_weight: 1 } });
  assert.equal(full.head, 'Live status from all 4 overflows upstream.');
  // Nothing upstream: said, never an empty map with nothing to say.
  const none = M.evmapCoverage({ upstream_summary: { overflows: 0 }, assumptions: { max_upstream_km: 60 } });
  assert.equal(none.kind, 'none');
  assert.match(none.said, /An empty drawing does not mean nothing reaches the water/);
  // The weighted share is not in the head; "reach" is not used for it.
  for (const c of [wye, crom, sandy, full]) assert.doesNotMatch(c.head + c.said, /reach|%/);
});

test('every overflow mark says whose it is, when it was reported, and where it is from the spot; travel is modelled', () => {
  const m = model(CROM), g = m.overflows.find(o => o.id === 'YWS00185');   // Grassington STW
  assert.equal(g.mark, 'spill');
  assert.equal(g.what, 'Grassington sewage works overflow');
  assert.equal(g.age, '1 h 30 min ago');
  assert.equal(g.src, "Yorkshire Water's live feed, via the National Storm Overflow Hub");
  assert.equal(text(g.rel), "25.7 km upstream along the rivers. Modelled travel time to the spot: about 36 h, at the model's assumed 0.2 m/s.");
  assert.equal(g.say, "Reported not discharging at the last poll before this update, after a spill that ended 28 Oct, 10:32. The model still counts that spill's water here.");
  for (const o of [...m.overflows, ...model(WYE).overflows]) {
    assert.ok(o.src, `${o.id} has a source`);
    assert.ok(o.age, `${o.id} has an age or "No status"`);
    assert.match(o.rel, /upstream along|At the spot/, `${o.id} is placed against the spot`);
    // The weight is never given as a share of a spill that arrives.
    assert.doesNotMatch(o.rel + o.say, /bacteria|% of a spill|reach the spot\./);
  }
  assert.equal(m.overflows.find(o => o.id === 'YWS00176').rel, 'At the spot.');
  assert.equal(text(M.evmapRel({ distance_km: 2, lake_distance_km: 3.1, travel_h: 20, weight: 0.4 }, { river_velocity_ms: 0.2, lake_velocity_ms: 0.05 })),
    "5.1 km upstream along the water, 3.1 km of it across a lake. Modelled travel time to the spot: about 20 h, at the model's assumed 0.2 m/s in rivers and 0.05 m/s in lakes.");
});

test('what counts as a gap: no live feed, no current status, a status not in the file, an aged status', () => {
  const now = NOW, at = CROM.generated_at;
  assert.equal(M.evmapMark({ status: 0, data_state: 'live', feed_updated_at: at }, now), 'live');
  assert.equal(M.evmapMark({ status: 1, data_state: 'live' }, now), 'spill');
  assert.equal(M.evmapMark({ status: -3, last_status: 1, data_state: 'offline' }, now), 'spill', 'running when its feed last answered');
  assert.equal(M.evmapMark({ status: 0, data_state: 'live', now_contribution: 0.1 }, now), 'spill', 'a spill lately whose water still counts');
  assert.equal(M.evmapMark({ status: -1, data_state: 'offline' }, now), 'dark');
  assert.equal(M.evmapMark({ status: 0, data_state: 'stale' }, now), 'dark');
  assert.equal(M.evmapMark({ status: -3, data_state: 'offline' }, now), 'dark', 'a feed that is down');
  assert.equal(M.evmapMark({ status: -2, data_state: 'no_feed' }, now), 'nofeed');
  assert.equal(M.evmapMark({ status: -2, data_state: 'offline' }, now), 'nofeed', 'not in its company\'s feed');
  assert.equal(M.evmapMark({ has_live: false }, now), 'nofeed');
  assert.equal(M.evmapMark({ has_live: true, status: null }, now), 'unheld', 'an older upstream file: not known');
  assert.equal(M.evmapMark({ status: 0, data_state: 'live', feed_updated_at: at }, Date.parse(at) + 7 * 36e5), 'dark', 'over six hours old where read');
  // The Wye: all 14 hollow and dashed, the company named.
  const wye = model(WYE).overflows;
  assert.equal(wye.length, 14);
  assert.ok(wye.every(o => o.mark === 'nofeed' && o.gap && o.age === 'No status'));
  assert.ok(wye.every(o => /Dŵr Cymru Welsh Water has no live feed SwimSignal reads/.test(o.say)));
});

test('each overflow takes its own status from the upstream file; the spot\'s counts are never used to work one out', () => {
  // The live upstream file of 30 Oct 2026 has no status fields (they come with this branch's build): the six
  // overflows outside the ten are not known, and say so.
  const out = model(CROM).overflows.filter(o => !CROM.spot.contributors.some(c => c.site_id === o.id));
  assert.equal(out.length, 6);
  assert.ok(out.every(o => o.mark === 'unheld' && o.gap && /this update's file does not give its status/.test(o.say)));
  // With the build's fields, each one's own: here five quiet, one offline.
  const states = ['live', 'live', 'offline', 'live', 'live', 'live'];
  let k = 0;
  const up = { overflows: CROM.upstream.overflows.map(o => CROM.spot.contributors.some(c => c.site_id === o.site_id) ? o
    : { ...o, status: states[k] === 'live' ? 0 : -1, data_state: states[k++], feed_updated_at: '2026-10-30T17:19:03+00:00' }) };
  const got = M.evmapModel(CROM.spot, CROM.trace, up, NOW, CROM.generated_at).overflows.filter(o => !CROM.spot.contributors.some(c => c.site_id === o.id));
  assert.deepEqual(got.map(o => o.mark), ['live', 'live', 'dark', 'live', 'live', 'live']);
  assert.equal(got[2].say, 'No current status: the monitor was offline at the last poll.');
  // The same file with the spot's counts changed: the marks do not move.
  const recount = M.evmapModel({ ...CROM.spot, now: { ...CROM.spot.now, monitored_upstream: 16 } }, CROM.trace, up, NOW, CROM.generated_at);
  assert.deepEqual(recount.overflows.map(o => o.mark), M.evmapModel(CROM.spot, CROM.trace, up, NOW, CROM.generated_at).overflows.map(o => o.mark));
  // No upstream file: the trace's positions, said to be without details.
  const bare = M.evmapModel(CROM.spot, CROM.trace, null, NOW, CROM.generated_at);
  assert.equal(bare.overflows.length, 16);
  assert.ok(bare.overflows.filter(x => !CROM.spot.contributors.some(c => c.site_id === x.id)).every(x => x.mark === 'unheld' && /could not load its details/.test(x.say)));
});

test('where the trace stops comes from the build: bars at its cut ends, none where every river reaches its source', () => {
  const wye = model(WYE), crom = model(CROM);
  assert.equal(wye.cuts.length, 6);
  const limit = wye.gaps.find(g => g.id === 'limit');
  assert.match(text(limit.say), /follows the rivers 60 km upstream and stops\. These 6 rivers go on above the bars; overflows there are not counted, whatever they report\./);
  assert.match(text(limit.rel), /Modelled travel time from there: about 83 h, at the model's assumed 0\.2 m\/s\./);
  const svg = M.evmapSvg(wye, 375);
  assert.equal((svg.match(/class="em-limit"/g) || []).length, 6);
  assert.match(svg, /trace stops, 60 km/);
  // Cromwheel: the build cut no river (its trace reaches every source within 60 km), so no bar and a note.
  assert.deepEqual(crom.cuts, []);
  assert.doesNotMatch(M.evmapSvg(crom, 375), /em-limit|trace stops/);
  assert.match(crom.notes.find(n => n.id === 'limit').say, /Every river traced reaches its source within 60/);
  // An older trace file without cut_ends: no bar guessed, and the gap said.
  const old = M.evmapModel(CROM.spot, { ...CROM.trace, cut_ends: undefined }, CROM.upstream, NOW, CROM.generated_at);
  assert.deepEqual(old.cuts, []);
  assert.match(old.gaps.find(g => g.id === 'limit').say, /not in this update's file, so it is not drawn/);
});

test('the other gaps are drawn: the rivers, the spot without lab samples; the gauge at its station where the build gives it', () => {
  const wye = model(WYE), svg = M.evmapSvg(wye, 375);
  assert.match(svg, /<rect [^>]*class="em-open em-dash"\/>/, 'the spot without lab samples: a dashed square');
  assert.match(M.evmapSvg(model(CROM), 375), /<rect [^>]*class="em-live"\/>/, 'with one: a filled square');
  assert.equal((svg.match(/class="em-open em-dash"/g) || []).length, 14 + 1, 'every overflow with no status drawn, not left out');
  assert.ok(wye.gaps.some(g => g.id === 'river' && /Nothing along them is measured/.test(g.say)));
  assert.ok(wye.gaps.some(g => g.kind === 'sample' && /No lab samples/.test(g.say)));
  const noGauge = model(WYE, NOW, { river_state: null });
  assert.ok(noGauge.gaps.some(g => g.id === 'gauge' && /No Environment Agency river gauge with a reading within 15 km/.test(text(g.say))));
  // The live file has no station position yet: kept in words.
  assert.match(text(wye.items.find(i => i.id === 'gauge').rel), /^4\.5 km away in a straight line, on the same river\. Not drawn: this update gives its distance, not its place\.$/);
  assert.doesNotMatch(svg, /em-gauge/);
  // With the build's station_lat and station_lon: drawn there, and not said to be missing.
  const placed = model(WYE, NOW, { river_state: { ...WYE.spot.river_state, station_lat: 51.8566, station_lon: -2.6017 } });
  assert.match(M.evmapSvg(placed, 375), /class="em-gauge"/);
  assert.doesNotMatch(placed.items.find(i => i.id === 'gauge').rel, /Not drawn/);
  assert.match(placed.items.find(i => i.id === 'gauge').say, /not part of the pollution level/);
});

test('the tile: the counts first, the weight explained in the notes, statuses as at the last poll, nothing reassuring or causal', () => {
  for (const f of [CROM, WYE]) {
    const h = tile(f), t = text(h);
    assert.match(h, /^<section class="tile em" id="evmap"/);
    assert.match(t, /Statuses as at this update, issued 30 Oct, 17:49 \(1 h ago\)\./);
    assert.match(t, /Gaps: what is not known here/);
    assert.match(t, /What a status is Each status is what the company's feed said at the last poll before this update, issued 30 Oct, 17:49, not a continuous reading\./);
    assert.doesNotMatch(t, /\bsafe\b|\bclean\b|\bcaus|\bpolluted by\b|bacteria|modelled reach|reach watched/i);
    assert.doesNotMatch(t, /\b(?:is|was|are) (?:low|moderate|high|very high)\b(?! risk)/i);
  }
  assert.match(text(tile(CROM)), /Share of the model's weight reporting .*carry 74% of the model's weight for this spot\. Each overflow's weight is the model's estimate .* it is not a measured share of what reaches the water\./);
  assert.match(text(tile(WYE)), /0 of the 14 overflow marks are statuses reported at the last poll; the hollow ones are gaps\./);
  assert.doesNotMatch(M.EVMAP_CSS, /#[0-9a-f]{3,6}\b|rgb|gradient|shadow|999px/i);
  assert.equal(M.evmapTile({ ...WYE.spot, error: 'forecast failed' }, WYE.trace, WYE.upstream, NOW, WYE.generated_at), '');
});

test('the keyboard: the drawing takes the focus and the arrow keys step through every mark, nearest first', () => {
  const m = model(CROM), svg = M.evmapSvg(m, 375);
  assert.match(svg, /^<svg class="em-svg" [^>]*tabindex="0"[^>]*aria-describedby="em-keys">/);
  assert.match(svg, /<desc id="em-keys">Use the arrow keys to step through the marks/);
  const order = M.evmapOrder(m).map(([o]) => o.km);
  assert.equal(order.length, 16);
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  assert.match(M.EVMAP_CSS, /\.em-svg:focus-visible \{ outline:2px solid var\(--focus\)/);
  // The folded list stays the full text, reachable by its summary.
  assert.match(tile(CROM), /<details class="em-more"><summary>Every mark and gap in words \(\d+\)<\/summary>/);
});

test('the layout keeps every mark inside the drawing, at any width', () => {
  for (const w of [288, 320, 375, 480]) for (const f of [CROM, WYE]) {
    const Lo = M.evmapLayout(model(f), w);
    for (const [x, y] of [...Lo.overflows, Lo.spot, ...Lo.cuts]) {
      assert.ok(x >= 0 && x <= w && y >= 0 && y <= Lo.height, `${x},${y} inside ${w}x${Lo.height}`);
    }
  }
});

test('the page is unchanged without ?evidence=1, and the offline copy keeps the script', () => {
  const page = fs.readFileSync(join(__dirname, '..', 'src', 'dipcast', 'site', 'index.html'), 'utf8');
  assert.doesNotMatch(page, /<script src="evmap\.js/);
  assert.match(page, /const EV_MAP = new URLSearchParams\(location\.search\)\.get\('evidence'\) === '1';/);
  assert.match(page, /\$\{EV_MAP && d\.detail_file \? '<div id="evmap-host"><\/div>' : ''\}/);
  assert.match(page, /if \(EV_MAP\) mountEvMap\(d\);/);
  assert.match(page, /s\.src = `evmap\.js\$\{v \? `\?v=\$\{new URL\(v\)\.searchParams\.get\('v'\)\}` : ''\}`;/);
  const sw = fs.readFileSync(join(__dirname, '..', 'src', 'dipcast', 'site', 'sw.js'), 'utf8');
  assert.match(sw, /`evmap\.js\?v=\$\{BUILD\}`/);
});

test("no other script of the page defines one of evmap.js's names", () => {
  const site = join(__dirname, '../src/dipcast/site');
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(m => m[1]));
  const mine = names(fs.readFileSync(join(site, 'evmap.js'), 'utf8'));
  const html = fs.readFileSync(join(site, 'index.html'), 'utf8');
  const others = [html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')),
    ...fs.readdirSync(site).filter(f => f.endsWith('.js') && !['evmap.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(site, f), 'utf8'))];
  assert.deepEqual(others.flatMap(src => [...names(src)].filter(n => mine.has(n))), []);
  assert.ok([...mine].every(n => /^(evmap|EVMAP)/.test(n)), 'every name begins evmap or EVMAP');
});
