// Evidence map (src/dipcast/site/evmap.js, prototype, docs/EVIDENCE-MAP-2026-10.md): what counts as a gap,
// the words of each mark (whose, when, where from the spot), little evidence told from evidence of no spill
// in words and in marks, and the page unchanged without ?evidence=1. On the live files of 30 Oct 2026,
// trimmed (tests/fixtures/evmap_*.json), and on a fixed clock an hour after their issue time.
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
const model = (f, now = NOW) => M.evmapModel(f.spot, f.trace, f.upstream, now, f.generated_at);
const tile = (f, now = NOW) => M.evmapTile(f.spot, f.trace, f.upstream, now, f.generated_at, 375);
const text = html => html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');

test('little evidence and evidence of no spill read differently, in words and in the head mark', () => {
  const wye = M.evmapCoverage(WYE.spot), crom = M.evmapCoverage(CROM.spot);
  assert.equal(wye.kind, 'little');
  assert.equal(wye.head, 'Little evidence here.');
  assert.match(wye.said, /^None of the 14 overflows upstream reports live: Dŵr Cymru Welsh Water has no live feed SwimSignal reads\./);
  assert.match(wye.said, /not a reading\. A quiet drawing here means not known\.$/);
  assert.equal(crom.kind, 'most');
  assert.match(crom.said, /^13 of 16 overflows upstream report live, carrying 74% of the modelled reach\. What they reported at issue: none discharging/);
  // A hollow dashed mark for little evidence, a filled one for a reading: not colour alone.
  assert.equal(wye.mark, 'nofeed');
  assert.notEqual(crom.mark, 'nofeed');
  assert.match(M.evmapSwatch(wye.mark), /em-open em-dash/);
  assert.doesNotMatch(M.evmapSwatch(crom.mark), /em-open/);
  // Most of the count reporting but little of the reach (Sandy Lane, Chester, 30 Oct: 1 of 13, 2.6%) is little too.
  const sandy = M.evmapCoverage({ upstream_summary: { overflows: 13 }, now: { monitored_upstream: 1, monitored_weight: 0.05, upstream_weight: 1.9, no_feed_upstream: 12 } });
  assert.equal(sandy.kind, 'little');
  assert.match(sandy.said, /1 of 13 overflows upstream report live, but they carry 3% of the modelled reach/);
  // Nothing upstream: said, never an empty map with nothing to say.
  const none = M.evmapCoverage({ upstream_summary: { overflows: 0 }, assumptions: { max_upstream_km: 60 } });
  assert.equal(none.kind, 'none');
  assert.match(none.said, /An empty drawing does not mean nothing reaches the water/);
});

test('every overflow mark says whose it is, when it was read, and where it is from the spot', () => {
  const m = model(CROM), g = m.overflows.find(o => o.id === 'YWS00185');   // Grassington STW
  assert.equal(g.mark, 'spill');
  assert.equal(g.what, 'Grassington sewage works overflow');
  assert.equal(g.age, '1 h 30 min ago');
  assert.equal(g.src, "Yorkshire Water's live feed, via the National Storm Overflow Hub");
  assert.equal(text(g.rel), "25.7 km upstream, about 36 h at the model's 0.2 m/s. The model expects 22% of a spill's bacteria to reach the spot.");
  assert.match(g.say, /^Reported a spill that ended 28 Oct, 10:32\. The model still counts its water here\.$/);
  for (const o of [...m.overflows, ...model(WYE).overflows]) {
    assert.ok(o.src, `${o.id} has a source`);
    assert.ok(o.age, `${o.id} has an age or "No reading"`);
    assert.match(o.rel, /upstream|At the spot/, `${o.id} is placed against the spot`);
  }
  assert.equal(m.overflows.find(o => o.id === 'YWS00176').rel, 'At the spot.');
  // Across a lake, both speeds.
  assert.equal(text(M.evmapRel({ distance_km: 2, lake_distance_km: 3.1, travel_h: 20, weight: 0.4 }, { river_velocity_ms: 0.2, lake_velocity_ms: 0.05 })),
    "5.1 km upstream, 3.1 km of it across a lake, about 20 h at the model's 0.2 m/s in rivers and 0.05 m/s in lakes. The model expects 40% of a spill's bacteria to reach the spot.");
});

