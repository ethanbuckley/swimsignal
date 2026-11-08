// Notifications blocked for the site (7 Nov 2026): the Alerts tile on the Saved page said "Notifications are blocked
// for this site in your browser settings" beside a "Turn on alerts" button that could not work, since a browser
// refuses without asking once a site is blocked. Tapping it swapped that line for "Could not change alerts:
// notifications are not allowed for this site", and nothing said how to allow them again. Now: no button, where to
// allow them on the device in hand, and the tile drawn again when the swimmer comes back (tests/browser_smoke.mjs
// checks that part in Chrome).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const Li = require('../src/dipcast/site/lists.js');
const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const card = page.slice(page.indexOf('function alertsCard()'), page.indexOf('async function bindAlerts()'));

function tile({permission = 'default', push = true, email = false, ios = false, app = false, safari = false, touch = true, offline = false, can = true} = {}) {
  const ctx = vm.createContext({DATA: {push: push ? {url: 'https://test.invalid/', key: 'k'} : undefined, email: email ? {url: 'https://test.invalid/'} : undefined},
    Notification: {permission}, canPush: () => can, offlineOff: () => offline, IOS: ios, STANDALONE: app, SAFARI_MAC: safari, TOUCH: touch,
    IN_APP: '', OWN_BROWSER: 'Safari', unblockHow: Li.unblockHow, navigator: {standalone: app}});
  vm.runInContext(card + ';this.alertsCard = alertsCard;', ctx);
  return ctx.alertsCard();
}

test('blocked: no button, and where to allow them on this device', () => {
  const h = tile({permission: 'denied'});
  assert.ok(!h.includes('id="alerts-btn"'), 'no Turn on alerts button');
  assert.ok(!h.includes('<button'));
  assert.match(h, /Notifications are blocked for this site in your browser settings, so alerts cannot be turned on\. To allow them, tap the icon to the left of the web address/);
  assert.match(h, /Then come back to this page\.<\/p>/);
  assert.match(h, /id="alerts" data-perm="denied"/);
  // What turning them on sends stays one tap away: it is still what they would agree to.
  assert.ok(h.includes('What turning alerts on sends'));
});

test('not blocked: the button, as before, and the tile marked for the re-check', () => {
  for (const permission of ['default', 'granted']) {
    const h = tile({permission});
    assert.ok(h.includes('<button type="button" class="btn" id="alerts-btn" disabled>Turn on alerts</button>'), permission);
    assert.ok(!h.includes('alerts-blocked'), permission);
    assert.match(h, /data-perm="asks"/);
  }
});

test('the offline copy turned off still comes first; no web push still says so; email still offered', () => {
  assert.match(tile({permission: 'denied', offline: true}), /Alerts need the offline copy/);
  const ios = tile({can: false, ios: true});
  assert.match(ios, /work only in the Home Screen app/);
  assert.match(ios, /data-perm=""/);
  const both = tile({permission: 'denied', email: true});
  assert.match(both, /Then come back to this page\. Or have them by email\.<\/p>/);
  assert.ok(both.includes('Email me alerts'));
});

test('where to allow them, by device', () => {
  const how = Li.unblockHow;
  assert.equal(how({ios: true, app: true, touch: true}),
    'To allow them, open Settings, then Notifications, then SwimSignal, and turn on Allow Notifications. Then come back to this page.');
  assert.match(how({app: true, touch: true}), /^To allow them, turn on notifications for SwimSignal in your device's settings for apps\./);
  assert.match(how({safari: true}), /^To allow them, open Safari's Settings, then Websites, then Notifications, and set this site to Allow\./);
  assert.equal(how({touch: true}), 'To allow them, tap the icon to the left of the web address, then turn on Notifications (it may be under Permissions). Then come back to this page.');
  assert.equal(how({}), 'To allow them, click the icon to the left of the web address, then turn on Notifications. Then come back to this page.');
  for (const o of [{ios: true}, {app: true}, {safari: true}, {touch: true}, {}]) assert.doesNotMatch(how(o), /[<>&]/, 'plain text, safe in the tile');
});

test('refused at the browser\'s question: the tile is redrawn as blocked, not "Could not change alerts"', () => {
  const bind = page.slice(page.indexOf('async function bindAlerts()'), page.indexOf('function alertsPermChanged()'));
  assert.match(bind, /if \(on && Notification\.permission === 'denied' && alertsPermChanged\(\)\) \{ const p = document\.getElementById\('alerts-blocked'\); if \(p\) p\.focus\(\); return; \}/);
  // The old line after a blocked load is gone: the tile itself says it.
  assert.ok(!bind.includes("m.textContent = 'Notifications are blocked"));
  // The re-check: back in view, or the browser's own change event.
  assert.match(bind, /^async function bindAlerts\(\) \{\n  bindEmailAlerts\(\); watchAlertPerm\(\);/);
  assert.match(page, /document\.addEventListener\('visibilitychange', \(\) => \{ if \(document\.visibilityState === 'visible'\) alertsPermChanged\(\); \}\);/);
  assert.match(page, /navigator\.permissions\.query\(\{ name: 'notifications' \}\)\.then\(st => \{ st\.onchange = alertsPermChanged; \}\)/);
});
