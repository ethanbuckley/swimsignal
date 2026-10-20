const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// The access note is a row of Not known here (index.html, accessSaid and unknowns) since 20 Oct 2026, not a
// paragraph under the five days (check).
test('access notes escape text and refuse executable source links', () => {
  const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
  const source = page.slice(page.indexOf('const check = d =>'), page.indexOf('// "; poor every year'));
  const ctx = vm.createContext({level: () => 'low', plainLevel: () => false, eaUnchecked: () => false,
    esc: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;')});
  vm.runInContext(source + ';globalThis.said = accessSaid; globalThis.check = check;', ctx);
  const access = {text: '<img onerror="bad">', url: 'javascript:bad', checked_at: '2026-10-03'};
  const html = ctx.said(access);
  assert.ok(html.includes('&lt;img') && !html.includes('<img') && !html.includes('javascript:'));
  assert.ok(html.includes('current signs have not been inspected'));
  assert.ok(ctx.said({...access, url: 'https://www.oxford.gov.uk/x'}).includes('<a href="https://www.oxford.gov.uk/x">Authority guidance</a>.'));
  assert.ok(!ctx.check({source: 'openstreetmap', access}).includes('Desk check'));   // no longer under the five days
});
