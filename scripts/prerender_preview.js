// The redesign's pages with their words in the HTML (src/dipcast/site/preview/; build_site.write_preview): the
// opening, and each place's page at spot/<id>/. The words are the page's own: this runs preview/app.js, with
// model.js and the live site's rules it loads, in Node, on this build's data, as at the moment the forecast was
// issued. The page's script then draws the same markup in the same place, so nothing moves.
//
//   node scripts/prerender_preview.js site/ out.json [home]     (- for stdout)
//
// site/ holds data/spots-lite.json, data/spot/<id>.json, data/upstream/<id>.json, data/research/figures.json and
// preview/hero-photos.json, as the build has written them by then. home is where the pages are under the site's root: "preview/" (the default)
// while they are a preview, "" when they are the site's own pages; every link in what is drawn starts with it.
// out.json is {home: html, spots: {id: html}}.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.join(__dirname, '..', 'src', 'dipcast', 'site');
// The page's scripts, in the page's order (preview/index.html), but for the two that only a browser can run: the
// map and the alerts. Nothing drawn here calls them.
const SCRIPTS = ['levels.js', 'eatoday.js', 'experience.js', 'lists.js', 'plan.js', 'preview/model.js', 'preview/app.js'];

// What the page's code expects of a browser that has stored nothing and is asked for nothing: an element that
// holds what is put in it, no saved places, no position, and the clock stopped at the time the forecast was issued.
function context(issuedAt, home) {
  const el = () => ({ innerHTML: '', textContent: '', dataset: {}, addEventListener() {}, setAttribute() {}, hasAttribute: () => false, prepend() {},
    querySelector: () => null, querySelectorAll: () => [], contains: () => false });
  const store = { getItem: () => null, setItem() {}, removeItem() {} };
  const document = { baseURI: 'https://build.invalid/', documentElement: { dataset: { home } }, head: el(), activeElement: null, addEventListener() {},
    getElementById: () => el(), querySelector: () => null, createElement: () => el() };
  const ctx = vm.createContext({ console, URL, URLSearchParams, Intl, setTimeout, clearTimeout, document, localStorage: store, sessionStorage: store,
    location: new URL(document.baseURI), history: { state: null, replaceState() {}, pushState() {} }, navigator: {}, addEventListener() {},
    matchMedia: () => ({ matches: false }), fetch: () => Promise.reject(new Error('no network at build')) });
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${issuedAt};`, ctx);
  for (const f of SCRIPTS) vm.runInContext(fs.readFileSync(path.join(SRC, f), 'utf8'), ctx, { filename: f });
  return ctx;
}

// "Issued 13:21, 0 min ago" loses its age, which would be wrong by the time the page is read; the script puts it back.
const ageless = html => html.replace(/(Issued [^<,]+), \d+ (?:min|h|days) ago/g, '$1');

const readJson = file => { try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (e) { return null; } };

function prerender(site, home = 'preview/') {
  const data = readJson(path.join(site, 'data', 'spots-lite.json'));
  if (!data || !Array.isArray(data.spots) || !Number.isFinite(Date.parse(data.generated_at))) throw new Error('no data/spots-lite.json with an issue time');
  const ctx = context(Date.parse(data.generated_at), home);
  ctx.IN = { data, hero: readJson(path.join(site, 'preview', 'hero-photos.json')) || {}, figs: readJson(path.join(site, 'data', 'research', 'figures.json')) };
  vm.runInContext('PVBuilt.load(IN.data, IN.hero, IN.figs);', ctx);
  const out = { home: ageless(vm.runInContext('PVBuilt.home()', ctx)), spots: {} };
  for (const s of data.spots) {
    if (!/^[A-Za-z0-9_-]+$/.test(String(s.id))) continue;
    const detail = s.detail_file && !String(s.detail_file).includes('..') ? readJson(path.join(site, 'data', s.detail_file)) : null;
    const up = readJson(path.join(site, 'data', 'upstream', `${s.id}.json`));
    ctx.IN = { id: s.id, files: { detail, up: up && Array.isArray(up.overflows) ? up.overflows : null } };
    out.spots[s.id] = ageless(vm.runInContext('PVBuilt.place(IN.id, IN.files)', ctx));
  }
  return out;
}

if (require.main === module) {
  const [site, dst, home] = process.argv.slice(2);
  if (!site || !dst || (home !== undefined && home !== '' && !/^[a-z]+\/$/.test(home))) { console.error('usage: node scripts/prerender_preview.js <site dir> <out.json, or - for stdout> [home: "preview/" or ""]'); process.exit(2); }
  const json = JSON.stringify(prerender(site, home === undefined ? 'preview/' : home));
  if (dst === '-') process.stdout.write(json); else fs.writeFileSync(dst, json);
}

module.exports = { prerender, ageless };
