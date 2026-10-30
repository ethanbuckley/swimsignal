// How an outing's backup is joined to its spot by water (src/dipcast/site/outing.js, outingJoined, outingJoin,
// outingApart): the proposal of 30 Oct 2026 asked for backups that avoid the same pollution sources, and the
// spot page's Nearby card already says how two spots are joined (index.html, joined and nearWhy). The plan's
// outing tile now says it too, in the card's words, under the pair. The fixtures copy the live files of
// 30 Oct 2026: Windermere at Millerground and at Lakeside YMCA share overflows ("s" both ways in
// data/spot/<id>.json), and Coniston Water drains to another catchment.
// node --test tests/site_outing_join.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');
const O = require('../src/dipcast/site/outing.js');
L.setToday('2026-10-31');

const WINDERMERE = '5dd0721c', CONISTON = '8ae0c974';
const lake = (id, name, catchment, extra = {}) => ({id, name, kind: 'lake', river: null, catchment, detail_file: `spot/${id}.json`,
  upstream_summary: {overflows: 3}, ...extra});
const miller = (extra = {}) => lake('bw-ukd1203-45650', 'Windermere, Millerground Landing', WINDERMERE, extra);
const lakeside = (extra = {}) => lake('bw-ukd1203-45625', 'Windermere, Lakeside YMCA', WINDERMERE, {upstream_summary: {overflows: 2}, ...extra});
const monk = () => lake('bw-ukd1230-45775', 'Coniston Water, Monk Coniston', CONISTON, {upstream_summary: {overflows: 2}});
const loaded = linked => ({detail_loaded: true, linked});
const river = (id, extra = {}) => ({id, name: id, kind: 'river', river: 'River Thames', catchment: '6002834c', upstream_summary: {overflows: 45}, ...extra});

test('the relation, from either spot\'s file: shares, downstream, upstream, another branch, a different catchment', () => {
  const m = miller(loaded({'bw-ukd1203-45625': 's'}));
  assert.equal(O.outingJoined(m, lakeside()), 's');
  // The backup's file in first: read the other way round, so the backup's "u" (the spot is upstream of it) is "d".
  assert.equal(O.outingJoined(river('a'), river('b', loaded({a: 'u'}))), 'd');
  assert.equal(O.outingJoined(river('a'), river('b', loaded({a: 'd'}))), 'u');
  assert.equal(O.outingJoined(river('a', loaded({b: 'd'})), river('b')), 'd');
  // Same catchment, linked to neither, once a file is in: another branch.
  assert.equal(O.outingJoined(river('a', loaded({})), river('wey', {river: 'River Wey'})), 'branch');
  // A different catchment needs no file: the lite file's catchments differ.
  assert.equal(O.outingJoined(miller(), monk()), 'apart');
});

test('nothing is claimed while a shared overflow cannot be ruled out, or where either has no place on the network', () => {
  // Same catchment, neither file in yet: it may still be "s", so not "another branch".
  assert.equal(O.outingJoined(miller(), lakeside()), null);
  // A file that did not arrive settles nothing.
  assert.equal(O.outingJoined(miller({detail_missing: true}), lakeside({detail_missing: true})), null);
  // An isolated lake, or a forecast older than these fields.
  assert.equal(O.outingJoined(miller(loaded({})), lake('tarn', 'Loughrigg Tarn', undefined)), null);
  assert.equal(O.outingJoined({...miller(), catchment: undefined}, monk()), null);
  assert.equal(O.outingJoined(miller(), null), null);
  assert.equal(O.outingJoin(miller(), lake('tarn', 'Loughrigg Tarn', undefined)), '');
});

