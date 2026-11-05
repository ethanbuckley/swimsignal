const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('src/dipcast/site/index.html', 'utf8');
const source = html.slice(html.indexOf('const DRAFTS ='), html.indexOf('// Words typed into a review'));
const ctx = vm.createContext({Event: class { constructor(type) { this.type = type; } }});
vm.runInContext(source, ctx);
const track = vm.runInContext('draftTrack', ctx), forget = vm.runInContext('draftForget', ctx);
function form(id) {
  const fields = [{name:'kind', type:'checkbox', value:'algae', checked:false}, {name:'text', type:'textarea', value:'', checked:false},
    {name:'consent', type:'checkbox', value:'yes', checked:false}];
  const listeners = {};
  for (const field of fields) field.dispatchEvent = () => {};
  return {id, fields, listeners, querySelectorAll: () => fields, insertAdjacentHTML: (_at, html) => {this.notice = html;},
    addEventListener: (type, callback) => {listeners[type] = callback;}};
}
test('text and checkbox drafts survive navigation in memory, scoped to spot, and cancel discards them', () => {
  const f = form('vn-form'); track(f, 'a');
  f.fields[0].checked = true; f.fields[1].value = 'water looked cloudy'; f.fields[2].checked = true;
  f.listeners.change({target:f.fields[0]});
  const other = form('vn-form'); track(other, 'b'); assert.equal(other.fields[1].value, '');
  const restored = form('vn-form'); track(restored, 'a');
  assert.equal(restored.fields[0].checked, true); assert.equal(restored.fields[1].value, 'water looked cloudy');
  assert.equal(restored.fields[2].checked, false); // consent is never restored
  restored.listeners.click({target:{closest: () => ({})}});
  const afterCancel = form('vn-form'); track(afterCancel, 'a'); assert.equal(afterCancel.fields[1].value, '');
});
test('a successful submission can remove its draft', () => {
  const f = form('rv-form'); track(f, 'a'); f.fields[1].value = 'note'; f.listeners.input();
  forget(f, 'a'); const again = form('rv-form'); track(again, 'a'); assert.equal(again.fields[1].value, '');
});
