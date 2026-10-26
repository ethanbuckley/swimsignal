// The next step after saving (25 October 2026, a phone-width walk through the Facebook post's link):
// what Save on a spot's page says, and where; the note after a shared list is added, which points to
// the alerts; and what Facebook's and Instagram's own browsers are told, since a link tapped in
// either app opens there, where push does not work and a saved list stays in that app.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const between = (a, b) => { const i = page.indexOf(a), j = page.indexOf(b, i); assert.ok(i >= 0 && j > i, `${a} .. ${b}`); return page.slice(i, j); };

// A small stand-in for the elements bindSave and bindToAlerts touch.
function el(id) {
  const on = {};
  return {id, innerHTML: '', textContent: '', attrs: {}, on, tabIndex: 0, focused: false, scrolled: null, removed: false,
    setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(k, f) { on[k] = f; },
    focus() { this.focused = true; }, scrollIntoView(o) { this.scrolled = o; }, remove() { this.removed = true; }};
}

function saveSetup({push = true, many = false, kept = true, phone = true, withSaveMsg = true} = {}) {
  const els = {save: el('save'), 'share-msg': el('share-msg'), 'save-go': el('save-go')};
  if (withSaveMsg) els['save-msg'] = el('save-msg');
  let opened = 0;
  const lists = {lists: many ? [{id: 'l1', name: 'My spots', spots: []}, {id: 'l2', name: 'Weekend & <Club>', spots: []}] : [{id: 'l1', name: 'Saved spots', spots: []}]};
  const ctx = vm.createContext({
    document: {getElementById: id => els[id] || null}, DATA: push ? {push: {url: 'https://push.invalid/'}} : {},
    LISTS: lists, listNow: () => lists.lists[many ? 1 : 0], manyLists: () => many, setLists: () => kept,
    addToList: x => x, removeFromList: x => x, saveLabel: on => (on ? 'Saved' : 'Save'), PHONE: {matches: phone},
    esc: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'), savedPath: () => '/saved/',
    plainClick: () => true, openSaved: () => { opened++; }});
  vm.runInContext(between('function bindSave(', 'function actions(') + ';this.bindSave = bindSave;', ctx);
  ctx.bindSave({id: 'spot'});
  return {els, click: () => els.save.on.click(), opened: () => opened};
}

