// The alerts tile on the Saved page with email alerts (push/src/email.js): offered only where the build
// set DATA.email, beside push when that is set too, with the consent text folded before the button.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const source = page.slice(page.indexOf('function alertsCard() {'), page.indexOf('// One plain sentence or four, as a list:'));

const PUSH = {url: 'https://push.example/', key: 'k'}, EMAIL = {url: 'https://push.example/'};
function card(data, {ios = false, standalone = false, push = true} = {}) {
  const ctx = vm.createContext({DATA: {spots: [{id: 'a'}], ...data}, canPush: () => push, offlineOff: () => false, IOS: ios, navigator: {standalone}});
  vm.runInContext(source + ';this.card = alertsCard;', ctx);
  return ctx.card();
}

test('no alert service, no tile', () => {
  assert.equal(card({}), '');
});

test('push alone keeps its words', () => {
  const h = card({push: PUSH});
  assert.match(h, /<p class="sub">A notification when one of your saved spots turns high or very high, at most once a day for each\.<\/p>/);
  assert.match(h, /id="alerts-btn"/);
  assert.doesNotMatch(h, /alert-mail|email/i);
  assert.match(card({push: PUSH}, {ios: true, push: false}), /On iPhone and iPad, alerts work only in the Home Screen app: .*save your spots in it\.<\/p>/);
});

test('email alone: a labelled field, the consent fold, then the button', () => {
  const h = card({email: EMAIL});
  assert.match(h, /<p class="sub">An email when one of your saved spots/);
  assert.doesNotMatch(h, /alerts-btn|push address/);
  assert.match(h, /<form class="alert-mail" id="alert-mail" novalidate><label for="alert-email">Your email address<\/label><input type="email" id="alert-email" name="email" autocomplete="email"/);
  const fold = h.indexOf('What signing up by email sends'), button = h.indexOf('Email me alerts</button>');
  assert.ok(fold > 0 && button > fold, 'consent text comes before the button');
  for (const words of ['sends your email address and the list of your saved spots, and nothing else about you',
    'It emails you a link to confirm, and sends nothing else until you do.', 'carry no tracking',
    'Every email has a link to unsubscribe, which deletes your address at once.', 'no alert does not mean the water is clean',
    '<a href="privacy.html#email-alerts">Privacy notice</a>']) assert.ok(h.includes(words), words);
  assert.match(h, /<input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">/);
});

test('push and email: both, email after a hairline, and an iPhone outside the Home Screen is pointed to email', () => {
  const h = card({push: PUSH, email: EMAIL});
  assert.match(h, /<p class="sub">A notification or an email when/);
  assert.ok(h.indexOf('alerts-btn') < h.indexOf('alert-mail split'));
  assert.match(h, /<label for="alert-email">Or by email<\/label>/);
  const ios = card({push: PUSH, email: EMAIL}, {ios: true, push: false});
  assert.match(ios, /On iPhone and iPad, notifications work only in the Home Screen app: .* Or have them by email\.<\/p>/);
  assert.match(ios, /id="alert-mail"/);
});

function form(fetch, value = 'ann@example.org') {
  let submit;
  const msg = {textContent: ''}, button = {disabled: false};
  const email = {value, checkValidity: () => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value), focus() {}};
  const f = {elements: {email, website: {value: ''}}, querySelector: () => button, addEventListener: (_, fn) => { submit = fn; }};
  const ctx = vm.createContext({DATA: {email: EMAIL, spots: [{id: 'a'}, {id: 'b'}]}, SAVED: new Set(['a', 'gone']), fetch, AbortSignal,
    document: {getElementById: id => ({'alert-mail': f, 'alerts-mail-msg': msg})[id]}});
  vm.runInContext(source + ';bindEmailAlerts();', ctx);
  return {send: () => submit({preventDefault() {}}), msg, email, button};
}

test('signing up posts the address and the saved spots that are in the forecast, and says what happens next', async () => {
  let sent;
  const f = form(async (url, init) => { sent = {url, ...init}; return {ok: true, status: 202}; });
  await f.send();
  assert.equal(sent.url, 'https://push.example/email/subscribe');
  assert.deepEqual(JSON.parse(sent.body), {email: 'ann@example.org', spots: ['a'], website: ''});
  assert.ok(sent.signal);
  assert.equal(f.msg.textContent, 'Check your inbox at ann@example.org: open the link in the email and press Confirm. Nothing more is sent until you do.');
  assert.equal(f.email.value, '', 'the address is not kept on the page');
  assert.equal(f.button.disabled, false);
});

test('a bad address, a busy connection, a refusal and no connection each say so', async () => {
  let calls = 0;
  const none = form(async () => { calls++; return {ok: true}; }, 'not an address');
  await none.send();
  assert.equal(none.msg.textContent, 'Enter your email address.');
  assert.equal(calls, 0);
  const busy = form(async () => ({ok: false, status: 429, text: async () => 'too many'}));
  await busy.send();
  assert.equal(busy.msg.textContent, 'Too many sign-ups from this connection. Try again in an hour.');
  const full = form(async () => ({ok: false, status: 503, text: async () => 'email sign-up is full for today; try again tomorrow'}));
  await full.send();
  assert.equal(full.msg.textContent, 'Could not sign up: email sign-up is full for today; try again tomorrow.');
  const off = form(async () => ({ok: false, status: 404, text: async () => 'Not found'}));
  await off.send();
  assert.equal(off.msg.textContent, 'Could not sign up: the alert service answered 404.');
  const offline = form(async () => { throw new TypeError('Failed to fetch'); });
  await offline.send();
  assert.equal(offline.msg.textContent, 'Could not reach the alert service. Check your connection and try again.');
});
