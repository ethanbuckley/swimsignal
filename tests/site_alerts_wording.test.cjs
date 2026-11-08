// Alert wording left by the 6 Nov 2026 phone audit (PR #642, items 3-5), fixed 8 Nov 2026:
//   - On an iPhone outside the Home Screen app, every saved card said "Notifications cannot be had in this browser."
//     with "See Alerts". The Alerts tile says what to do, once, in the words of the line under Save (#653).
//   - An outing's alerts said notifications were blocked without saying how to allow them (lists.js unblockHow).
//   - Closing the browser's question without a choice read "Could not change alerts: notifications are not allowed
//     for this site." It says what happened and how to be asked again.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const Li = require('../src/dipcast/site/lists.js');
const O = require('../src/dipcast/site/outing.js');
const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const outingSrc = fs.readFileSync('src/dipcast/site/outing.js', 'utf8');
const card = page.slice(page.indexOf('function alertsCard()'), page.indexOf('async function bindAlerts()'));

function tile({permission = 'default', email = false, ios = false, can = true} = {}) {
  const ctx = vm.createContext({DATA: {push: {url: 'https://test.invalid/', key: 'k'}, email: email ? {url: 'https://test.invalid/'} : undefined},
    Notification: {permission}, canPush: () => can, offlineOff: () => false, IOS: ios, STANDALONE: false, SAFARI_MAC: false, TOUCH: true,
    IN_APP: '', OWN_BROWSER: 'Safari', unblockHow: Li.unblockHow, navigator: {standalone: false}});
  vm.runInContext(card + ';this.alertsCard = alertsCard;', ctx);
  return ctx.alertsCard();
}

test('no notifications in this browser: the saved cards say nothing, whatever the reason', () => {
  for (const can of ['ios', 'inapp', 'offline', 'none']) {
    for (const email of [false, true]) {
      const st = Li.spotAlert({push: true, email, can});
      assert.equal(st.text, '', `${can}, email ${email}`);
      assert.equal(st.link, false, `${can}, email ${email}: no "See Alerts" under every card`);
      assert.equal(st.toggle, false);
    }
  }
  assert.equal(Li.spotAlert({push: false, email: true}).text, '');   // an email-only site: the tile holds the form
  // Nothing anywhere still says "cannot be had".
  assert.ok(!fs.readFileSync('src/dipcast/site/lists.js', 'utf8').includes("'Notifications cannot be had"));
});

test('iPhone outside the Home Screen app: the Alerts tile says what to do once, as the line under Save does', () => {
  const h = tile({can: false, ios: true});
  const steps = h.replace(/<\/?b>/g, '');
  assert.equal((steps.match(/tap Share, then Add to Home Screen, open SwimSignal from there/g) || []).length, 1);
  assert.match(steps, /On iPhone and iPad, alerts work only in the Home Screen app: tap Share, then Add to Home Screen, open SwimSignal from there and save your spots in it\./);
  // The line under Save on a spot's page (#653) gives the same steps in the same order.
  assert.match(Li.saveAlertHint({push: true, can: 'ios'}).text, /tap Share, then Add to Home Screen, open SwimSignal from there and save this spot in it\.$/);
});

test('an outing with notifications blocked says how to allow them, then the calendar', () => {
  const pairs = [{spot: 'frensham', date: '2026-11-10', name: 'Frensham'}];
  const how = Li.unblockHow({touch: true});
  const h = O.outingAlert({state: 'blocked', pairs, list: [], unblock: how});
  assert.equal(h, '<p class="small">Notifications are blocked for this site in your browser settings, so SwimSignal cannot alert you about this outing. '
    + 'To allow them, tap the icon to the left of the web address, then turn on Notifications (it may be under Permissions). Then come back to this page. '
    + 'Or add it to your calendar.</p>');
  const ios = O.outingAlert({state: 'blocked', pairs, list: [], unblock: Li.unblockHow({ios: true, app: true, touch: true})});
  assert.match(ios, /open Settings, then Notifications, then SwimSignal, and turn on Allow Notifications\./);
  // The page passes the device's steps, and draws the part again once they are allowed.
  assert.match(outingSrc, /unblock: st\.state === 'blocked' && typeof unblockHow === 'function' \? unblockHow\(\{ ios: IOS, app: STANDALONE, safari: SAFARI_MAC, touch: TOUCH \}\)/);
  assert.match(outingSrc, /el\.dataset\.state === 'blocked' && Notification\.permission !== 'denied'/);
});

test('the question closed without a choice: what happened, and how to be asked again', () => {
  assert.equal(Li.notAllowedSaid({answer: 'default', touch: true}),
    'You did not allow notifications, so alerts are still off. Tap Turn on alerts to be asked again.');
  assert.equal(Li.notAllowedSaid({answer: 'default', touch: false}),
    'You did not allow notifications, so alerts are still off. Click Turn on alerts to be asked again.');
  // Closed again on this visit (Chrome stops asking after the third close), or refused without a block (Firefox's
  // "Block" without remembering it): asking again may not work, so where to allow them, for this device.
  for (const x of [{answer: 'default', again: true}, {answer: 'denied'}]) {
    assert.equal(Li.notAllowedSaid({...x, touch: true}),
      'You did not allow notifications, so alerts are still off. Your browser may not ask again for a while. '
      + 'To allow them, tap the icon to the left of the web address, then turn on Notifications (it may be under Permissions). Then come back to this page.');
  }
  assert.match(Li.notAllowedSaid({answer: 'default', again: true, safari: true}), /open Safari's Settings, then Websites, then Notifications/);
  // The page keeps the browser's answer with the error and says this instead of the old line; a blocked site still
  // gets the blocked tile first.
  assert.match(page, /const answer = await Notification\.requestPermission\(\);\n\s*if \(answer !== 'granted'\) throw Object\.assign\(new Error\([^)]*\), \{ answer \}\);/);
  assert.match(page, /m\.textContent = e\.answer \? notAllowedSaid\(\{ answer: e\.answer, again: ALERT_UI\.refused\+\+ > 0,/);
  const bind = page.slice(page.indexOf('async function bindAlerts()'), page.indexOf('function alertsPermChanged()'));
  assert.ok(bind.indexOf("Notification.permission === 'denied' && alertsPermChanged()") < bind.indexOf('notAllowedSaid('));
});
