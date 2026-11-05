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

// A list's link pasted on the Saved page (the Home Screen app on an iPhone has no address bar, 26 Oct
// 2026): only a link to this site's Saved page holding a list is taken, and only its hash is kept.
test('a pasted link opens a list only when it is a link to a list on this site', () => {
  const live = 'https://swimsignal.co.uk/saved/#list=Windermere&spots=osm-windermere-waterhead,bw-ukd1203-45650';
  const here = 'http://localhost:8812';
  assert.deepEqual(S.pastedList(live, here), {hash: '#list=Windermere&spots=osm-windermere-waterhead,bw-ukd1203-45650'});
  assert.deepEqual(S.pastedList(`  \n${live}\t `, here), S.pastedList(live, here));   // spaces and a line break around it, as a paste brings
  assert.deepEqual(S.pastedList('https://www.swimsignal.co.uk/saved/#spots=a,b', 'https://swimsignal.co.uk'), {hash: '#spots=a,b'});   // a link from before lists
  assert.deepEqual(S.pastedList('http://localhost:8812/saved/index.html#list=W&spots=a', here), {hash: '#list=W&spots=a'});   // the page's own host
  assert.deepEqual(S.pastedList('https://swimsignal.co.uk/saved#list=W&spots=a', here), {hash: '#list=W&spots=a'});   // typed without the last slash
  assert.deepEqual(S.pastedList('https://example.org/swimsignal/saved/#list=W&spots=a', 'https://example.org/swimsignal/'), {hash: '#list=W&spots=a'});   // under a folder
  assert.deepEqual(S.pastedList('https://swimsignal.co.uk/saved/' + S.shareHash('Plan', ['a'], '2026-10-27'), here), {hash: '#list=Plan&day=2026-10-27&spots=a'});
  // What is turned away, and why.
  const why = (t, origin = here) => S.pastedList(t, origin).why;
  for (const t of ['', '   \n', null, undefined, 42, {toString: () => live}]) assert.equal(why(t), 'empty', String(t));
  assert.equal(why('https://swimsignal.co.uk/saved/#spots=' + 'a,'.repeat(S.PASTE_MAX)), 'long');
  assert.equal(why('swimsignal.co.uk/saved/#list=W&spots=a'), 'notlink');   // no https://, so not a link a browser opens
  assert.equal(why('Windermere'), 'notlink');
  assert.equal(why('javascript:alert(1)//saved/#spots=a'), 'site');
  assert.equal(why('ftp://swimsignal.co.uk/saved/#spots=a'), 'site');
  assert.equal(why('https://example.com/saved/#list=W&spots=a'), 'site');
  assert.equal(why('https://swimsignal.co.uk.evil.com/saved/#list=W&spots=a'), 'site');   // a look-alike host
  assert.equal(why('https://evil.com/?https://swimsignal.co.uk/saved/#list=W&spots=a'), 'site');
  assert.equal(why('http://localhost:9999/saved/#list=W&spots=a'), 'site');   // another port is another site
  assert.equal(why('https://swimsignal.co.uk/saved/#list=W&spots=a', 'not a page address'), undefined);   // no origin: swimsignal.co.uk still is
  assert.equal(why('https://swimsignal.co.uk/spot/grasmere/#list=W&spots=a'), 'notlist');   // not the Saved page
  assert.equal(why('https://swimsignal.co.uk/sites.html#spots=a,b&name=Club'), 'notlist');   // a sites view, not a list
  assert.equal(why('https://swimsignal.co.uk/saved/'), 'notlist');
  assert.equal(why('https://swimsignal.co.uk/saved/#spots='), 'notlist');
  assert.equal(why('https://swimsignal.co.uk/saved/#list=Weekend'), 'notlist');
  // A name with markup in it stays in the hash, as typed; the page escapes the name it shows (esc in renderShared).
  const odd = S.pastedList('https://swimsignal.co.uk/saved/#list=%3Cb%3EHi%3C%2Fb%3E&spots=a', here);
  assert.deepEqual(odd, {hash: '#list=%3Cb%3EHi%3C%2Fb%3E&spots=a'});
  assert.equal(S.readShared(odd.hash).name, '<b>Hi</b>');
  // A raw < in a pasted link is percent-encoded by the URL parser, never kept as markup.
  assert.doesNotMatch(S.pastedList('https://swimsignal.co.uk/saved/#list=<b>Hi</b>&spots=a', here).hash, /</);
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

// The list's answer line with a day picked (16 Oct 2026, docs/REVIEW-2026-10-16.md 8.4, G4): picking
// "Mon 19 Oct" turned the list to "On Monday" while the line above it still said "Tomorrow: 67 of 105
// spots at low risk". With a day picked the line is that day's; with none, the weekend's better day
// stays the rule (Ethan, PR #216).

// ------------------------------------------------------------------------------ the home list, A–Z by area
// The rows with no monitored overflow upstream go at the end of their area behind one line (review of
// 16 Oct 2026, C3). Top-level definitions taken from index.html's script, as site_honest_headlines does.
const pageSrc = (() => { const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return page.slice(page.indexOf('<script>\n') + 9, page.lastIndexOf('</script>')).split('\n'); })();
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
const GEN = '2026-10-16T23:24:15+01:00';
function listPage(spots) {
  const dir = path.join(__dirname, '../src/dipcast/site/');
  const ctx = vm.createContext({ console, DATA: { generated_at: GEN, spots } });
  for (const f of ['experience.js', 'levels.js']) vm.runInContext(fs.readFileSync(dir + f, 'utf8'), ctx, { filename: f });
  vm.runInContext(`setToday('2026-10-16');\n` + pageDefs(['esc', 'VIEW', 'mapLevel', 'mapWhen', 'listHeadline', 'issued', 'overview', 'lowEligible', 'lowToChoose', 'areaHead', 'QUIET_NAMES', 'areaRows']), ctx);
  return ctx;
}
const DAYS = ['2026-10-16', '2026-10-17', '2026-10-18', '2026-10-19', '2026-10-20'];
const fc = (id, name, n = 3) => ({ id, name, kind: 'lake', area: 'Cumbria and the Lake District', upstream_summary: { overflows: n }, location: { mode: 'lake' },
  now: { label: 'low', risk: 0, discharging_upstream: 0, monitored_upstream: n }, contributors: [], assumptions: { max_upstream_km: 60, recent_spill_hours: 48 },
  days: DAYS.map(date => ({ date, label: 'low', risk: n ? 0.01 : 0, rain_48h_mm: 29, in_validated_season: false })) });
const cumbria = [fc('blea', 'Blea Tarn, Langdale', 0), fc('butt', 'Buttermere', 0), fc('con', 'Coniston Water'), fc('crum', 'Crummock Water', 0),
  fc('elter', 'Elter Water'), fc('duddon', 'River Duddon, Birks Bridge', 0), fc('loug', 'Loughrigg Tarn', 0)];
const item = s => `<li><a class="row" data-id="${s.id}">${s.name}</a></li>`;
const ids = h => [...h.matchAll(/<li( class="quiet"( hidden)?)?><a class="row" data-id="(\w+)"/g)].map(m => m[3] + (m[1] ? (m[2] ? ':hidden' : ':shown') : ''));

test('in A–Z, an area\'s spots with no monitored overflow upstream go last, behind one line that names them', () => {
  const ctx = listPage(cumbria), rows = vm.runInContext('areaRows', ctx);
  const h = rows('Cumbria and the Lake District', cumbria, item, new Set());
  assert.deepEqual(ids(h), ['con', 'elter', 'blea:hidden', 'butt:hidden', 'crum:hidden', 'duddon:hidden', 'loug:hidden']);
  const line = h.match(/<li class="quiet-head">.*?<\/li>/)[0];
  assert.match(line, /data-quiet="Cumbria and the Lake District" aria-expanded="false"/);
  assert.match(line.replace(/<[^>]+>/g, ' '), /5 more spots with no monitored overflow upstream\s+Blea Tarn, Langdale, Buttermere, Crummock Water and 2 more/);
  // The area's head still counts every spot in it.
  assert.match(h, /<h3>Cumbria and the Lake District <span>· 7 spots, 2 at low risk<\/span><\/h3>/);
  // Opened, the rows show and the line says so; an area of quiet spots alone has no "more".
  assert.deepEqual(ids(rows('Cumbria and the Lake District', cumbria, item, new Set(['Cumbria and the Lake District']))).slice(2), ['blea:shown', 'butt:shown', 'crum:shown', 'duddon:shown', 'loug:shown']);
  assert.match(rows('X', cumbria.slice(0, 2), item, new Set()), /<span>2 spots with no monitored overflow upstream<\/span><span class="k">Blea Tarn, Langdale and Buttermere<\/span>/);
  // An area with none has no line; a search (fold false) shows every match as a row, in A–Z.
  assert.doesNotMatch(rows('X', [cumbria[2], cumbria[4]], item, new Set()), /quiet/);
  assert.deepEqual(ids(rows('X', cumbria, item, new Set(), false)), cumbria.map(s => s.id));
});

test('the count over the list still counts every spot with no monitored overflow, folded or not', () => {
  // 24 of 105 on 16 Oct 2026: here 24 quiet spots among 30.
  const spots = Array.from({ length: 30 }, (_, i) => fc(`s${i}`, `Spot ${i}`, i < 24 ? 0 : 3));
  const ctx = listPage(spots);
  assert.match(vm.runInContext('overview', ctx)(spots), / · 24 with no monitored overflow found upstream[ .]/);
});

test('"Highest risk" and "Near me" draw rows as before; A–Z, and lowest risk with no search or place, fold by area', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  // areaGroups is A–Z, or lowest risk with no search and no place (byArea, 31 Oct 2026); the other orders map every item to a row.
  assert.match(page, /const byArea = \(\) => VIEW\.sort === 'low' && !VIEW\.q\.trim\(\) && !VIEW\.here;/);
  assert.match(page, /function areaGroups\(items\) \{\n\s+if \(!\(VIEW\.sort === 'name' \|\| byArea\(\)\)/);
  assert.match(page, /ul\.innerHTML = groups \? groups\.map\(\(\[a, xs\]\) => byArea\(\) \? areaFold\(a, xs, spotItem\) : areaRows\(a, xs, spotItem, VIEW\.quiet, !words\.length\)\)\.join\(''\)\n\s+: items\.length \? items\.map\(spotItem\)\.join\(''\)/);
  // "Low risk only" keeps low spots alone, so none is behind the line.
  const ctx = listPage(cumbria);
  assert.equal(cumbria.filter(s => vm.runInContext('mapLevel', ctx)(s) === 'low').every(s => s.upstream_summary.overflows > 0), true);
});

// Add to my lists from a shared link (phone audit, 25 Oct 2026): a newcomer had the empty "My spots" a
// first visit makes, so adding "Windermere" left two lists and a chip for an empty one beside it.
test('a shared list takes the place of a first visit’s empty "My spots", and is added beside anything else', () => {
  const W = ['osm-windermere-waterhead', 'bw-ukd1203-45650'];
  const fresh = S.readLists(null, null);
  assert.deepEqual(fresh, {current: 'l1', lists: [{id: 'l1', name: 'My spots', spots: []}]});
  const one = S.addSharedList(fresh, 'Windermere', W);
  assert.deepEqual(one, {current: 'l1', lists: [{id: 'l1', name: 'Windermere', spots: W}]});   // one list, shown, Save adds to it
  assert.deepEqual(fresh.lists[0].spots, []);   // the old state is left as it was
  // Anything saved, a renamed list, or more than one list: beside them, exactly as makeList.
  const saved = S.addToList(fresh, 'l1', 'grasmere');
  const renamed = S.renameList(fresh, 'l1', 'Weekend');
  const two = S.makeList(fresh, 'Club');
  for (const st of [saved, renamed, two]) assert.deepEqual(S.addSharedList(st, 'Windermere', W), S.makeList(st, 'Windermere', W));
  assert.deepEqual(S.addSharedList(saved, 'Windermere', W).lists.map(l => [l.name, l.spots.length]), [['My spots', 1], ['Windermere', 2]]);
  // From a link before lists (#spots= only), the name a shared list reads: still one list.
  assert.equal(S.addSharedList(fresh, S.SHARED_LIST, W).lists[0].name, 'Shared list');
  // The page uses it for Add to my lists.
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  assert.match(page, /setLists\(addSharedList\(LISTS, sh\.name, spots\.map\(s => s\.id\)\)\)/);
});

 test('shared plans preserve valid dates outside the forecast window', () => {
  for (const date of ['2026-10-01', '2026-12-01']) {
    const read = S.readShared(S.shareHash('Plan', ['a'], date), DATES);
    assert.equal(read.day, null);
    assert.equal(read.requestedDay, date);
  }
  for (const date of ['2026-02-30', 'tomorrow'])
    assert.equal(S.readShared(`#spots=a&day=${date}`, DATES).requestedDay, undefined);
});
