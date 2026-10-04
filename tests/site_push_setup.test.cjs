const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const page = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const source = page.slice(page.indexOf('function pushDeadline('), page.indexOf('// The list changed, or the page opened'));

function setup(manager, fetch) {
  let timer, cleared = 0;
  const ctx = vm.createContext({canPush: () => true, pushReg: async () => ({pushManager: manager}),
    Notification: {requestPermission: async () => 'granted'}, DATA: {push: {url: 'https://test.invalid/', key: 'key'}, spots: [{id:'spot'}]},
    SAVED: new Set(['spot']), b64: () => 'key', fetch, AbortSignal, localStorage: {setItem() {},removeItem() {}},
    PUSH_KEY: 'test', setTimeout: fn => {timer=fn;return 1;}, clearTimeout: () => {cleared++;}});
  vm.runInContext(source + ';this.on = alertsOn;this.off = alertsOff;', ctx);
  return {ctx, fire: () => timer(), cleared: () => cleared};
}

test('stalled push registration times out without sending a late subscription', async () => {
  let finish, sent = 0;
  const state = setup({getSubscription: async () => null, subscribe: () => new Promise(r => {finish=r;})}, async () => {sent++;});
  const operation = state.ctx.on();
  await new Promise(setImmediate);
  assert.ok(finish);
  state.fire();
  await assert.rejects(operation, /could not finish setting up notifications/);
  finish({toJSON: () => ({})});
  await new Promise(setImmediate);
  assert.equal(sent, 0);
  assert.ok(state.cleared() >= 2);
});

test('failed server unsubscribe preserves browser subscription for a retry', async () => {
  let removed = 0;
  const state = setup({getSubscription: async () => ({endpoint:'test', unsubscribe: async () => {removed++;}})},
    async (_url, options) => {assert.ok(options.signal); return {ok:false,status:503};});
  await assert.rejects(state.ctx.off(), /503; try again/);
  assert.equal(removed, 0);
});

// The weekly note (push/src/weekly.js): off unless ticked, sent with the saved spots, and remembered
// with them so that the page's re-sends keep it.
function withStorage() {
  const store = new Map(), bodies = [];
  const ctx = vm.createContext({canPush: () => true, pushReg: async () => ({pushManager: {getSubscription: async () => sub}}),
    Notification: {requestPermission: async () => 'granted'}, DATA: {push: {url: 'https://test.invalid/', key: 'key'}, spots: [{id:'spot'}]},
    SAVED: new Set(['spot']), b64: () => 'key', AbortSignal, PUSH_KEY: 'test', setTimeout, clearTimeout,
    fetch: async (_url, options) => { bodies.push(JSON.parse(options.body || '{}')); return {ok: true, status: 204}; },
    localStorage: {getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k)}});
  const sub = {endpoint: 'https://fcm.googleapis.com/fcm/send/x', toJSON: () => ({endpoint: 'https://fcm.googleapis.com/fcm/send/x'}), unsubscribe: async () => true};
  vm.runInContext(source + ';this.send = sendSub;this.weeklyOn = weeklyOn;this.on = alertsOn;this.off = alertsOff;', ctx);
  return {ctx, sub, bodies, store};
}

test('the weekly note is off unless ticked, and a re-send keeps what was ticked', async () => {
  const t = withStorage();
  await t.ctx.on();
  assert.equal(t.bodies.at(-1).weekly, false);
  assert.equal(t.ctx.weeklyOn(), false);
  await t.ctx.send(t.sub, true);
  assert.deepEqual(t.bodies.at(-1), {subscription: {endpoint: 'https://fcm.googleapis.com/fcm/send/x'}, spots: ['spot'], weekly: true});
  assert.equal(t.ctx.weeklyOn(), true);
  await t.ctx.send(t.sub);   // a change of saved spots, or the weekly re-send
  assert.equal(t.bodies.at(-1).weekly, true);
  await t.ctx.off();         // turning alerts off forgets it: on again starts with the note off
  assert.equal(t.ctx.weeklyOn(), false);
  t.store.set('test', 'not json');
  assert.equal(t.ctx.weeklyOn(), false);
});

test('the weekly box is in the alerts tile, hidden until alerts are on', () => {
  const card = page.slice(page.indexOf('function alertsCard('), page.indexOf('async function bindAlerts('));
  assert.match(card, /id="alerts-btn" disabled>Turn on alerts<\/button>`\s*\/\/[^\n]*\n\s*\+ '<label class="rv-consent" id="alerts-week" hidden><input type="checkbox">/);
  assert.match(card, /the days with the lowest pollution risk, Friday to Monday, at each saved spot/);
  assert.match(card, /Ticking the weekly note adds only that you want it\./);
  const bind = page.slice(page.indexOf('async function bindAlerts('), page.indexOf('function bindEmailAlerts('));
  assert.match(bind, /w\.hidden = !on; box\.checked = on && weeklyOn\(\);/);
});
