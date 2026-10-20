// Paper (review F5): the app's print styles and the folds the page opens before printing, and the
// prose pages' print block in page.css.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const CSS = fs.readFileSync(path.join(__dirname, '../src/dipcast/api/static/page.css'), 'utf8');
// The @media print block of a stylesheet: from its opening brace to the matching close.
function printBlock(src) {
  const at = src.indexOf('@media print {');
  assert.ok(at >= 0, 'no @media print block');
  let depth = 0;
  for (let i = src.indexOf('{', at); i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}' && --depth === 0) return src.slice(at, i + 1);
  }
  throw new Error('unclosed @media print');
}
const hidden = block => block.match(/([^{}]+)\{\s*display:\s*none/g).join(' ');

test('the app prints without its header links, map, bottom bar, skip link or controls', () => {
  const css = printBlock(PAGE.match(/<style>([\s\S]*?)<\/style>/)[1]), off = hidden(css);
  for (const sel of ['.top nav', '.skip', '.bottom-nav', '#map-wrap', '.tile:has(#spot-map)', '.loc', '.actions', '.toolbar', '.search', '.chips-row', '.pick', '.btn'])
    assert.ok(off.includes(sel), `${sel} is not hidden in print`);
  // One column, not the desktop grid's scrolling panel, which prints one page and cuts off the rest.
  assert.match(css, /#panel \{[^}]*overflow:visible/);
  assert.match(css, /#app \{ display:block; \}/);
  assert.match(css, /html, body \{ height:auto; \}/);
  // The level marks are backgrounds: the panel asks the browser to keep them.
  assert.match(css, /#panel \{[^}]*print-color-adjust:exact/);
});

test('before printing, the folds open; afterwards the same ones shut, and the EA panel and settings stay shut', () => {
  const src = PAGE.match(/const PRINT_FOLDS = [^\n]+\nfunction openFoldsForPrint[\s\S]*?\n}\n/)[0];
  const ctx = {};
  vm.runInNewContext(src + 'this.PRINT_FOLDS = PRINT_FOLDS; this.openFoldsForPrint = openFoldsForPrint;', ctx);
  for (const not of ['.ea-today', '.consent', '.lists', '#your-data', '#home-screen'])
    assert.ok(ctx.PRINT_FOLDS.includes(`:not(${not})`), `${not} would be opened`);
  assert.ok(ctx.PRINT_FOLDS.includes(':not([open])'), 'a fold the reader opened would be shut afterwards');
  const folds = [{open: false}, {open: false}];
  let asked = '';
  const shut = ctx.openFoldsForPrint({querySelectorAll: sel => { asked = sel; return folds; }});
  assert.equal(asked, ctx.PRINT_FOLDS);
  assert.deepEqual(folds.map(d => d.open), [true, true]);
  shut();
  assert.deepEqual(folds.map(d => d.open), [false, false]);
  assert.match(PAGE, /addEventListener\('beforeprint'/);
  assert.match(PAGE, /addEventListener\('afterprint'/);
});

test('the prose pages print at the paper width, without the header links, and nothing cut off in a scrolling box', () => {
  const css = printBlock(CSS), off = hidden(css);
  assert.ok(off.includes('.top nav'));
  assert.ok(off.includes('details.ea-today'));
  assert.match(css, /main\.doc \{ max-width: none;/);
  assert.match(css, /\.tw, #coastal-sites[^{]*\{ overflow: visible; max-height: none; \}/);
  assert.match(css, /details::details-content \{ content-visibility: visible;/);
});

test('a five-day strip on a prose page (the sites view) keeps its colours on paper', () => {
  assert.match(printBlock(CSS), /\.week, \.wk \{ print-color-adjust: exact;/);
});
