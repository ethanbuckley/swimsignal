// A phone's spot folds (index.html, phoneFolds): the line under each title names what the fold holds, from its
// sections' own headings, so it never promises a guide, a gauge or a map the spot has not got (29 Oct 2026).
// node --test tests/site_fold_said.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const i = html.indexOf('const foldSaid = '), src = html.slice(i, html.indexOf('\n', html.indexOf('\n', i) + 1));
const ctx = vm.createContext({}); vm.runInContext(src + '\nthis.foldSaid = foldSaid;', ctx);
const sec = h => ({ querySelector: () => (h === null ? null : { textContent: h }) });
const body = (...hs) => ({ children: hs.map(sec) });

test('the line is the headings the fold holds, three at most', () => {
  assert.equal(ctx.foldSaid(body('Where the risk comes from', 'Upstream', ' Forecast for\n today ')), 'Where the risk comes from · Upstream · Forecast for today');
  assert.equal(ctx.foldSaid(body('Latest readings', 'Practical guide', 'Know this spot?', 'Notes on a visit')), 'Latest readings · Practical guide · Know this spot? and more');
  assert.equal(ctx.foldSaid(body('Latest readings', null, 'Latest readings')), 'Latest readings');   // a section with no heading, a repeat
});

test('the folds carry no fixed line', () => {
  const folds = html.slice(html.indexOf('const FOLDS = ['), html.indexOf('];', html.indexOf('const FOLDS = [')));
  assert.doesNotMatch(folds, /practical guide|water level|the map/i);
  assert.match(html, /f\.querySelector\('\.fg-s'\)\.textContent = foldSaid\(f\.querySelector\('\.fold-body'\)\)/);
});
