const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync('src/dipcast/api/static/coverage.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

test('coastal search matches site names and reports the visible count', () => {
  let search;
  const input = {value:'', addEventListener: (_event, fn) => {search=fn;}};
  const count = {};
  const sites = ['Spittal', 'Saltburn'].map(name => ({querySelector: () => ({textContent:name})}));
  vm.runInNewContext(script, {document: {getElementById: id => id === 'coastal-search' ? input : id === 'coastal-count' ? count : null,
    querySelectorAll: selector => selector === '.coastal-site' ? sites : []}, Date, setInterval() {}});
  input.value = ' SPITT '; search();
  assert.deepEqual(sites.map(s => s.hidden), [false,true]);
  assert.equal(count.textContent, '1 of 2 sites');
  input.value = 'unlisted'; search();
  assert.equal(count.textContent, '0 of 2 sites');
  input.value = ''; search();
  assert.deepEqual(sites.map(s => s.hidden), [false,false]);
});

test('expired official advice is replaced on opening and while the page stays open', () => {
  let tick, clock = Date.parse('2026-09-16T08:29:00+01:00');
  const rows = ['2026-09-16T08:29:00+01:00','2026-09-17T08:29:00+01:00']
    .map(expires => ({dataset:{adviceExpires:expires}, textContent:'At snapshot: no increased risk'}));
  vm.runInNewContext(script, {document: {getElementById: () => null,
    querySelectorAll: selector => selector === '.coastal-site' ? [] : rows},
    Date:{now:()=>clock,parse:Date.parse}, setInterval: fn => {tick=fn;}});
  assert.match(rows[0].textContent, /expired/);
  assert.match(rows[1].textContent, /no increased risk/);
  clock += 86400000; tick();
  assert.match(rows[1].textContent, /expired/);
});

// Wales: the page asks NRW for current samples and forecasts when the list is opened (wales.py).
const T = s => Date.parse(s);
function walesContext(extra = {}) {
  const ctx = {document: {getElementById: () => null, querySelectorAll: () => []}, setInterval() {}, ...extra};
  vm.runInNewContext(script, ctx);
  return ctx;
}
const forecast = (key, level, day, expires, published = `${day}T08:30:11`) => ({
  stp_bathingWater: `http://environment.data.gov.uk/wales/bathing-waters/id/bathing-water/${key}`,
  riskLevel: `http://environment.data.gov.uk/def/bwq-stp/${level}`, predictedOn: {_value: day},
  predictedAt: {_value: `${day}T08:30:00`}, publishedAt: {_value: published}, expiresAt: {_value: expires}});

test('NRW times have no zone and are read as UK time, in summer and winter', () => {
  const c = walesContext();
  assert.equal(c.ukTime('2026-09-30T08:30:00'), T('2026-09-30T08:30:00+01:00'));
  assert.equal(c.ukTime('2026-12-01T08:30:00'), T('2026-12-01T08:30:00Z'));
  assert.ok(Number.isNaN(c.ukTime('yesterday')) && Number.isNaN(c.ukTime(undefined)));
  assert.equal(c.ukWhen(T('2026-09-11T10:53:00+01:00')), '11 Sep 2026, 10:53');   // as wales.py and coastal.py write it
});

test('only a forecast in force counts; expired, future, wrong-day, unknown and conflicting ones do not', () => {
  const c = walesContext(), now = T('2026-09-30T12:00:00+01:00');
  const got = c.walesForecasts([
    forecast('ukl1403-38300', 'increased', '2026-09-30', '2026-10-01T08:29:59'),
    forecast('ukl1403-38301', 'normal', '2021-05-21', '2021-05-22T08:29:59'),                          // Llandudno West Shore, still listed on 3 Oct 2026
    forecast('ukl1403-38302', 'normal', '2026-09-30', '2026-10-01T08:29:59', '2026-09-30T13:00:00'),   // published after now
    {...forecast('ukl1403-38303', 'normal', '2026-09-30', '2026-10-01T08:29:59'), predictedOn: {_value: '2026-09-29'}},   // predictedOn is not its prediction day
    forecast('ukl1403-38304', 'unknown', '2026-09-30', '2026-10-01T08:29:59'),
    forecast('ukl1403-38305', 'normal', '2026-09-30', '2026-10-01T08:29:59'),
    forecast('ukl1403-38305', 'increased', '2026-09-30', '2026-10-01T08:29:59', '2026-09-30T09:00:00'),
    forecast('ukl1403-38306', 'normal', '2026-09-30', '2026-10-03T08:29:59'),                          // longer than 36 hours
    {riskLevel: 'increased'}, null], now);
  assert.deepEqual([...got.keys()].sort(), ['ukl1403-38300', 'ukl1403-38305']);
  assert.equal(got.get('ukl1403-38300').level, 'increased');
  assert.equal(got.get('ukl1403-38305').conflict, true);
  assert.equal(c.walesForecasts([forecast('ukl1403-38300', 'increased', '2026-09-30', '2026-10-01T08:29:59')], T('2026-10-01T08:30:00+01:00')).size, 0);
});

function row(id, sampleAt) {
  const parts = {'.wales-sample': {textContent: 'snapshot sample'}, '.wales-advice': {textContent: 'Current NRW forecast: open the profile', dataset: {}}};
  return {dataset: {site: id, ...(sampleAt ? {sampleAt} : {})}, querySelector: q => parts[q], parts};
}

test('the rows get the newer sample and the forecast in force, and say when none is', () => {
  const c = walesContext(), now = T('2026-09-30T12:00:00+01:00');
  const rows = [row('ukl1403-38300', '2026-09-09T11:53:00+01:00'), row('ukl1403-38301', '2026-09-20T10:00:00+01:00'), row('ukl1403-38302')];
  const samples = c.walesSamples([
    {bwq_bathingWater: {eubwidNotation: 'ukl1403-38300'}, sampleDateTime: {inXSDDateTime: {_value: '2026-09-18T10:36:00'}},
     escherichiaColiCount: 1200, escherichiaColiQualifier: {countQualifierNotation: '='}, intestinalEnterococciCount: 10, intestinalEnterococciQualifier: {countQualifierNotation: '<'}},
    {bwq_bathingWater: {eubwidNotation: 'ukl1403-38301'}, sampleDateTime: {inXSDDateTime: {_value: '2026-09-02T10:00:00'}}, escherichiaColiCount: 50},
    {bwq_bathingWater: {eubwidNotation: 'ukl1403-38302'}, sampleDateTime: {inXSDDateTime: {_value: '2026-09-02T10:00:00'}}, escherichiaColiCount: -1}]);
  const n = c.walesApply(rows, samples, c.walesForecasts([forecast('ukl1403-38300', 'increased', '2026-09-30', '2026-10-01T08:29:59')], now));
  assert.equal(n, 1);
  assert.equal(rows[0].parts['.wales-sample'].textContent, 'Latest NRW sample 18 Sep 2026, 10:36: E. coli 1,200, intestinal enterococci <10 per 100 ml');
  assert.equal(rows[1].parts['.wales-sample'].textContent, 'snapshot sample');   // NRW's answer is older than the snapshot's
  assert.equal(rows[2].parts['.wales-sample'].textContent, 'snapshot sample');   // a negative count is not a sample
  assert.equal(rows[0].parts['.wales-advice'].textContent, 'NRW: increased pollution risk, until 1 Oct 2026, 08:29');
  assert.equal(rows[0].parts['.wales-advice'].dataset.adviceSource, 'NRW');
  assert.equal(rows[0].parts['.wales-advice'].dataset.adviceExpires, new Date(T('2026-10-01T08:29:59+01:00')).toISOString());
  assert.equal(rows[1].parts['.wales-advice'].textContent, 'No current NRW forecast for this site');
});

test('opening the list asks NRW once; a failure keeps the snapshot and says forecasts are unavailable', async () => {
  const rows = [row('ukl1403-38300')], status = {textContent: ''}, asked = [];
  let toggle; const details = {open: false, addEventListener: (_e, fn) => { toggle = fn; }, removeEventListener: () => { toggle = null; }};
  const doc = {getElementById: id => ({'wales-status': status, 'wales-directory': details})[id] || null,
    querySelectorAll: q => q === '.wales-site' ? rows : []};
  const fail = async url => { asked.push(url); return {ok: false, status: 403}; };
  walesContext({document: doc, fetch: fail, AbortSignal: {timeout: () => undefined}});
  details.open = true; toggle();
  assert.equal(toggle, null);   // asked once, not on every toggle
  await new Promise(r => setImmediate(r));
  assert.equal(asked.length, 2);
  assert.ok(asked.every(u => u.startsWith('https://environment.data.gov.uk/wales/bathing-waters/doc/bathing-water-quality/')));
  assert.match(status.textContent, /did not answer/);
  assert.equal(rows[0].parts['.wales-advice'].textContent, 'Current NRW forecast unavailable: open the profile');
  assert.equal(rows[0].parts['.wales-sample'].textContent, 'snapshot sample');
});

test('an expired NRW forecast is replaced while the page stays open, naming NRW', () => {
  let clock = T('2026-10-01T08:00:00+01:00'), tick;
  const advice = {dataset: {adviceExpires: '2026-10-01T07:29:59.000Z', adviceSource: 'NRW'}, textContent: 'NRW: increased pollution risk'};
  vm.runInNewContext(script, {document: {getElementById: () => null, querySelectorAll: q => q === '[data-advice-expires]' ? [advice] : []},
    Date: {now: () => clock, parse: Date.parse}, setInterval: fn => { tick = fn; }});
  assert.match(advice.textContent, /increased/);
  clock = T('2026-10-01T08:30:00+01:00'); tick();
  assert.equal(advice.textContent, 'This NRW advice has expired; check the official profile');
});
