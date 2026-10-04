// Named lists of saved spots (src/dipcast/site/lists.js): the move from one list to several without
// losing a saved spot, what odd stored values read as, the changes the Saved page makes, and the
// links that share a list or a plan.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const S = require('../src/dipcast/site/lists.js');
const DATES = ['2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-08'];
const json = v => JSON.stringify(v);

test('the one list from before lists becomes "My spots", in its order, and nothing is lost', () => {
  const state = S.readLists(null, json(['wharfe-burnsall', 'grasmere', 'eden-armathwaite']));
  assert.deepEqual(state, {current: 'l1', lists: [{id: 'l1', name: 'My spots', spots: ['wharfe-burnsall', 'grasmere', 'eden-armathwaite']}]});
  assert.deepEqual(S.readLists(null, null), {current: 'l1', lists: [{id: 'l1', name: 'My spots', spots: []}]});   // a first visit
  // Written back, the lists read as they were, and the old key, written beside them, adds nothing.
  const two = S.makeList(state, 'Weekend', ['buttermere']);
  assert.deepEqual(S.readLists(S.listsText(two), json(S.allSaved(two))), two);
});

test('a spot a page from before lists saved since is added to the first list; one it removed is kept', () => {
  const lists = json({v: 1, current: 'l2', lists: [{id: 'l1', name: 'My spots', spots: ['a']}, {id: 'l2', name: 'Weekend', spots: ['b']}]});
  const state = S.readLists(lists, json(['a', 'b', 'new']));
  assert.deepEqual(state.lists.map(l => l.spots), [['a', 'new'], ['b']]);
  assert.equal(state.current, 'l2');
  // An old list that has lost a spot, or is empty or broken, takes nothing out of a list.
  for (const old of [json(['a']), '[]', 'not json', null]) assert.deepEqual(S.readLists(lists, old).lists.map(l => l.spots), [['a'], ['b']], String(old));
});

test('odd stored values read as empty, or are mended, rather than stopping the page', () => {
  const first = {current: 'l1', lists: [{id: 'l1', name: 'My spots', spots: []}]};
  for (const text of ['', 'not json', 'null', '42', '"lists"', '[]', '{}', '{"lists": "a,b"}', '{"lists": []}', '{"lists": [null, 3, "x", []]}'])
    assert.deepEqual(S.readLists(text, null), first, text);
  // Lists that are partly right keep what can be read.
  const state = S.readLists(json({current: {}, lists: [
    {id: 'l1', name: 42, spots: ['a', 3, null, 'a', '', 'x'.repeat(101), 'b']},   // a name that is not text, ids that are not ids, a repeat
    {id: 'l1', name: 'Weekend', spots: 'c'},                                       // the same id twice; spots that are not a list
    {id: '<script>', name: '  Club\u0000 \u202e swims \n', spots: ['c']},            // an id that is not one; control and direction characters
    {name: 'my SPOTS', spots: ['d']},                                              // no id; a name in use, in other letters
  ]}), json('not a list'));
  assert.deepEqual(state, {current: 'l1', lists: [
    {id: 'l1', name: 'My spots', spots: ['a', 'b']},
    {id: 'l2', name: 'Weekend', spots: []},
    {id: 'l3', name: 'Club swims', spots: ['c']},
    {id: 'l4', name: 'my SPOTS 2', spots: ['d']},
  ]});
  // A change from another tab is followed only if it holds lists.
  assert.equal(S.listsReadable(S.listsText(state)), true);
  for (const text of [null, '', '[]', '{}', 'not json', '{"lists": {}}']) assert.equal(S.listsReadable(text), false, String(text));
});

test('a name is text, at most 40 characters as a reader counts them, and never empty', () => {
  assert.equal(S.listName('  Weekend   swims '), 'Weekend swims');
  assert.equal(S.listName({toString: () => 'x'}), '');
  assert.equal(S.listName('a'.repeat(60)).length, 40);
  assert.equal(Array.from(S.listName('🏊'.repeat(50))).length, 40);   // emoji are not cut in half
  const many = S.makeList(S.makeList(S.readLists(null, null), 'Weekend'), 'weekend');
  assert.deepEqual(many.lists.map(l => l.name), ['My spots', 'Weekend', 'weekend 2']);
  assert.equal(S.makeList(many, '   ').lists.at(-1).name, 'New list');
  assert.equal(S.freeListName([{id: 'l1', name: 'x'.repeat(40)}], 'x'.repeat(40)), 'x'.repeat(38) + ' 2');   // the number fits
});

