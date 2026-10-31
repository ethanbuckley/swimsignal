// Open a list from a link, on the Saved page (26 October 2026, a phone-journey audit). The Home Screen
// app on an iPhone has no address bar and keeps its own storage, so a list sent to someone, or copied
// in Safari, could not be opened there at all. The page's own renderSaved, listsCard, the form and
// renderShared run here in a small stand-in for the browser, with lists.js; what they draw, and what
// a paste does, is checked.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const dir = 'src/dipcast/site/';
const page = fs.readFileSync(dir + 'index.html', 'utf8');
const between = (a, b) => { const i = page.indexOf(a), j = page.indexOf(b, i); assert.ok(i >= 0 && j > i, `${a} .. ${b}`); return page.slice(i, j); };

const SPOTS = [{id: 'osm-windermere-waterhead', name: 'Windermere, Waterhead', lat: 54.42, lon: -2.96},
  {id: 'bw-ukd1203-45650', name: 'Windermere, Millerground', lat: 54.38, lon: -2.92}];
const LINK = 'https://swimsignal.co.uk/saved/#list=Windermere&spots=osm-windermere-waterhead,bw-ukd1203-45650';

function savedPage({standalone = true} = {}) {
  const els = {}, calls = [];
  const el = id => ({id, value: '', textContent: '', innerHTML: '', on: {}, focused: false,
    addEventListener(k, f) { this.on[k] = f; }, focus() { this.focused = true; }});
  const loc = {origin: 'https://swimsignal.co.uk', pathname: '/saved/', hash: ''};
  const go = url => { const u = new URL(url, loc.origin); loc.pathname = u.pathname; loc.hash = u.hash; };
  const ctx = vm.createContext({
    console, URL, navigator: {standalone}, location: loc,
    history: {state: null, pushState(s, t, url) { calls.push(['push', url]); go(url); }, replaceState(s, t, url) { calls.push(['replace', url]); go(url); }},
    document: {title: '', getElementById: id => els[id] || null, querySelector: () => null, querySelectorAll: () => []},
    setPanel: h => { ctx.panel = h; for (const k of Object.keys(els)) delete els[k]; for (const m of h.matchAll(/ id="([^"]+)"/g)) els[m[1]] = el(m[1]); },
    keepPlace: () => calls.push(['keepPlace']), scrollTop: () => {}, focusHeading: () => calls.push(['focusHeading']),
  });
  for (const f of ['experience.js', 'lists.js']) vm.runInContext(fs.readFileSync(dir + f, 'utf8'), ctx, {filename: f});
  vm.runInContext(`
    let shown = null, current = null, LISTS = readLists(null, null);
    const DATA = {spots: ${JSON.stringify(SPOTS)}, push: {url: 'https://push.invalid/'}}, BRAND = 'SwimSignal', ROOT = new URL('https://swimsignal.co.uk/');
    const savedPath = () => ROOT.pathname + 'saved/', sitesURL = () => 'sites.html', IN_APP = '', IOS = true;
    const SAVED = {get size() { return allSaved(LISTS).length; }, has: id => allSaved(LISTS).includes(id)};
    const setLists = s => { LISTS = s; return true; }, listNow = () => shownList(LISTS), manyLists = () => LISTS.lists.length > 1;
    const listSpots = l => l.spots.map(id => DATA.spots.find(s => s.id === id)).filter(Boolean);
    const none = () => '', nothing = () => {}, contribLayer = {clearLayers: nothing}, selLayer = contribLayer;
    const L = {circleMarker: () => ({addTo: nothing}), latLngBounds: nothing}, map = {fitBounds: nothing}, PHONE = {matches: true};
    const setView = nothing, planDates = () => [], notices = none, bestDayNote = none, savedGrid = none, issued = none, ago = none, agoSpan = none, ageMin = none;
    const swimsShown = () => false, compareSection = none, savedCompare = none, alertsCard = none, swimsCard = none, cols = h => h, solo = h => h;
    const bindBack = nothing, bindSavedPage = nothing, bindLists = nothing, bindAlerts = nothing, bindComparison = nothing, bindBestDay = nothing;
    const bindSwims = nothing, bindToAlerts = nothing, bindFind = nothing, placeMap = nothing, plainClick = () => true, select = nothing;
    const RING = none, MOTION = () => ({}), dayName = d => d;
    const savedCard = s => '<li class="scard">' + esc(s.name) + '</li>';
    ${between('const esc =', '\nconst fmt')}
    ${between('const LISTS_UI =', 'function bindToAlerts(')}
    ${between('function listsCard(', 'function bindLists(')}
    ${between('const importForm =', '// A list someone shared')}
    ${between('function renderShared(', 'function openSaved(')}
    this.renderSaved = renderSaved; this.lists = () => LISTS;`, ctx);
  const paste = text => { els['ls-import-link'].value = text; els['ls-import'].on.submit({preventDefault() {}}); };
  return {ctx, els, calls, loc, paste};
}

test('with nothing saved, the Saved page has the form on a tile of its own, and the Home Screen app points to it', () => {
  const p = savedPage();
  p.ctx.renderSaved();
  const h = p.ctx.panel;
  assert.match(h, /<details class="sec tile lists"><summary>Open a shared list<\/summary><form class="lists-form" id="ls-import"><label for="ls-import-link">Open a list from a link<\/label>/);
  assert.equal(h.match(/id="ls-import"/g).length, 1);
  assert.match(page, /\.tile > \.lists-form:first-child \{ margin:0; padding:0; border-top:0; \}/);   // no rule above it on its own tile
  assert.doesNotMatch(h, /id="lists"/);   // Your lists waits for something to put in a list
  assert.match(h, /iPhones keep the two apart, so save them again here, or paste a list's link below\./);
  assert.match(h, /Paste a link to a list, sent to you or copied with Share this list in Safari, to see it and add it here\./);
  // A plain text box: a browser's own check of a web address never stops the paste, and the phone's keyboard is the one for addresses.
  assert.match(h, /<input type="text" id="ls-import-link" inputmode="url" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" maxlength="8000" enterkeyhint="go"/);
  assert.match(h, /<button type="submit" class="btn">Open<\/button><\/div><p class="small muted msg" id="ls-import-msg" role="status"><\/p><\/form>/);
  // In a browser, no word of Safari or the Home Screen.
  const b = savedPage({standalone: false});
  b.ctx.renderSaved();
  assert.match(b.ctx.panel, /copied with Share this list, to see it/);
  assert.doesNotMatch(b.ctx.panel, /paste a list's link below/);
});

test('a paste that is not a list says why, as text, and goes nowhere', () => {
  const p = savedPage();
  p.ctx.renderSaved();
  const cases = [['', 'Paste a link to a SwimSignal list first.'], ['Windermere <img src=x onerror=alert(1)>', 'That is not a link. Paste the whole link, starting https://.'],
    ['https://example.com/saved/#list=W&spots=a', 'That is a link to another website, not SwimSignal.'],
    ['https://swimsignal.co.uk/spot/grasmere/', "That link has no list of spots in it. A list's link has saved/#list= in it."],
    ['https://swimsignal.co.uk/saved/#spots=' + 'a'.repeat(8000), 'That is too long to be a link to a list.']];
  for (const [text, said] of cases) {
    p.els['ls-import-link'].focused = false;
    p.paste(text);
    assert.equal(p.els['ls-import-msg'].textContent, said, text);
    assert.equal(p.els['ls-import-msg'].innerHTML, '');   // written as text, never as markup
    assert.ok(p.els['ls-import-link'].focused, 'the box has the focus again, to paste once more');
  }
  assert.deepEqual(p.calls, []);
  assert.equal(p.loc.hash, '');
});

test('a list\'s link opens the shared list, which adds it once and then says it is there already', () => {
  const p = savedPage();
  p.ctx.renderSaved();
  p.paste(`  ${LINK}\n`);
  assert.equal(JSON.stringify(p.calls), JSON.stringify([['keepPlace'], ['push', '/saved/#list=Windermere&spots=osm-windermere-waterhead,bw-ukd1203-45650'], ['focusHeading']]));
  assert.match(p.ctx.panel, /<h1 class="page-h" tabindex="-1">Windermere<\/h1><p class="lede">Someone shared this list of 2 spots with you\./);
  assert.match(p.ctx.panel, /<button type="button" class="btn primary" id="sh-add">Add to my lists<\/button>/);
  assert.match(p.ctx.panel, /Windermere, Waterhead<\/li><li class="scard">Windermere, Millerground/);
  // Added, it takes the place of a first visit's empty "My spots" (lists.js addSharedList, #369), and the
  // address is the Saved page's again.
  p.els['sh-add'].on.click();
  assert.equal(JSON.stringify(p.ctx.lists().lists.map(l => [l.name, l.spots])), JSON.stringify([['Windermere', ['osm-windermere-waterhead', 'bw-ukd1203-45650']]]));
  assert.equal(p.loc.hash, '');
  // Now something is saved: the form is in Your lists, and not on a tile of its own.
  assert.match(p.ctx.panel, /<details class="sec tile lists" id="lists">[\s\S]*id="ls-new"[\s\S]*<form class="lists-form" id="ls-import">[\s\S]*id="lists-msg"/);
  assert.doesNotMatch(p.ctx.panel, /<section class="sec tile lists">/);
  // The same link again: no second copy, but "It is in your lists already".
  p.paste(LINK);
  assert.match(p.ctx.panel, /It is in your lists already, as Windermere\. <button type="button" class="linkbtn small" id="sh-show">Show it<\/button>/);
  assert.doesNotMatch(p.ctx.panel, /id="sh-add"/);
  assert.equal(p.ctx.lists().lists.length, 1);
  // A name with markup in it is shown as text.
  p.els['sh-show'].on.click();
  p.paste('https://swimsignal.co.uk/saved/#list=%3Cb%3EHi%3C%2Fb%3E&spots=osm-windermere-waterhead');
  assert.match(p.ctx.panel, /<h1 class="page-h" tabindex="-1">&lt;b&gt;Hi&lt;\/b&gt;<\/h1>/);
});

test('the form is bound with the Saved page\'s other parts', () => {
  assert.match(between('function renderSaved(', 'function bindToAlerts('), /bindLists\(l\); bindImport\(\);/);
});

test('the first-save action precedes secondary tools on an empty Saved page', () => {
  const p = savedPage();
  p.ctx.renderSaved();
  const h = p.ctx.panel;
  assert.ok(h.indexOf('id="find"') < h.indexOf('<summary>Swim journal</summary>'));
  assert.ok(h.indexOf('id="find"') < h.indexOf('Open a shared list'));
  assert.match(h, /<details class="sec tile lists"><summary>Open a shared list<\/summary>/);
});
