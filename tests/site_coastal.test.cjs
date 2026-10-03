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
  vm.runInNewContext(script, {document: {getElementById: id => id === 'coastal-search' ? input : count,
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
