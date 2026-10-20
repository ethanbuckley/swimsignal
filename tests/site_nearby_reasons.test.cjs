// Why each spot on the Nearby card is there, in words (outside review, 20 Oct 2026): River Thames, Long
// Bridges, at moderate risk, offered "Lower risk nearby: River Thames, Hurley", downstream on the same
// river, with nothing to say so. The build gives each spot its `catchment` and the spots its water is
// `linked` to (src/dipcast/spot_links.py, tests/test_spot_links.py); index.html turns them into a reason
// under each row (nearWhy) and keeps another catchment or branch in view when one is near (otherAsWell).
// The fixtures copy Long Bridges, Hurley and Port Meadow as the live files had them on 20 Oct 2026.
// node --test tests/site_nearby_reasons.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const DATES = ['2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23', '2026-10-24'];
const NOW = Date.parse('2026-10-20T18:00:00+01:00');
const RISK = { low: 0.01, moderate: 0.23, high: 0.5, 'very high': 0.8 };
const spot = (id, labels, extra = {}) => ({ id, name: id, kind: 'river', river: 'River Thames', source: 'curated', lat: 51.74, lon: -1.25,
  upstream_summary: { overflows: 45 }, location: { mode: 'river' }, contributors: [],
  now: { label: labels[0], risk: RISK[labels[0]], discharging_upstream: 0, monitored_upstream: 45 },
  assumptions: { max_upstream_km: 60, recent_spill_hours: 48 },
  days: labels.map((l, i) => ({ date: DATES[i], label: l, risk: RISK[l], p_ecoli_gt900: 0.03, in_validated_season: false, rain_48h_mm: 1 })), ...extra });

const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
class FixedDate extends Date { constructor(...a) { if (!a.length) super(NOW); else super(...a); } static now() { return NOW; } }
const NAMES = ['esc', 'tone', 'km', 'away', 'PAGE_ID', 'spotPath', 'glyph', 'ICON', 'headNote', 'NEAR_KM', 'notHigherAnyDay', 'allFiveDays', 'ratedBetter',
  'joined', 'otherWater', 'unread', 'fewerUnread', 'nearWhy', 'otherAsWell', 'nearby'];
