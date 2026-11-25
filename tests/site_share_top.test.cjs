// Share beside Save at the top of a spot's page (17 Nov 2026): the same link as "Share this spot" at the foot.
// node --test tests/site_share_top.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const src = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>'));
const fn = name => { const i = src.indexOf(`function ${name}(`); assert.ok(i >= 0, name);
  return src.slice(i, src.indexOf('\n}\n', i) + 3); };

test('the button follows Save in the top row, is named for a reader, and is drawn from the stroke set', () => {
  assert.match(src, /\$\{saveButton\(d\)\}\$\{SHARE_TOP\}<\/div>`;/);
  const b = vm.runInNewContext(src.slice(src.indexOf('const SHARE_TOP ='), src.indexOf('</button>\';', src.indexOf('const SHARE_TOP =')) + 11) + '\nSHARE_TOP');
  assert.match(b, /^<button type="button" class="save share-top" id="share-top" aria-label="Share this spot"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true">.*<\/svg><span>Share<\/span><\/button>$/);
  assert.match(html, /\.top-row \.save:not\(\.share-top\) \{ margin-left:auto; \}/);
  assert.match(html, /@media \(max-width:399px\) \{ \.share-top > span \{ display:none; \} \}/);
});

function run({ touch, day = null, fail = false }) {
  const els = { share: { textContent: 'Copy link to this spot' }, 'share-top': {}, 'share-msg': { textContent: '' }, 'save-msg': { textContent: '' } };
  const clicks = {}, shared = [], copied = [];
  for (const id of ['share', 'share-top']) els[id].addEventListener = (_e, f) => { clicks[id] = f; };
  const nav = { clipboard: { writeText: async u => { if (fail) throw new Error('no'); copied.push(u); } } };
  if (touch) nav.share = async o => { shared.push(o); };
  const ctx = vm.createContext({ document: { getElementById: id => els[id] || null }, matchMedia: () => ({ matches: touch }), navigator: nav,
    location: { origin: 'https://swimsignal.co.uk' }, URL, spotPath: id => `/swim/${id}/`, DAY: day, BRAND: 'SwimSignal', dayName: () => 'Friday' });
  vm.runInContext(fn('bindShare') + '\nbindShare({ id: "wharfe-ilkley", name: "Wharfe at Ilkley" });', ctx);
  return { els, clicks, shared, copied };
}

test('on a phone both buttons open the share sheet with the spot\'s own page', async () => {
  const r = run({ touch: true });
  assert.equal(r.els.share.textContent, 'Share this spot');
  await r.clicks['share-top'](); await r.clicks.share();
  assert.equal(r.shared.length, 2);
  for (const s of r.shared) assert.deepEqual({ ...s }, { title: 'Wharfe at Ilkley · SwimSignal', url: 'https://swimsignal.co.uk/swim/wharfe-ilkley/' });
});

test('on a desktop the top button copies the link and says so under Save; the foot button says so under itself', async () => {
  const r = run({ touch: false, day: '2026-11-20' });
  await r.clicks['share-top']();
  assert.deepEqual(r.copied, ['https://swimsignal.co.uk/swim/wharfe-ilkley/#day=2026-11-20']);
  assert.equal(r.els['save-msg'].textContent, "Link to Friday's forecast copied.");
  assert.equal(r.els['share-msg'].textContent, '');
  await r.clicks.share();
  assert.equal(r.els['share-msg'].textContent, "Link to Friday's forecast copied.");
});

test('where the clipboard is refused the link itself is shown', async () => {
  const r = run({ touch: false, fail: true });
  await r.clicks['share-top']();
  assert.equal(r.els['save-msg'].textContent, 'https://swimsignal.co.uk/swim/wharfe-ilkley/');
});
