// A postcode typed into the home page's search says why nothing matched (17 Nov 2026), as Plan a swim does.
// node --test tests/site_postcode_said.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const dir = path.join(__dirname, '../src/dipcast/site/');
const html = fs.readFileSync(dir + 'index.html', 'utf8');
const def = html.slice(html.indexOf('const noMatchLead ='), html.indexOf('// Near me: a pin at the end of the search field'));

test('a postcode gets the reason; anything else the plain words', () => {
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(dir + 'plan.js', 'utf8'), ctx);
  const lead = vm.runInContext(def + '\nnoMatchLead', ctx);
  for (const q of ['OX1 4', 'ox1 4ab', 'LS29', 'M1 1AA', ' SW1A 1AA '])
    assert.equal(lead(q), 'Postcodes do not work here yet: type a town, a village or a river.', q);
  for (const q of ['Oxfrd', 'River Zzz', '', null, undefined, 'Ilkley']) assert.equal(lead(q), 'No inland forecasts match.', String(q));
});

test('without the planner\'s file the plain words stand', () => {
  assert.equal(vm.runInNewContext(def + '\nnoMatchLead("OX1 4")'), 'No inland forecasts match.');
});

test('the list\'s empty row opens with it', () => {
  assert.match(html, /<li class="empty"><p class="below">\$\{noMatchLead\(VIEW\.q\)\} SwimSignal forecasts \$\{DATA\.spots\.length\} river and lake spots/);
});