function page(spots) {
  const ctx = vm.createContext({ Date: FixedDate, ROOT: { pathname: '/' }, milesAway: m => `${m.toFixed(1)} miles away`, MILE_KM: 1.609, DATA: { spots } });
  const dir = path.join(__dirname, '../src/dipcast/site/');
  vm.runInContext(fs.readFileSync(dir + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(dir + 'levels.js', 'utf8') + `\nsetToday("${DATES[0]}");`, ctx);
  vm.runInContext(pageDefs(NAMES) + '\nvar DAY = null;', ctx);
  return ctx;
}
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/&nbsp;| /g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();
const run = (ctx, f, ...a) => vm.runInContext(f, ctx)(...a);
// The rows' ids, in order, and each row's reason.
const rows = h => [...h.matchAll(/data-id="([^"]+)"/g)].map(m => m[1]);
const why = (h, id) => { const li = h.split('<li>').find(x => x.includes(`data-id="${id}"`)) || ''; const m = li.match(/<span class="why">([^<]*)<\/span>/); return m ? m[1] : null; };

// Long Bridges, Port Meadow upstream (23 overflows counted at both), Hurley 37 km away in a straight line and
// 87 km of river below, beyond the 60 km the forecast traces, so none counted at both.
const THAMES = '6002834c';
const longBridges = () => spot('osm-thames-long-bridges', ['moderate', 'moderate', 'moderate', 'moderate', 'high'], { lat: 51.73783, lon: -1.24522,
  catchment: THAMES, linked: { 'thames-port-meadow': 's', 'thames-hurley': 'd' } });
const portMeadow = () => spot('thames-port-meadow', ['low', 'low', 'low', 'low', 'low'], { lat: 51.7717, lon: -1.2795, catchment: THAMES });
const hurley = () => spot('thames-hurley', ['low', 'low', 'low', 'moderate', 'moderate'], { lat: 51.5463, lon: -0.8236, catchment: THAMES });

test('the relation the build gives is read as it is: shares, downstream, upstream, another branch, a different catchment', () => {
  const d = longBridges(), ctx = page([]);
  assert.equal(run(ctx, 'joined', d, portMeadow()), 's');
  assert.equal(run(ctx, 'joined', d, hurley()), 'd');
  assert.equal(run(ctx, 'joined', { ...d, linked: { 'thames-hurley': 'u' } }, hurley()), 'u');
  assert.equal(run(ctx, 'joined', d, spot('wey', ['low'], { river: 'River Wey', catchment: THAMES })), 'branch');   // the Wey joins below both
  assert.equal(run(ctx, 'joined', d, spot('nidd', ['low'], { river: 'River Nidd', catchment: '032759b2' })), 'apart');
  // Nothing claimed where either side has no place on the network, or the forecast came before these fields.
  assert.equal(run(ctx, 'joined', d, spot('tarn', ['low'], { kind: 'lake', river: null })), null);
  assert.equal(run(ctx, 'joined', { ...d, catchment: undefined, linked: undefined }, portMeadow()), null);
  assert.equal(run(ctx, 'otherWater', d, spot('nidd', ['low'], { catchment: 'x' })), true);
  assert.equal(run(ctx, 'otherWater', d, portMeadow()), false);
  assert.equal(run(ctx, 'otherWater', d, spot('tarn', ['low'])), false);   // not known
});

test('each reason in words: same river, the forecast\'s counting, another branch, a different catchment', () => {
  const d = longBridges(), ctx = page([]), w = s => run(ctx, 'nearWhy', d, s);
  assert.equal(w(portMeadow()), 'Same river, shares overflows with this spot.');
  assert.equal(w(hurley()), 'Same river, further downstream. The forecast counts none of the same overflows.');
  assert.equal(run(ctx, 'nearWhy', { ...d, linked: { 'thames-hurley': 'u' } }, hurley()), 'Same river, further upstream. The forecast counts none of the same overflows.');
  // Not "same river" between a river and a lake, or rivers of two names (the Cherwell into the Thames).
  assert.equal(w(spot('thames-port-meadow', ['low'], { river: 'River Cherwell', catchment: THAMES })), 'Shares overflows with this spot.');
  const lakeBelow = spot('thames-hurley', ['low'], { kind: 'lake', river: null, catchment: THAMES });
  assert.equal(w(lakeBelow), 'Downstream of this spot. The forecast counts none of the same overflows.');
  // The forecast's counting only where both have overflows upstream: a tarn above Elter Water has none.
  assert.equal(w({ ...hurley(), upstream_summary: { overflows: 0 } }), 'Same river, further downstream.');
  assert.equal(w(spot('wey', ['low'], { river: 'River Wey', catchment: THAMES })), 'Same catchment, another branch.');
  assert.equal(w(spot('nidd', ['low'], { river: 'River Nidd', catchment: '032759b2' })), 'Different catchment.');
  assert.equal(w(spot('tarn', ['low'], { kind: 'lake', river: null })), '');
  // A different catchment is a fact, never a reassurance.
  for (const s of [spot('nidd', ['low'], { catchment: 'x' }), spot('wey', ['low'], { catchment: THAMES })])
    assert.doesNotMatch(w(s), /clean|safe|lower|better|independent|unaffected|free/i);
});

test('"Fewer missing upstream readings" where fewer overflows upstream give no current reading, and no smaller a share of their weight reports', () => {
  const ctx = page([]), fewer = (d, s) => run(ctx, 'fewerUnread', d, s);
  // Long Bridges on 20 Oct 2026: 44 of 45 report, with 99.5% of the weight.
  const d = longBridges(); d.now.monitored_upstream = 44; d.now.monitored_weight = 2.0356; d.now.upstream_weight = 2.0454;
  const all = spot('a', ['low'], { upstream_summary: { overflows: 10 } }); all.now.monitored_upstream = 10;
  assert.equal(run(ctx, 'unread', d), 1);
  assert.equal(fewer(d, all), true);
  assert.match(run(ctx, 'nearWhy', d, { ...all, catchment: 'x' }), /^Different catchment\. Fewer missing upstream readings\.$/);
  // Fewer by count, but the one that does not report carries most of the weight: not said.
  const three = { ...d, now: { ...d.now, monitored_upstream: 42, monitored_weight: 2.0, upstream_weight: 2.0454 } };   // 3 missing, 98% reporting
  const heavy = spot('b', ['low'], { upstream_summary: { overflows: 4 } });
  heavy.now = { ...heavy.now, monitored_upstream: 3, monitored_weight: 0.3, upstream_weight: 1 };                      // 1 missing, 30% reporting
  assert.equal(run(ctx, 'unread', heavy), 1);
  assert.equal(fewer(three, heavy), false);
  // Not where this spot misses none, nor at a spot with nothing upstream, nor where the other misses as many.
  assert.equal(fewer({ ...d, now: { ...d.now, monitored_upstream: 45 } }, all), false);
  assert.equal(fewer(d, spot('c', ['low'], { upstream_summary: { overflows: 0 } })), false);
  const same = spot('e', ['low'], { upstream_summary: { overflows: 9 } }); same.now.monitored_upstream = 8;
  assert.equal(fewer(d, same), false);
});

test('Long Bridges: Hurley is offered as further down the same river, and the note says nothing new where no other water is shown', () => {
  const d = longBridges(), ctx = page([d, portMeadow(), hurley()]);
  const h = run(ctx, 'nearby', d);
  assert.deepEqual(rows(h), ['thames-port-meadow', 'thames-hurley']);   // Hurley is moderate on Thursday, Long Bridges too: no higher
  assert.equal(why(h, 'thames-hurley'), 'Same river, further downstream. The forecast counts none of the same overflows.');
  assert.equal(why(h, 'thames-port-meadow'), 'Same river, shares overflows with this spot.');
  assert.match(text(h), /Lower risk nearby .* Lower now, and no higher on any of the five days\. A lower forecast level, not clean water: check the signs there too\.$/);
  assert.doesNotMatch(h, /different catchment or branch/i);
  // The reason sits in the row's own line, never in a level's colour.
  assert.match(h, /<\/span><span class="why">Same river, further downstream\./);
});

test('where the nearest three all share this water, the third gives way to the nearest on other water within reach', () => {
  const near = (id, dlat, extra = {}) => spot(id, ['low', 'low', 'low', 'low', 'low'], { lat: 51.73783 + dlat, lon: -1.24522, catchment: THAMES, ...extra });
  const d = longBridges();
  d.linked = { a: 's', b: 's', c: 'd', e: 's' };
  const [a, b, c, e] = [near('a', 0.01), near('b', 0.02), near('c', 0.03), near('e', 0.04)];
  const branch = near('wey', 0.2, { river: 'River Wey' });                 // about 22 km: the same catchment, another branch
  const apart = near('nidd', 0.3, { river: 'River Nidd', catchment: 'x' });   // about 33 km
  const far = near('far', 0.5, { catchment: 'y' });                          // about 56 km: out of reach
  let ctx = page([d, a, b, c, e, apart, branch, far]);
  let h = run(ctx, 'nearby', d);
  assert.deepEqual(rows(h), ['a', 'b', 'wey']);   // nearest first still: the branch in place of c
  assert.match(text(h), /A different catchment or branch has overflows and runoff of its own\.$/);
  // One on other water among the nearest three already: the nearest three, as before.
  ctx = page([d, a, { ...branch, lat: 51.73783 + 0.015 }, b, c, apart]);
  assert.deepEqual(rows(run(ctx, 'nearby', d)), ['a', 'wey', 'b']);
  // None within reach: the nearest three, as before.
  ctx = page([d, a, b, c, e, far]);
  assert.deepEqual(rows(run(ctx, 'nearby', d)), ['a', 'b', 'c']);
  // Fewer than three: nothing to give way.
  ctx = page([d, a, apart]);
  assert.deepEqual(rows(run(ctx, 'nearby', d)), ['a', 'nidd']);
});

test('every earlier rule still holds: the other water is chosen only from the spots the rules offer', () => {
  const near = (id, labels, dlat, extra = {}) => spot(id, labels, { lat: 51.73783 + dlat, lon: -1.24522, catchment: 'other', ...extra });
  const d = longBridges(); d.linked = { a: 's', b: 's', c: 's' };
  const same = (id, dlat) => near(id, ['low', 'low', 'low', 'low', 'low'], dlat, { catchment: THAMES });
  const higher = near('higher', ['low', 'low', 'low', 'very high', 'low'], 0.05);                           // higher on Thursday
  const plain = near('plain', ['low', 'low', 'low', 'low', 'low'], 0.06, { upstream_summary: { overflows: 0 }, days: [] });   // no level
  const poorWater = near('poor', ['low', 'low', 'low', 'low', 'low'], 0.07, { source: 'designated', classification: { class: 'poor', year: 2025 } });
  const dark = near('dark', ['low', 'low', 'low', 'low', 'low'], 0.08); dark.now.monitored_upstream = 0;      // right now not known
  const ok = near('ok', ['low', 'low', 'low', 'low', 'low'], 0.2);
  const ctx = page([d, same('a', 0.01), same('b', 0.02), same('c', 0.03), higher, plain, poorWater, dark, ok]);
  const h = run(ctx, 'nearby', d);
  assert.deepEqual(rows(h), ['a', 'b', 'ok']);
  // A water rated poor offers only better-rated waters, other water or not.
  const poorHere = { ...d, source: 'designated', classification: { class: 'poor', year: 2025 } };
  const rated = near('rated', ['low', 'low', 'low', 'low', 'low'], 0.25, { source: 'designated', classification: { class: 'good', year: 2025 } });
  const c2 = page([poorHere, same('a', 0.01), same('b', 0.02), ok, rated]);
  assert.deepEqual(rows(run(c2, 'nearby', poorHere)), ['rated']);
  assert.match(text(run(c2, 'nearby', poorHere)), /Rated better than poor by the Environment Agency, and lower now/);
  // A picked day compares that day alone, and the reasons stay the same.
  const c3 = page([d, higher]);
  vm.runInContext(`DAY = "${DATES[3]}"`, c3);
  assert.deepEqual(rows(run(c3, 'nearby', d)), []);
  vm.runInContext(`DAY = "${DATES[1]}"`, c3);
  const g = run(c3, 'nearby', d);
  assert.deepEqual(rows(g), ['higher']);
  assert.equal(why(g, 'higher'), 'Different catchment.');
  assert.match(text(g), /Lower that day\./);
  // At a low spot, "Nearby" lists the nearest whatever their level, each with its reason, and no note.
  const lowHere = { ...d, days: d.days.map(x => ({ ...x, label: 'low', risk: 0.01 })), now: { ...d.now, label: 'low', risk: 0.01 } };
  const c4 = page([lowHere, same('a', 0.01), higher, plain]);
  const n = run(c4, 'nearby', lowHere);
  assert.match(text(n), /^Nearby /);
  assert.deepEqual(rows(n), ['a', 'higher', 'plain']);
  assert.doesNotMatch(n, /class="sub"/);
});
