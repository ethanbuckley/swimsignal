// Pages that share levels.js take it from require() in Node and from its globals in a browser, through a
// list written out in each file. A name used but left off that list works in every Node test and is
// undefined in the browser: the event page for organisers drew nothing for any spot with overflows
// upstream (R.WEIGHT_SAID, 5 Nov 2026). Every R.name a file uses must be on its browser list.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const dir = path.join(__dirname, '../src/dipcast/site');
const shim = /const (\w+) = (?:typeof module === 'object' && module\.exports|node) \? require\('\.\/levels\.js'\)\s*:\s*\{([^}]*)\}/g;

test("each page's browser list of levels.js names has every name the page uses", () => {
  let checked = 0;
  for (const f of fs.readdirSync(dir).filter(n => n.endsWith('.js'))) {
    const src = fs.readFileSync(path.join(dir, f), 'utf8');
    for (const m of src.matchAll(shim)) {
      const have = new Set(m[2].replace(/\/\/.*$/gm, '').match(/\w+/g) || []);
      const used = new Set([...src.matchAll(new RegExp(`\\b${m[1]}\\.(\\w+)`, 'g'))].map(u => u[1]));
      assert.deepEqual([...used].filter(n => !have.has(n)), [], `${f}: used as ${m[1]}.name but not on its browser list`);
      checked++;
    }
  }
  assert.ok(checked >= 6, `found ${checked} lists`);
});

test('the names on those lists are globals of levels.js, as a browser loads it', () => {
  const vm = require('node:vm');
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(dir, 'levels.js'), 'utf8'), ctx);   // as a <script>: no module
  for (const f of fs.readdirSync(dir).filter(n => n.endsWith('.js'))) {
    for (const m of fs.readFileSync(path.join(dir, f), 'utf8').matchAll(shim)) {
      for (const n of m[2].replace(/\/\/.*$/gm, '').match(/\w+/g)) {
        assert.equal(vm.runInContext(`typeof ${n}`, ctx) !== 'undefined', true, `${f}: ${n} is not a global of levels.js`);
      }
    }
  }
});
