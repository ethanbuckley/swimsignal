const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('access notes escape text and refuse executable source links', () => {
  const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
  const source = page.slice(page.indexOf('const check = d =>'), page.indexOf('// "; poor every year'));
  const ctx = vm.createContext({level: () => 'low', plainLevel: () => false,
    esc: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;')});
  vm.runInContext(source + ';globalThis.render = check;', ctx);
  const html = ctx.render({access: {text: '<img onerror="bad">', url: 'javascript:bad', checked_at: '2026-10-03'}});
  assert.ok(html.includes('&lt;img') && !html.includes('<img') && !html.includes('javascript:'));
  assert.ok(html.includes('current signs have not been inspected'));
});
