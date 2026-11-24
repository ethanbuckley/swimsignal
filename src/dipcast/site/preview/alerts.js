// SwimSignal, the redesign preview: alerts for saved places. The live site's own alerts (index.html, "alerts"), through
// the same alert service and the same record in this browser ('dipcast.push'), so turning them on here or there is
// one setting, and a list changed on either page is sent once. Nothing here asks the browser for anything until
// "Turn on alerts" is pressed. window.PVAlerts.
(function () {
'use strict';
const PUSH_KEY = 'dipcast.push', OFFLINE_KEY = 'dipcast.offline', ua = navigator.userAgent;
const IOS = /iP(hone|ad|od)/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const STANDALONE = !!navigator.standalone || matchMedia('(display-mode: standalone)').matches;
// Facebook's or Instagram's own browser has no push, and keeps what a page stores apart from Safari or Chrome.
const IN_APP = /FBAN|FBAV|FB_IAB|FBIOS/.test(ua) ? 'Facebook' : /Instagram/.test(ua) ? 'Instagram' : '';
const OWN_BROWSER = IOS ? 'Safari' : 'your own browser, such as Chrome';
const SAFARI_MAC = !IOS && /Safari\//.test(ua) && !/Chrome|Chromium|CriOS|Edg|Firefox|FxiOS|OPR/.test(ua);
const TOUCH = matchMedia('(pointer: coarse)').matches;
const canPush = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
// The offline copy can be turned off on the live site (its foot, "Your data"); alerts arrive through its worker.
const offlineOff = () => { try { return localStorage.getItem(OFFLINE_KEY) === 'off'; } catch (e) { return false; } };
const b64 = s => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
const record = () => { try { const v = JSON.parse(localStorage.getItem(PUSH_KEY) || 'null'); return v && typeof v === 'object' ? v : {}; } catch (e) { return {}; } };
const weeklyOn = () => record().weekly === true;
// Places whose alerts were turned off one by one on the live site's cards: kept, and never sent.
const turnedOff = () => { const x = record().off; return Array.isArray(x) ? x.filter(id => typeof id === 'string') : []; };
function deadline(work, message, ms = 20000) {
  let timer;
  return Promise.race([work, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), ms); })]).finally(() => clearTimeout(timer));
}
// The site's worker (../sw.js, the live site's own, whose reach covers this page). Looked for, never started, when
// the page only needs to know whether alerts are on; started when alerts are turned on.
const site = () => new URL('../', location.href);
async function worker(start) {
  if (!canPush() || offlineOff()) return null;
  if (start) { await navigator.serviceWorker.register(new URL('sw.js', site())).catch(() => {});
    return Promise.race([navigator.serviceWorker.ready, new Promise(r => setTimeout(() => r(null), 5000))]); }
  return (await navigator.serviceWorker.getRegistration(site()).catch(() => null)) || null;
}
async function subscription() { const reg = await worker(false);
  return reg ? deadline(reg.pushManager.getSubscription(), 'the browser did not answer; try again', 8000) : null; }
// What this browser can do: 'yes', or why not.
const can = () => !canPush() ? (IN_APP ? 'inapp' : IOS && !STANDALONE ? 'ios' : 'none') : offlineOff() ? 'offline' : Notification.permission === 'denied' ? 'blocked' : 'yes';
async function isOn() { return can() === 'yes' && Notification.permission === 'granted' && !!(await subscription().catch(() => null)); }
// Send the list: the push address and the saved places' ids, and nothing else (the live page's sendSub).
async function send(push, sub, ids, weekly = weeklyOn()) {
  const off = turnedOff(), spots = ids.filter(id => !off.includes(id));
  const res = await fetch(push.url + 'subscribe', { method: 'POST', signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subscription: sub.toJSON(), spots, weekly }) });
  if (!res.ok) throw new Error(`the alert service answered ${res.status}`);
  try { localStorage.setItem(PUSH_KEY, JSON.stringify({ endpoint: sub.endpoint, spots, weekly, at: Date.now(), ...(off.length ? { off } : {}) })); } catch (e) { /* only saves a re-send */ }
}
async function turnOn(push, ids) {
  const answer = await Notification.requestPermission();
  if (answer !== 'granted') throw Object.assign(new Error('notifications are not allowed for this site'), { answer });
  const reg = await worker(true); if (!reg) throw new Error('the offline copy is not running, so notifications cannot be set up');
  const had = await deadline(reg.pushManager.getSubscription(), 'the browser did not answer; try again', 8000);
  const sub = had || await deadline(reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(push.key) }),
    'the browser could not finish setting up notifications. Check your connection and try again. On iPhone, use the Home Screen app');
  // An address made just now that the service did not take is dropped again, or a reload would say "on" with nothing sent.
  try { await send(push, sub, ids); } catch (e) { if (!had) await sub.unsubscribe().catch(() => {}); throw e; }
}
async function turnOff(push) {
  const sub = await subscription(); if (!sub) return false;
  const res = await fetch(push.url + 'unsubscribe', { method: 'POST', signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ endpoint: sub.endpoint }) });
  if (!res.ok) throw new Error(`the alert service answered ${res.status}; try again`);
  await deadline(sub.unsubscribe(), 'the browser could not turn notifications off; try again', 8000);
  try { localStorage.removeItem(PUSH_KEY); localStorage.removeItem('dipcast.pushclears'); } catch (e) { /* nothing kept */ }
  return true;
}
async function setWeekly(push, ids, want) { const sub = await subscription(); if (!sub) throw new Error('alerts are off in this browser'); await send(push, sub, ids, want); }
// The list changed, or the page opened: sent again if it differs from what the service holds, or once a week.
async function sync(push, ids) {
  if (!push || can() !== 'yes' || Notification.permission !== 'granted') return;
  const sub = await subscription(); if (!sub) return;
  const last = record(), off = turnedOff(), spots = ids.filter(id => !off.includes(id));
  if (last.endpoint === sub.endpoint && Array.isArray(last.spots) && last.spots.join() === spots.join() && Date.now() - last.at < 7 * 864e5) return;
  await send(push, sub, ids);
}
const serviceDown = e => !!e && (e.name === 'TypeError' || e.name === 'TimeoutError' || e.name === 'AbortError' || /alert service answered 5/.test(e.message || ''));
window.PVAlerts = { can, isOn, turnOn, turnOff, setWeekly, sync, weeklyOn, serviceDown, where: { ios: IOS, app: STANDALONE, safari: SAFARI_MAC, touch: TOUCH, inApp: IN_APP, own: OWN_BROWSER } };
})();
