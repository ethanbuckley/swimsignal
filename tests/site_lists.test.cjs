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
test('the answer line follows the picked day, and keeps the weekend rule with none', () => {
  const dir = path.join(__dirname, '../src/dipcast/site/');
  const html = fs.readFileSync(dir + 'index.html', 'utf8');
  const src = html.slice(html.indexOf('<script>\nconst BRAND') + 9, html.lastIndexOf('</script>')).split('\n');
  const defs = names => names.map(n => { const i = src.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < src.length && /^[\s})\]+]/.test(src[j])) j++;
    return src.slice(i, j).join('\n'); }).join('\n');
  const fri = '2026-10-16', days = ['2026-10-16', '2026-10-17', '2026-10-18', '2026-10-19', '2026-10-20'];   // Fri to Tue
  const spot = labels => ({upstream_summary: {overflows: 1}, location: {mode: 'river'}, now: {label: labels[0]},
    days: labels.map((l, i) => ({date: days[i], label: l, risk: l === 'low' ? 0.01 : 0.5}))});
  //                      Fri     Sat     Sun     Mon     Tue
  const spots = [spot(['low', 'high', 'low', 'low', 'high']), spot(['low', 'low', 'high', 'low', 'high']),
                 spot(['high', 'high', 'high', 'low', 'high']), {days: [], upstream_summary: {overflows: 0}}];
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(dir + 'levels.js', 'utf8') + `\nsetToday("${fri}");`, ctx);
  vm.runInContext(`let VIEW = {day: null}; const DATA = {generated_at: '2026-10-16T09:12:00+01:00', spots: ${JSON.stringify(spots)}};\n` + defs(['esc', 'dateLabel', 'fiveDays', 'mostLine', 'lowAnswer', 'answerLines']), ctx);
  const line = day => { vm.runInContext(`VIEW.day = ${JSON.stringify(day)}`, ctx);
    return vm.runInContext('answerLines()', ctx).match(/<p class="low-answer">(.*?)<span class="pick"/)[1].replace(/<[^>]+>/g, ''); };
  assert.equal(line(null), 'Tomorrow: 1 of 4 spots at low risk');   // the weekend's better day: Saturday and Sunday tie, so the earlier
  assert.equal(line('2026-10-19'), 'Monday: 3 of 4 spots at low risk');
  assert.equal(line('2026-10-20'), 'Tuesday: none of 4 spots at low risk');
  assert.equal(line(fri), 'Today: 2 of 4 spots at low risk');
  assert.equal(line('2026-10-18'), 'Sunday: 1 of 4 spots at low risk');
  // A picked day worse than the week's best keeps the best-day line under it, in the answer's form.
  vm.runInContext('VIEW.day = "2026-10-20"', ctx);
  assert.match(vm.runInContext('answerLines()', ctx), /<p class="planner-note best-day"><b>Monday<\/b>: 3 of 4, the most this week<span class="pick"> · <button[^>]* data-pick-day="2026-10-19"/);
  // The week's best day itself: no second line.
  vm.runInContext('VIEW.day = "2026-10-19"', ctx);
  assert.doesNotMatch(vm.runInContext('answerLines()', ctx), /best-day/);
  // The rule itself (levels.js), and a picked day outside the five read as none picked.
  const L = require('../src/dipcast/site/levels.js');
  L.setToday(fri);
  try {
    assert.equal(L.lowAnswerDay(spots, days, '2026-10-19').date, '2026-10-19');
    assert.equal(L.lowAnswerDay(spots, days, '2026-10-30').date, '2026-10-17');
    assert.equal(L.lowAnswerDay(spots, days).date, '2026-10-17');
  } finally { L.setToday(null); }
  // Picking a day redraws the line: setMapDay fills #answer-lines again, and the list draws it there.
  const setMapDay = html.slice(html.indexOf('function setMapDay(iso) {'), html.indexOf('\n}\n', html.indexOf('function setMapDay(iso) {')));
  assert.match(setMapDay, /getElementById\('answer-lines'\); if \(ans\) \{ ans\.innerHTML = answerLines\(\); bindBestDay\(ans\); \}/);
  assert.match(html, /<div id="answer-lines">\$\{answerLines\(\)\}<\/div>/);
});

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
  vm.runInContext(`setToday('2026-10-16');\n` + pageDefs(['esc', 'VIEW', 'mapLevel', 'mapWhen', 'listHeadline', 'issued', 'overview', 'areaHead', 'QUIET_NAMES', 'areaRows']), ctx);
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
  assert.match(vm.runInContext('overview', ctx)(spots), / · 24 with no monitored overflow found upstream · /);
});

test('"Highest risk", "Near me" and "Low risk only" draw rows as before: only A–Z folds', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  // areaGroups is A–Z alone; the other orders map every item to a row.
  assert.match(page, /function areaGroups\(items\) \{\n\s+if \(VIEW\.sort !== 'name'/);
  assert.match(page, /ul\.innerHTML = groups \? groups\.map\(\(\[a, xs\]\) => areaRows\(a, xs, spotItem, VIEW\.quiet, !words\.length\)\)\.join\(''\)\n\s+: items\.length \? items\.map\(spotItem\)\.join\(''\)/);
  // "Low risk only" keeps low spots alone, so none is behind the line.
  const ctx = listPage(cumbria);
  assert.equal(cumbria.filter(s => vm.runInContext('mapLevel', ctx)(s) === 'low').every(s => s.upstream_summary.overflows > 0), true);
});