test('the line in the Nearby card\'s words, said of the backup', () => {
  const m = miller(loaded({'bw-ukd1203-45625': 's'}));
  assert.equal(O.outingJoin(m, lakeside()), 'Backup: shares overflows with your spot. At least one overflow upstream counts in both levels.');
  assert.equal(O.outingJoin(river('a', loaded({b: 's'})), river('b')),
    'Backup: same river, shares overflows with your spot. At least one overflow upstream counts in both levels.');
  assert.equal(O.outingJoin(river('a', loaded({b: 'd'})), river('b')), 'Backup: same river, further downstream. The forecast counts none of the same overflows.');
  assert.equal(O.outingJoin(river('a', loaded({b: 'u'})), river('b')), 'Backup: same river, further upstream. The forecast counts none of the same overflows.');
  // Not "same river" between a river and a lake; the counting only where both have overflows upstream.
  assert.equal(O.outingJoin(river('a', loaded({b: 'd'})), river('b', {kind: 'lake', river: null, upstream_summary: {overflows: 0}})), 'Backup: downstream of your spot.');
  assert.equal(O.outingJoin(river('a', loaded({})), river('wey', {river: 'River Wey'})), 'Backup: same catchment, another branch. It has overflows and runoff of its own.');
});

test('a different catchment gets a plain fact, never a reassuring word', () => {
  const said = O.outingJoin(miller(), monk());
  assert.equal(said, 'Backup: different catchment. It has overflows and runoff of its own.');
  assert.doesNotMatch(said, /safe|clean|clear|better|avoid|independent|unaffected|separate/i);
  assert.equal(O.outingJoin(miller(), {...monk(), upstream_summary: {overflows: 0}}), 'Backup: different catchment. It has runoff of its own.');
});

// ------------------------------------------------------------------------------ the tile
const col = (s, extra = {}) => ({id: s.id, name: s.name, href: `spot/${s.id}/`, tone: 'low', headline: 'Low risk tomorrow', meta: 'Lake', catchment: s.catchment, ...extra});
const tile = (main, alt, o = {}) => O.outingSection({day: '2026-11-01', when: '', spot: main.id, backup: alt && alt.id, groups: [], missing: [], issued: 'x', open: true,
  backupGroups: [['In this plan', [lakeside(), monk(), lake('tarn', 'Loughrigg Tarn', undefined)]]],
  main: col(main), alt: alt && col(alt), join: alt ? O.outingJoin(main, alt) : '', ...o});

test('the line sits just over the two columns, which run on through each spot\'s access guide below', () => {
  const h = tile(miller(loaded({'bw-ukd1203-45625': 's'})), lakeside());
  assert.match(h, /<p class="outing-said">[^<]*<\/p><p class="outing-join" id="outing-join">Backup: shares overflows with your spot\. At least one overflow upstream counts in both levels\.<\/p><div class="outing-pair">.*Your spot.*Backup/s);
  // Unknown yet: the element is there, empty, for the page to fill once a spot's file is in.
  assert.match(tile(miller(), lakeside()), /<p class="outing-join" id="outing-join"><\/p><div class="outing-pair">/);
  // No backup: no line.
  assert.doesNotMatch(tile(miller(), null), /outing-join/);
});

test('in the backup\'s list, the spots in another catchment than the spot\'s are marked; unknown ones are not', () => {
  const h = tile(miller(), monk());
  assert.match(h, /<option value="bw-ukd1230-45775" selected>Coniston Water, Monk Coniston, different catchment<\/option>/);
  assert.match(h, /<option value="bw-ukd1203-45625">Windermere, Lakeside YMCA<\/option>/);
  assert.match(h, /<option value="tarn">Loughrigg Tarn<\/option>/);
  // No spot chosen yet: nothing to compare with, so nothing marked.
  const none = O.outingSection({day: '2026-11-01', groups: [], missing: [], issued: 'x', open: true, main: null, alt: null,
    backupGroups: [['In this plan', [monk()]]]});
  assert.match(none, /<option value="bw-ukd1230-45775">Coniston Water, Monk Coniston<\/option>/);
  assert.equal(O.outingApart(null, monk()), false);
});