test('the Saved page’s changes: save, remove and put back, move, copy, rename, delete', () => {
  let s = S.readLists(null, json(['a', 'b']));
  s = S.makeList(s, 'Weekend');
  assert.equal(S.shownList(s).name, 'Weekend');   // a new list is the one shown, and Save adds to it
  s = S.addToList(s, 'l2', 'c'); s = S.addToList(s, 'l2', 'c');
  assert.deepEqual(S.listById(s, 'l2').spots, ['c']);   // once only
  s = S.copyToList(s, 'a', 'l2');
  assert.deepEqual(s.lists.map(l => l.spots), [['a', 'b'], ['c', 'a']]);
  s = S.moveToList(s, 'b', 'l1', 'l2');
  assert.deepEqual(s.lists.map(l => l.spots), [['a'], ['c', 'a', 'b']]);
  assert.equal(S.moveToList(s, 'a', 'l1', 'l1'), s);
  const without = S.removeFromList(s, 'l2', 'a');
  assert.deepEqual(S.addToList(without, 'l2', 'a', 1).lists[1].spots, ['c', 'a', 'b']);   // Undo puts it back where it was
  assert.deepEqual(S.allSaved(s), ['a', 'c', 'b']);
  assert.deepEqual(S.renameList(s, 'l1', 'Weekend').lists.map(l => l.name), ['Weekend 2', 'Weekend']);
  assert.equal(S.renameList(s, 'l1', '  '), s);
  assert.deepEqual(S.renameList(s, 'l2', 'weekend').lists[1].name, 'weekend');   // a list may change its own name's letters
  // Deleting the list shown shows the first; deleting the last leaves an empty "My spots".
  const gone = S.deleteList(s, 'l2');
  assert.deepEqual(gone, {current: 'l1', lists: [{id: 'l1', name: 'My spots', spots: ['a']}]});
  assert.deepEqual(S.deleteList(gone, 'l1'), {current: 'l1', lists: [{id: 'l1', name: 'My spots', spots: []}]});
  assert.equal(S.pickList(s, 'l9'), s);
  assert.deepEqual(S.keepSpots(s, id => id !== 'a').lists.map(l => l.spots), [[], ['c', 'b']]);
  // Nothing changes the lists it was given.
  assert.deepEqual(s.lists.map(l => l.spots), [['a'], ['c', 'a', 'b']]);
});

test('a list in a link holds its name and its spots, and reads back the same', () => {
  const hash = S.shareHash('Weekend & club', ['wharfe-burnsall', 'grasmere']);
  assert.equal(hash, '#list=Weekend%20%26%20club&spots=wharfe-burnsall,grasmere');
  assert.deepEqual(S.readShared(hash, DATES), {name: 'Weekend & club', spots: ['wharfe-burnsall', 'grasmere'], day: null});
  // A plan's carries its day, kept while it is one of the five.
  const plan = S.shareHash(S.planListName('2026-10-06'), ['a', 'b'], '2026-10-06');
  assert.equal(plan, '#list=Plan%20for%20Tuesday%206%20Oct&day=2026-10-06&spots=a,b');
  assert.deepEqual(S.readShared(plan, DATES), {name: 'Plan for Tuesday 6 Oct', spots: ['a', 'b'], day: '2026-10-06'});
  assert.equal(S.readShared(plan, ['2026-10-07']).day, null);   // opened after the day
  // Nothing about where a plan starts, or any other list, can be in it: only these three keys are written.
  assert.deepEqual(plan.slice(1).split('&').map(p => p.split('=')[0]), ['list', 'day', 'spots']);
});

test('a link from before lists, or an odd one, reads safely', () => {
  assert.deepEqual(S.readShared('#spots=a,b%2Dc', DATES), {name: 'Shared list', spots: ['a', 'b-c'], day: null});
  for (const h of ['', '#', '#day=2026-10-04', '#list=Weekend', '#from=Kendal&at=54.3,-2.7&within=20', null, undefined]) assert.equal(S.readShared(h, DATES), null, String(h));
  assert.deepEqual(S.readShared('#spots=', DATES), {name: 'Shared list', spots: [], day: null});
  const odd = S.readShared('#list=%E0%A4%A&spots=a,%E0%A4%A,a,,b&day=tomorrow&spots=zzz', DATES);   // broken escapes, repeats, a day that is not a date
  assert.deepEqual(odd, {name: 'Shared list', spots: ['a', 'b'], day: null});
  assert.equal(S.readShared('#list=Club+swims&spots=a').name, 'Club swims');   // a + typed for a space
  assert.equal(S.readShared(`#list=${'n'.repeat(500)}&spots=${Array.from({length: 500}, (_, i) => 's' + i).join(',')}`).spots.length, 200);
  assert.equal(S.readShared(`#list=${'n'.repeat(500)}&spots=a`).name.length, 40);
  assert.deepEqual(S.readShared('#list=%3Cb%3EHi%3C%2Fb%3E%0A&spots=a').name, '<b>Hi</b>');   // the page escapes it: esc() in renderShared
});

// The page loads lists.js as a plain script beside the others: its names must not collide with theirs,
// or the second declaration stops the page.
test('lists.js loads beside the page’s other scripts without a clash', () => {
  const dir = path.join(__dirname, '../src/dipcast/site/');
  const ctx = vm.createContext({console, require: () => { throw new Error('the page has no require'); }});
  for (const f of ['experience.js', 'levels.js', 'plan.js', 'lists.js']) vm.runInContext(fs.readFileSync(dir + f, 'utf8'), ctx, {filename: f});
  assert.equal(vm.runInContext("JSON.stringify(readLists(null, '[\"a\"]').lists[0].spots)", ctx), '["a"]');   // storedList from experience.js
  const page = fs.readFileSync(dir + 'index.html', 'utf8');
  assert.ok(page.indexOf('<script src="plan.js"></script>') < page.indexOf('<script src="lists.js"></script>'));
  assert.ok(page.indexOf('<script src="lists.js"></script>') < page.indexOf('<script>\nconst BRAND'));
  const mine = [...fs.readFileSync(dir + 'lists.js', 'utf8').matchAll(/^(?:const|let|function) ([A-Za-z_$][\w$]*)/gm)].map(m => m[1]);
  const script = page.match(/<script>\nconst BRAND[\s\S]*?<\/script>/)[0];
  for (const n of mine) assert.doesNotMatch(script, new RegExp(`^(?:const|let|var|function) ${n.replace('$', '\\$')}\\b`, 'm'), n);
});
