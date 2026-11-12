// A lake spot's link to a local group's past water samples (index.html, localSamplesLine; build_site.write_waterhead,
// data/research/local-samples.json): who, how many and the latest date, never a count, and said to be past samples.
// node --test tests/site_local_samples.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, '..', 'src', 'dipcast', 'site', 'index.html'), 'utf8');
const between = (a, b) => { const i = page.indexOf(a), j = page.indexOf(b, i); assert.ok(i >= 0 && j > i, `${a} .. ${b}`); return page.slice(i, j); };
const ctx = vm.createContext({ esc: s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]) });
vm.runInContext(between('function localSamplesLine', 'const localSamplesHost') + ';this.localSamplesLine = localSamplesLine;', ctx);
const WET = { href: 'waterhead.html', place: 'Waterhead, Windermere', by: 'Ambleside Action for a Future', samples: 59, first: '2025-04-16', last: '2026-10-12' };

test("the line names who took them, how many and the latest date, and says they are past samples", () => {
  assert.equal(ctx.localSamplesLine(WET), '<a href="waterhead.html">Local water samples, 2025 to 2026</a>: 59 samples taken at '
    + "Waterhead, Windermere by Ambleside Action for a Future, the latest on 12 Oct 2026. Past samples, not today's water.");
});

test('nothing is said without a page, dates or samples, and an odd link is refused', () => {
  assert.equal(ctx.localSamplesLine(null), '');
  assert.equal(ctx.localSamplesLine({ ...WET, samples: 0 }), '');
  assert.equal(ctx.localSamplesLine({ ...WET, last: '' }), '');
  assert.equal(ctx.localSamplesLine({ ...WET, href: 'javascript:alert(1)' }), '');
  assert.equal(ctx.localSamplesLine({ ...WET, href: 'https://example.org/x.html' }), '');
});

test('in the page: after the lake temperatures, on a phone too, and asked for on a spot page', () => {
  assert.match(page, /\+ lakeTempHost\(d\) \+ localSamplesHost\(d\);/);
  assert.match(page, /'#now-tiles', '#lt-past', '#ls-past', '#seasonal'/);   // after the readings; the day's tiles moved up (PHONE_EARLY, 5 Nov 2026)
  assert.match(page, /lakeTempFor\(d\); localSamplesFor\(d\);/);
});

// 12 Nov 2026: the other listed spots on the samples' water body link them too, and say they are from elsewhere.
test('a spot elsewhere on the same water body says so, with how far, and claims nothing about its own water', () => {
  const line = ctx.localSamplesLine({ ...WET, elsewhere: true, km: 4.6 });
  assert.equal(line, '<a href="waterhead.html">Local water samples elsewhere on this lake, 2025 to 2026</a>: 59 samples taken at '
    + 'Waterhead, Windermere, about 4.6&nbsp;km from here, by Ambleside Action for a Future, the latest on 12 Oct 2026. '
    + "Past samples from another part of the lake, not this spot's water.");
  assert.equal(ctx.localSamplesLine({ ...WET, elsewhere: true }), '');          // no distance: nothing said
  assert.equal(ctx.localSamplesLine({ ...WET, elsewhere: true, km: 'x' }), '');
  assert.doesNotMatch(line, /\b(safe|clean)\b/i);
});