test("Save says what it did under the button, not at the foot of the page", () => {
  // The empty line sits straight under the row with the back link and Save, before the notices.
  assert.match(page, /\$\{saveButton\(d\)\}<\/div>`;\n[^\n]*\n\s*h \+= '<p class="small muted save-msg" id="save-msg" aria-live="polite"><\/p>';\n\s*h \+= notices\(d\);/);
  assert.match(page, /\.save-msg:empty \{ margin:0; \}/);   // empty, it takes no room on the built page
  const s = saveSetup();
  s.click();
  assert.equal(s.els['share-msg'].innerHTML, '');
  assert.equal(s.els['save-msg'].innerHTML,
    'Saved on this device. Your saved spots are under <a href="/saved/" id="save-go">Saved</a>, in the bar at the bottom. There you can also set up alerts for them.');
  s.els['save-go'].on.click({preventDefault() {}});
  assert.equal(s.opened(), 1);   // the link opens the Saved view in place
});

test('the alerts sentence is there only where the site has alerts, and list names are escaped', () => {
  const none = saveSetup({push: false, phone: false});
  none.click();
  assert.equal(none.els['save-msg'].innerHTML, 'Saved on this device. Your saved spots are under <a href="/saved/" id="save-go">Saved</a>, at the top of the page.');
  const many = saveSetup({many: true});
  many.click();
  assert.match(many.els['save-msg'].innerHTML, /^Saved to Weekend &amp; &lt;Club&gt; on this device\. Your lists are under <a [^>]+>Saved<\/a>, in the bar at the bottom\. There you can also set up alerts for them\.$/);
  const lost = saveSetup({kept: false});
  lost.click();
  assert.equal(lost.els['save-msg'].innerHTML, 'This browser is not keeping site data, so this spot stays saved only for this visit.');
  const old = saveSetup({withSaveMsg: false});   // a page without the line falls back to the one at the foot
  old.click();
  assert.match(old.els['share-msg'].innerHTML, /^Saved on this device\./);
});

test("Facebook's and Instagram's own browsers are told apart from the rest by their user agents", () => {
  const src = between('const IN_APP =', '\nconst b64');
  const read = (ua, ios = false) => [...vm.runInContext(src + ';[IN_APP, OWN_BROWSER]', vm.createContext({navigator: {userAgent: ua}, IOS: ios}))];
  assert.deepEqual(read('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/480.0.0.0]', true), ['Facebook', 'Safari']);
  assert.deepEqual(read('Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/480.0.0.0;]'), ['Facebook', 'your own browser, such as Chrome']);
  assert.deepEqual(read('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Instagram 350.0.0', true), ['Instagram', 'Safari']);
  assert.equal(read('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1', true)[0], '');
});

function card({inApp = '', ios = false, push = true} = {}) {
  const ctx = vm.createContext({DATA: {push: push ? {url: 'https://push.invalid/'} : null}, canPush: () => false, offlineOff: () => false,
    IN_APP: inApp, IOS: ios, OWN_BROWSER: ios ? 'Safari' : 'your own browser, such as Chrome', navigator: {standalone: false}});
  vm.runInContext(between('function alertsCard(', 'async function bindAlerts(') + ';this.alertsCard = alertsCard;', ctx);
  return ctx.alertsCard();
}

test("in Facebook's browser the alerts tile says to open the page in Safari first, not to tap Share", () => {
  const fb = card({inApp: 'Facebook', ios: true});
  assert.match(fb, /Alerts cannot be turned on in the Facebook app's browser\. Open this page in Safari \(the Facebook app's menu has an option for it\), then tap <b>Share<\/b>, then <b>Add to Home Screen<\/b>, open SwimSignal from there and save your spots in it\./);
  assert.doesNotMatch(fb, /On iPhone and iPad, alerts work only/);
  assert.match(card({inApp: 'Instagram'}), /Open this page in your own browser, such as Chrome \(the Instagram app's menu has an option for it\) and save your spots there\./);
  // Safari on an iPhone keeps its own words, and the consent fold is unchanged before them.
  const safari = card({ios: true});
  assert.match(safari, /On iPhone and iPad, alerts work only in the Home Screen app: tap <b>Share<\/b>, then <b>Add to Home Screen<\/b>/);
  assert.match(safari, /<details class="more consent"><summary>What turning alerts on sends<\/summary>/);
});

test('a shared list says, before its button, that added it stays under Saved with alerts, and the note after points to them', () => {
  const shared = between('function renderShared(', 'function openSaved(');
  const lede = shared.indexOf('Once added, it stays under Saved, where you can set up alerts for its spots.'), note = shared.indexOf("You are in the ${IN_APP} app's browser."), add = shared.indexOf('id="sh-add"');
  assert.ok(lede > 0 && note > lede && add > note, 'the lede, then the in-app note, then Add to my lists');
  assert.match(shared, /alerts cannot be turned on here\. `/);
  assert.match(shared, /\(kept && \(DATA\.push \|\| DATA\.email\) \? ' To hear when one of its spots reaches high or very high risk: <button type="button" class="linkbtn small" id="to-alerts">Go to alerts<\/button>' : ''\)/);
  assert.match(between('function renderSaved(', 'function bindSavedPage('), /bindSwims\(\); bindToAlerts\(\);/);
});

test('"Go to alerts" brings the alerts heading into view and focuses it, and goes when there is no tile', () => {
  const src = between('function bindToAlerts(', 'function bindSavedPage(');
  const run = els => { const ctx = vm.createContext({document: {getElementById: id => els[id] || null}}); vm.runInContext(src + ';bindToAlerts();', ctx); };
  const els = {'to-alerts': el('to-alerts'), 'alerts-h': el('alerts-h')};
  run(els);
  els['to-alerts'].on.click();
  assert.equal(JSON.stringify(els['alerts-h'].scrolled), '{"block":"start"}');
  assert.equal(els['alerts-h'].tabIndex, -1);
  assert.ok(els['alerts-h'].focused);
  const lone = {'to-alerts': el('to-alerts')};
  run(lone);
  assert.ok(lone['to-alerts'].removed);
  assert.match(page, /#alerts-h \{ scroll-margin-top:calc\(var\(--header-h\) \+ 24px\); \}/);
});