test('what counts as a gap: no live feed, no current reading, a reading not held, an aged reading', () => {
  const now = NOW;
  assert.equal(M.evmapMark({ status: 0, data_state: 'live', feed_updated_at: CROM.generated_at }, now), 'live');
  assert.equal(M.evmapMark({ status: 1, data_state: 'live' }, now), 'spill');
  assert.equal(M.evmapMark({ status: -3, last_status: 1, data_state: 'offline' }, now), 'spill', 'running when its feed last answered');
  assert.equal(M.evmapMark({ status: 0, data_state: 'live', now_contribution: 0.1 }, now), 'spill', 'a spill lately whose water still counts');
  assert.equal(M.evmapMark({ status: -1, data_state: 'offline' }, now), 'dark');
  assert.equal(M.evmapMark({ status: 0, data_state: 'stale' }, now), 'dark');
  assert.equal(M.evmapMark({ status: -3, data_state: 'offline' }, now), 'dark', 'a feed that is down');
  assert.equal(M.evmapMark({ status: -2, data_state: 'no_feed' }, now), 'nofeed');
  assert.equal(M.evmapMark({ status: -2, data_state: 'offline' }, now), 'nofeed', 'not in its company\'s feed');
  // A current reading read over six hours later is no longer current.
  assert.equal(M.evmapMark({ status: 0, data_state: 'live', feed_updated_at: CROM.generated_at }, Date.parse(CROM.generated_at) + 7 * 36e5), 'dark');
  // The Wye: all 14 hollow and dashed.
  const wye = model(WYE).overflows;
  assert.equal(wye.length, 14);
  assert.ok(wye.every(o => o.mark === 'nofeed' && o.gap && o.age === 'No reading'));
  assert.ok(wye.filter(o => o.id.startsWith('DCW')).every(o => /Dŵr Cymru Welsh Water has no live feed SwimSignal reads/.test(o.say)), 'named where one of the ten says so');
});

test('the overflows outside the ten get a state only where the counts settle it', () => {
  // Cromwheel: 16 upstream, 13 reporting; the ten listed hold 8 counted and 2 offline, so of the other six,
  // five reported and one did not, and which is not in the data.
  const m = model(CROM), out = m.overflows.filter(o => !CROM.spot.contributors.some(c => c.site_id === o.id));
  assert.equal(out.length, 6);
  assert.ok(out.every(o => o.mark === 'unheld' && o.gap));
  assert.match(out[0].say, /Of the 6 overflows upstream like it, 5 reported live at issue and 1 did not; which is which is not in the data\./);
  // Where the counts leave one answer they give it: every other one reporting quietly.
  const spot = { ...CROM.spot, now: { ...CROM.spot.now, monitored_upstream: 14 } };
  const o = M.evmapOthers(spot, CROM.upstream.overflows, new Map(CROM.spot.contributors.map(c => [c.site_id, c])));
  assert.deepEqual({ n: o.n, live: o.live, state: o.state }, { n: 6, live: 6, state: 'live' });
  // A spill among them: never drawn as quiet.
  const dis = { ...spot, now: { ...spot.now, discharging_upstream: 1 } };
  assert.equal(M.evmapOthers(dis, CROM.upstream.overflows, new Map(CROM.spot.contributors.map(c => [c.site_id, c]))).state, 'unheld');
  // No upstream file: the trace's positions, said to be without details, never quiet.
  const bare = M.evmapModel(CROM.spot, CROM.trace, null, NOW, CROM.generated_at);
  assert.equal(bare.overflows.length, 16);
  assert.ok(bare.overflows.filter(x => !CROM.spot.contributors.some(c => c.site_id === x.id)).every(x => x.mark === 'unheld' && /could not load its details/.test(x.say)));
});

