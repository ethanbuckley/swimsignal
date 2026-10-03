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
