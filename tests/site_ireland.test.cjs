// The coverage page's search over the Irish lists (ireland.py, northern_ireland.py): accents and
// apostrophes do not count, so a reader without an Irish keyboard finds "Trá Mór".
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync('src/dipcast/api/static/coverage.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

function list(searchId, countId, selector, names) {
  let search;
  const input = {value: '', addEventListener: (_event, fn) => { search = fn; }};
  const count = {};
  const sites = names.map(name => ({querySelector: () => ({textContent: name})}));
  vm.runInNewContext(script, {document: {getElementById: id => id === searchId ? input : id === countId ? count : null,
    querySelectorAll: s => s === selector ? sites : []}, Date, setInterval() {}});
  return {find: term => { input.value = term; search(); return sites.filter(s => !s.hidden).length; }, count, sites};
}

test('a search without accents finds Irish names, and one with them still does', () => {
  const l = list('ireland-search', 'ireland-count', '.ireland-site',
    ['An Trá Mór, Coill Rua, Indreabhán', 'Trá na mBan, An Spidéal', 'Oileán Chléire', 'Loughrea Lake']);
  assert.equal(l.find('tra mor'), 1);
  assert.equal(l.find('Trá'), 2);
  assert.equal(l.find('SPIDEAL'), 1);
  assert.equal(l.find('oilean chleire'), 1);
  assert.equal(l.count.textContent, '1 of 4 sites');
  assert.equal(l.find(''), 4);
});

test("Northern Irish names match with or without the apostrophe, straight or curly", () => {
  const l = list('ni-search', 'ni-count', '.ni-site', ["Rea's Wood", 'Brown’s Bay', 'Portrush Curran (East Strand)']);
  assert.equal(l.find('reas wood'), 1);
  assert.equal(l.find("Brown's"), 1);
  assert.equal(l.find('browns bay'), 1);
  assert.equal(l.find('east strand'), 1);
  assert.equal(l.count.textContent, '1 of 3 sites');
});