test('the gaps are drawn: where the trace stops, the rivers, the spot without lab samples, no gauge', () => {
  const wye = model(WYE), crom = model(CROM);
  // The Wye's eight ends between 58.7 and 59.5 km along the rivers, and none of its shorter ones.
  assert.equal(wye.ends.length, 8);
  assert.ok(wye.ends.every(e => e.km >= 58.2 && e.km <= 60));
  assert.ok(crom.ends.length >= 1 && crom.ends.every(e => e.km >= 58.2));
  const limit = wye.gaps.find(g => g.id === 'limit');
  assert.match(text(limit.say), /follows the rivers 60 km upstream and stops\. Overflows above these 8 points are not counted, whatever they report\./);
  assert.match(text(limit.rel), /over 83 h at the model's 0\.2 m\/s\. Marked where a traced river ends 58 km or more along it, an estimate\./);
  const svg = M.evmapSvg(wye, 375);
  assert.equal((svg.match(/class="em-limit"/g) || []).length, 8);
  assert.match(svg, /trace stops, 60 km/);
  assert.match(svg, /<rect [^>]*class="em-open em-dash"\/>/, 'the spot without lab samples: a dashed square');
  assert.match(M.evmapSvg(crom, 375), /<rect [^>]*class="em-live"\/>/, 'with one: a filled square');
  assert.equal((svg.match(/class="em-open em-dash"/g) || []).length, 14 + 1, 'every unreported overflow drawn, not left out');
  assert.ok(wye.gaps.some(g => g.id === 'river' && /Nothing along them is measured/.test(g.say)));
  assert.ok(wye.gaps.some(g => g.kind === 'sample' && /No lab samples/.test(g.say)));
  const noGauge = M.evmapModel({ ...WYE.spot, river_state: null }, WYE.trace, WYE.upstream, NOW, WYE.generated_at);
  assert.ok(noGauge.gaps.some(g => g.id === 'gauge' && /No Environment Agency river gauge with a reading within 15 km/.test(text(g.say))));
  const gauge = wye.items.find(i => i.id === 'gauge');
  assert.equal(text(gauge.rel), "4.5 km away in a straight line, on the same river. Not drawn: this page's data gives its distance, not its place.");
  assert.match(gauge.say, /Not part of the pollution level\./);
});

test('the tile: both lists in full, no causal or reassuring words, tokens only', () => {
  for (const f of [CROM, WYE]) {
    const h = tile(f), t = text(h);
    assert.match(h, /^<section class="tile em" id="evmap"/);
    assert.match(t, /Readings as at this update, issued 30 Oct, 17:49 \(1 h ago\)\./);
    assert.match(t, /Gaps: what is not known here/);
    assert.doesNotMatch(t, /\bsafe\b|\bclean\b|\bcaus|\bpolluted by\b/i);
    // A level word always with its noun: none stands bare in the tile.
    assert.doesNotMatch(t, /\b(?:is|was|are) (?:low|moderate|high|very high)\b(?! risk)/i);
  }
  assert.match(text(tile(WYE)), /0 of the 14 overflow marks are readings; the hollow ones are gaps\./);
  assert.doesNotMatch(M.EVMAP_CSS, /#[0-9a-f]{3,6}\b|rgb|gradient|shadow|999px/i);
  assert.equal(M.evmapTile({ ...WYE.spot, error: 'forecast failed' }, WYE.trace, WYE.upstream, NOW, WYE.generated_at), '');
});

test('the layout keeps every mark inside the drawing, at any width', () => {
  for (const w of [288, 375, 480]) for (const f of [CROM, WYE]) {
    const Lo = M.evmapLayout(model(f), w);
    for (const [x, y] of [...Lo.overflows, Lo.spot, ...Lo.ends]) {
      assert.ok(x >= 0 && x <= w && y >= 0 && y <= Lo.height, `${x},${y} inside ${w}x${Lo.height}`);
    }
  }
});

test('the page is unchanged without ?evidence=1: no script tag, a host only behind the flag', () => {
  const page = fs.readFileSync(join(__dirname, '..', 'src', 'dipcast', 'site', 'index.html'), 'utf8');
  assert.doesNotMatch(page, /<script src="evmap\.js/);
  assert.match(page, /const EV_MAP = new URLSearchParams\(location\.search\)\.get\('evidence'\) === '1';/);
  assert.match(page, /\$\{EV_MAP && d\.detail_file \? '<div id="evmap-host"><\/div>' : ''\}/);
  assert.match(page, /if \(EV_MAP\) mountEvMap\(d\);/);
  assert.match(page, /s\.src = `evmap\.js\$\{v \? `\?v=\$\{new URL\(v\)\.searchParams\.get\('v'\)\}` : ''\}`;/);
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
