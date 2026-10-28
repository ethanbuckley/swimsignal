// Today's EA advice on a bathing water's page (src/dipcast/site/eatoday.js): the EA's own panel, loaded
// once when its fold is opened, sandboxed, with no referrer, and nothing kept. The same rules as the
// coverage page's fold (tests/site_coastal.test.cjs). node --test tests/site_eatoday.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const ea = require('../src/dipcast/site/eatoday.js');

const SITE = join(__dirname, '../src/dipcast/site');
const SRC = fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8');
const PROFILE = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945';
const WIDGET = 'https://environment.data.gov.uk/bwq/widget/widget/widget1?eu=ukj2310-11945&history=false&m=false&p=false';
// Frensham Great Pond as spots.json has it at 15:29 on 4 Oct 2026: the EA had a harmful-algae incident open there since 19 Jun.
const frensham = (extra = {}) => ({ id: 'bw-ukj2310-11945', name: 'Frensham Great Pond', kind: 'lake', source: 'designated',
  classification: { class: 'excellent', year: 2025, url: PROFILE }, ...extra });

test("the EA's id comes from the spot's own id, or else its EA page, and only a bathing-water id counts", () => {
  assert.equal(ea.eaTodayId(frensham()), 'ukj2310-11945');
  assert.equal(ea.eaTodayId(frensham({ id: 'frensham' })), 'ukj2310-11945');   // from site= in the EA page's address
  assert.equal(ea.eaTodayId(frensham({ id: 'bw-uki2203-11942' })), 'uki2203-11942');   // the spot's own id first
  assert.equal(ea.eaTodayId(frensham({ classification: undefined })), null);   // not a designated bathing water
  assert.equal(ea.eaTodayId(frensham({ unlisted: true })), null);              // a point clicked on the map
  assert.equal(ea.eaTodayId(null), null);
  for (const url of [`${PROFILE}"><script>`, 'https://example.org/?site=ukj2310-1194', 'https://example.org/?site=javascript:x', undefined])
    assert.equal(ea.eaTodayId(frensham({ id: 'bw-ukj2310-11945&p=true', classification: { url } })), null, String(url));
});

test('the EA widget address is built only from a bathing-water id', () => {
  assert.equal(ea.eaTodayUrl('ukj2310-11945'), WIDGET);
  for (const bad of ['ukj2310-11945&p=true', 'javascript:alert(1)', '"><script>', 'bw-ukj2310-11945', '', undefined, null, 42])
    assert.equal(ea.eaTodayUrl(bad), null);
});

test("the fold is drawn closed, with the EA's page as its content until it is opened, and nothing from the EA", () => {
  const html = ea.eaTodayFold(frensham());
  assert.equal(html, '<details class="ea-today" id="ea-today" data-site="ukj2310-11945" data-name="Frensham Great Pond" data-rated="yes"><summary>Today\'s EA advice</summary>'
    + `<p>Open <a href="${PROFILE}">the EA's page</a> for today's advice.</p></details>`);
  assert.doesNotMatch(html, /<details[^>]* open|iframe|widget/);
  assert.match(ea.eaTodayFold(frensham({ name: 'A "pond" <b>' })), /data-name="A &quot;pond&quot; &lt;b&gt;"/);
  assert.equal(ea.eaTodayFold(frensham({ classification: { class: 'excellent', year: 2025 } })).includes(`href="${PROFILE}"`), true);   // no EA page given: its address from the id
  assert.equal(ea.eaTodayFold(frensham({ classification: undefined })), '');
  assert.equal(ea.eaTodayFold(frensham({ unlisted: true })), '');
});

// A fold as the browser gives it to the listener, and the page around eatoday.js, on a fixed clock.
function fold(site = 'ukj2310-11945', name = 'Frensham Great Pond', rated = 'yes') {
  const summary = { tag: 'summary' };
  return { dataset: { site, name, rated }, open: false, children: [summary, { tag: 'p' }], scrolled: 0,
    classList: { contains: c => c === 'ea-today' },
    querySelector: q => q === 'summary' ? summary : null,
    replaceChildren(...kids) { this.children = kids; },
    scrollIntoView(o) { this.scrolled++; this.block = o && o.block; } };
}
function page(clock = Date.parse('2026-10-04T16:45:00+01:00')) {
  let toggle, capture;
  const touched = [];
  const element = tag => ({ tag, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } });
  const kept = new Proxy({}, { get: (_t, k) => { touched.push(k); return () => null; } });
  const ctx = { document: { addEventListener: (event, fn, c) => { if (event === 'toggle') { toggle = fn; capture = c; } }, createElement: element },
    Date: Object.assign(function (t) { return new Date(t); }, { now: () => clock, parse: Date.parse }), Intl,
    localStorage: kept, sessionStorage: kept, indexedDB: kept };
  vm.runInNewContext(SRC, ctx);
  return { capture: () => capture, touched,
    open: f => { f.open = true; toggle({ target: f }); }, close: f => { f.open = false; toggle({ target: f }); } };
}

test('opening the fold loads the EA panel once, sandboxed, with no referrer, and says when', () => {
  const p = page(), f = fold();
  assert.equal(p.capture(), true);   // toggle does not bubble: the page listens on the way down
  assert.equal(f.children.length, 2);   // nothing loaded while it is closed
  p.open(f);
  const [summary, frame, note] = f.children;
  assert.equal(summary.tag, 'summary');
  assert.equal(frame.tag, 'iframe');
  assert.equal(frame.src, WIDGET);
  assert.equal(frame.title, "Environment Agency: today's advice at Frensham Great Pond");
  assert.equal(frame.attrs.sandbox, 'allow-popups allow-popups-to-escape-sandbox');   // no scripts, no same-origin
  assert.equal(frame.referrerPolicy, 'no-referrer');
  assert.equal(note.tag, 'p');
  assert.equal(note.innerHTML, "The Environment Agency's own panel, loaded 4 Oct 2026, 16:45. It shows no issue time, and browsers may keep it for up to an hour. No warning is not a water test. "
    + `If the panel does not show, open <a href="${PROFILE}">the EA's page</a>.`);   // the closed fold's link, kept for a panel that does not load
  assert.equal(f.scrolled, 1);
  assert.equal(f.block, 'nearest');
  p.close(f); p.open(f);
  assert.equal(f.children[1], frame);   // reopened: the same panel, not a second request
  assert.equal(f.scrolled, 1);
  assert.deepEqual(p.touched, []);      // nothing kept in the browser
});

test('a site with no rating yet gets the taller frame its panel needs, and so does a narrow phone', () => {
  // The EA's panel for a newly designated site adds two lines (Ham and Kingston: 314 px at 315 px wide, 4 Oct 2026).
  const ham = frensham({ id: 'bw-uki2203-11942', name: 'Ham and Kingston, River Thames', classification: { class: null, url: PROFILE.replace('ukj2310-11945', 'uki2203-11942') } });
  assert.match(ea.eaTodayFold(ham), /data-site="uki2203-11942" data-name="Ham and Kingston, River Thames" data-rated="no"/);
  const p = page(), f = fold('uki2203-11942', 'Ham and Kingston, River Thames', 'no'), g = fold();
  p.open(f); p.open(g);
  assert.equal(f.children[1].className, 'unrated');
  assert.equal(g.children[1].className, undefined);
  const css = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
  assert.match(css, /details\.ea-today iframe \{[^}]*max-width:343px; height:280px;/);
  assert.match(css, /details\.ea-today iframe\.unrated \{ height:340px; \}/);
  assert.match(css, /@media \(max-width: 374px\) \{ details\.ea-today iframe \{ height:330px; \} details\.ea-today iframe\.unrated \{ height:400px; \} \}/);
});

test("the line under the panel links the fold's own EA page, escaped", () => {
  const p = page(), f = fold();
  const own = 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945&x="1"';
  f.querySelector = q => q === 'summary' ? f.children[0] : q === 'p a' ? { getAttribute: k => k === 'href' ? own : null } : null;
  p.open(f);
  assert.match(f.children[2].innerHTML, /open <a href="https:\/\/environment\.data\.gov\.uk\/bwq\/profiles\/profile\.html\?site=ukj2310-11945&amp;x=&quot;1&quot;">the EA's page<\/a>\.$/);
});

test('the time under the panel is UK time, in winter too', () => {
  assert.equal(ea.eaTodayWhen(Date.parse('2026-10-04T15:45:00Z')), '4 Oct 2026, 16:45');
  assert.equal(ea.eaTodayWhen(Date.parse('2026-12-01T08:05:00Z')), '1 Dec 2026, 08:05');
});

test('a fold with a malformed id, a closed fold or another element loads nothing', () => {
  const p = page();
  const bad = fold('ukj2310-11945"><img src=x>');
  p.open(bad);
  assert.equal(bad.children.length, 2);
  const shut = fold();
  p.close(shut);
  assert.equal(shut.children.length, 2);
  const other = { ...fold(), classList: { contains: () => false } };
  p.open(other);
  assert.equal(other.children.length, 2);
});

// ---------------------------------------------------------------------------- the page around it
const html = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
function pageDefs(names) {   // as tests/site_planner.test.cjs: a definition runs to the next line at the margin
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function pageWith(withScript) {
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(join(SITE, 'levels.js'), 'utf8') + '\nsetToday("2026-10-04");', ctx);
  if (withScript) vm.runInContext(SRC, ctx);
  vm.runInContext(pageDefs(['esc', 'glyph', 'ICON', 'tone', 'tile', 'factorRow', 'explain', 'poorLine', 'ratingHistory',
    'riverTile', 'waterTile', 'weatherOn', 'facts', 'standing', 'check', 'nowTile', 'noFeedSaid', 'ecoliName', 'ecoliFold', 'ecoliCheck', 'ecoliSaid', 'ecoliMore',
    'sinceTime', 'spillFor', 'overflowSaid', 'longSpillLine', 'eaSaid', 'coverWords', 'coverLine', 'answerAfter']), ctx);
  return ctx;
}
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
const spot = frensham({ days: [{ date: '2026-10-04', risk: 0, label: 'low', rain_48h_mm: 0 }], upstream_summary: { overflows: 0 }, contributors: [],
  location: { mode: 'lake' }, assumptions: { max_upstream_km: 60 } });

// Since 11 Oct 2026 the answer says, beside the level, that the EA's advice for today could not be checked,
// and opens the fold (Frensham read "Low risk" and "Usual care" while the panel said bathing was not
// advised). Since 20 Oct 2026 as a clause of the line on what the forecast could read (coverLine), short,
// above the issue time. The line under the five days no longer repeats it.
test('beside the answer, the EA advice could not be checked: open the fold, whose link opens it; without the script, the EA page', () => {
  const line = vm.runInContext('coverLine', pageWith(true))(spot);
  assert.equal(line, '<p class="cover">Today\'s EA advice not checked: <a href="#ea-today">open it</a> before you swim.</p>');   // no overflow upstream: no live count
  assert.doesNotMatch(line, /widget/);
  const without = vm.runInContext('coverLine', pageWith(false))(spot);
  assert.match(without, new RegExp(`Today's EA advice not checked: <a href="${PROFILE.replace(/[.?]/g, '\\$&')}">see the EA's page</a> before you swim`));
  const river = { ...spot, id: 'osm-x', source: 'curated', classification: undefined };
  assert.equal(vm.runInContext('coverLine', pageWith(true))(river), '');   // not a bathing water, nothing upstream: nothing to say
  assert.equal(vm.runInContext('coverLine', pageWith(true))({ ...spot, unlisted: true, source: 'unlisted' }), '');   // a clicked point
  // Under the five days, the caveat alone.
  assert.equal(text(vm.runInContext('check', pageWith(true))(spot)), 'A forecast, not a water test.');
  assert.doesNotMatch(vm.runInContext('check', pageWith(true))(river), /ea-today/);
});

test('a tile ends with its fold, after the rest of its explanation', () => {
  const t = vm.runInContext('tile', pageWith(true))({ icon: '', label: 'Environment Agency rating, 2025', fig: 'Excellent', say: 'S.', more: 'M.', fold: ea.eaTodayFold(spot) });
  assert.ok(t.indexOf('class="t-say"') < t.indexOf('class="t-more"') && t.indexOf('class="t-more"') < t.indexOf('class="ea-today"'));
  assert.ok(t.endsWith('</details></div>'));
});

test("one fold per page, at the foot of the rating tile, rated or not yet; a picked day's rating row has none", () => {
  const ctx = pageWith(true), facts = vm.runInContext('facts', ctx), standing = vm.runInContext('standing', ctx);
  for (const s of [spot, { ...spot, id: 'bw-uki2203-11942', name: 'Ham and Kingston, River Thames',
    classification: { class: null, url: PROFILE.replace('ukj2310-11945', 'uki2203-11942') } }]) {
    const tiles = facts(s), rating = tiles[0];
    assert.match(rating.label, /^Environment Agency rating/);
    assert.equal(rating.fold, ea.eaTodayFold(s));
    assert.ok(rating.fold.includes(`data-site="${s.id.slice(3)}"`));
    assert.equal(tiles.filter(t => t.fold).length, 1);
    // The tile's sentence no longer says the page lacks the advice; the fold follows it.
    assert.match(text(rating.say), /The EA's page has its latest samples and any short-term advice against bathing, after pollution or algae\.$/);
    const day = standing(s, '2026-10-06');
    assert.doesNotMatch(day, /ea-today|which this page does not include/);
    assert.match(text(day), /any short-term advice against bathing, after pollution or algae\./);
  }
  // Without eatoday.js the page says what it said before, and has no fold.
  const before = pageWith(false), r0 = vm.runInContext('facts', before)(spot)[0];
  assert.equal(r0.fold, '');
  assert.match(text(r0.say), /after pollution or algae, which this page does not include\.$/);
  assert.match(text(vm.runInContext('standing', before)(spot, '2026-10-06')), /which this page does not include\./);
  // A spot that is not a bathing water has no rating tile and no fold.
  assert.equal(facts({ ...spot, id: 'osm-x', source: 'curated', classification: undefined }).some(t => t.fold), false);
});

test('the evidence panel says nothing of the fold: the advice is not part of the level', () => {
  assert.doesNotMatch(fs.readFileSync(join(SITE, 'evidence.js'), 'utf8'), /ea-today|eaToday|Today's EA advice|short-term/);
});

test('the embed, the organisers\' page and sign, and the alerts do not load the panel (the embed and the organisers\' page load eatoday.js for the compact form alone)', () => {
  const files = ['embed.js', 'embed.html', 'organisers.js', 'organisers.html', 'sign.html'].map(f => join(SITE, f))
    .concat(fs.readdirSync(join(__dirname, '../push/src')).filter(f => f.endsWith('.js')).map(f => join(__dirname, '../push/src', f)));
  for (const f of files) assert.doesNotMatch(fs.readFileSync(f, 'utf8'), /bwq\/widget|ea-today|eaTodayFold|eaTodayOpen|eaTodayListen|eaTodayOfficial/, f);
});

test("no other script of the page defines one of eatoday.js's names, and the page loads it first", () => {
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(m => m[1]));
  const mine = names(SRC);
  const others = [pageSrc.join('\n'),
    ...fs.readdirSync(SITE).filter(f => f.endsWith('.js') && !['eatoday.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(SITE, f), 'utf8'))];
  assert.deepEqual(others.flatMap(src => [...names(src)].filter(n => mine.has(n))), []);
  assert.ok(mine.has('eaTodayFold') && [...mine].every(n => /^(eaToday|EA_TODAY)/.test(n)));
  assert.ok(html.indexOf('src="eatoday.js"') > 0 && html.indexOf('src="eatoday.js"') < html.indexOf('<script>\n'), 'loaded before the page script that calls it');
});

// Official advice (eaTodayOfficial): reviewed lines the build writes into spots.json from data/advisories/
// (src/dipcast/official_advice.py). Fixture items only: no real approval is used here.
const LINE = 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026';
const item = (extra = {}) => ({ line: LINE, publisher: 'Environment Agency', link: PROFILE, since: '2026-06-19', checked: '2026-10-26', state: 'checked', restricts: true, ...extra });

test('official advice: the line, its link and when it was last checked, in a block of its own above the level', () => {
  const html = ea.eaTodayOfficial(frensham({ official: [item()] }));
  assert.equal(html, '<section class="notice official" id="official" aria-labelledby="official-h"><h2 id="official-h">Official advice</h2><ul>'
    + `<li><p class="o-line">${LINE}</p><p class="o-src"><a href="${PROFILE}">Open the Environment Agency page</a>. Last checked 26 Oct 2026.</p></li></ul>`
    + "<p class=\"o-sep\">Follow this advice first. It is not SwimSignal's, and the forecast below does not include it.</p></section>");
  assert.equal(ea.eaTodayApart(frensham({ official: [item()] })), '<p class="gaps o-apart">This level is SwimSignal\'s forecast. The official advice above is separate.</p>');
  assert.doesNotMatch(html, /risk|iframe|widget/i);   // it names no level and loads nothing
});

test('official advice: none, or none a page can show, draws nothing and changes nothing', () => {
  for (const official of [undefined, null, [], 'x', [{}], [item({ state: 'approved' })], [item({ checked: 'soon' })], [item({ line: '' })], [item({ publisher: 7 })]]) {
    assert.equal(ea.eaTodayOfficial(frensham({ official })), '', JSON.stringify(official));
    assert.equal(ea.eaTodayApart(frensham({ official })), '');
  }
  assert.equal(ea.eaTodayOfficial(null), '');
});

test('official advice: an old or failed check still shows the advice, and says it was not re-checked', () => {
  assert.equal(ea.eaTodayChecked(item({ state: 'stale', checked: '2026-10-19' })), 'Not re-checked since 19 Oct 2026.');
  assert.equal(ea.eaTodayChecked(item({ state: 'unverified', checked: '2026-10-19' })),
    'Not re-checked since 19 Oct 2026: the Environment Agency source could not be read.');
  const html = ea.eaTodayOfficial(frensham({ official: [item({ state: 'unverified', checked: '2026-10-19' })] }));
  assert.ok(html.includes(`<p class="o-line">${LINE}</p>`));
  assert.match(html, /Not re-checked since 19 Oct 2026: the Environment Agency source could not be read\./);
});

test('official advice: two at once are both shown, in the order given (newest first), each with its own check', () => {
  const council = item({ line: 'Waverley Borough Council: advice against swimming (harmful algae) since 20 Oct 2026', publisher: 'Waverley Borough Council',
    link: 'https://www.waverley.gov.uk/x', since: '2026-10-20', state: 'stale' });
  const html = ea.eaTodayOfficial(frensham({ official: [council, item()] }));
  assert.equal((html.match(/<li>/g) || []).length, 2);
  assert.ok(html.indexOf('Waverley') < html.indexOf(LINE));
  assert.match(html, /Open the Waverley Borough Council page<\/a>\. Not re-checked since 26 Oct 2026\./);
  assert.match(html, /Open the Environment Agency page<\/a>\. Last checked 26 Oct 2026\./);
});

test('official advice: its words are escaped, and a link that is not https is left out', () => {
  const html = ea.eaTodayOfficial(frensham({ official: [item({ line: '<img src=x onerror=alert(1)>', publisher: 'A & "B"', link: 'javascript:alert(1)' })] }));
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<img|javascript:|<a /);
  assert.match(html, /Last checked 26 Oct 2026\./);
  assert.doesNotMatch(ea.eaTodayOfficial(frensham({ official: [item({ link: 'https://x.org/"><script>' })] })), /<script>|<a /);
});

test('official advice: the coverage line says what was checked and when, in place of "not checked"', () => {
  assert.equal(ea.eaTodayCover(frensham({ official: [item()] })),
    'The Environment Agency\'s notice above was last checked 26 Oct. Open <a href="#ea-today">today\'s EA advice</a> for the latest');
  assert.equal(ea.eaTodayCover(frensham({ official: [item({ state: 'unverified', checked: '2026-10-19' })] })),
    'The Environment Agency\'s notice above has not been re-checked since 19 Oct. Open <a href="#ea-today">today\'s EA advice</a> for the latest');
  assert.match(ea.eaTodayCover(frensham({ official: [item(), item({ since: '2026-01-01' })] })), /^The notices above were last checked 26 Oct\./);
  // Not a bathing water (no fold): the publisher's own page instead.
  assert.equal(ea.eaTodayCover({ id: 'osm-x', name: 'X', official: [item()] }),
    `The Environment Agency's notice above was last checked 26 Oct. Open <a href="${PROFILE}">the Environment Agency page</a> for the latest`);
  for (const d of [frensham(), frensham({ official: [] }), null]) assert.equal(ea.eaTodayCover(d), '');
});

test('official advice: gone from the open list, or changed since review, stays up and says so', () => {
  assert.equal(ea.eaTodayChecked(item({ state: 'gone', checked: '2026-10-26' })),
    "Not re-checked since 26 Oct 2026: no longer in the Environment Agency's open list; its end was not published.");
  assert.equal(ea.eaTodayChecked(item({ state: 'changed', checked: '2026-10-26' })),
    "Not re-checked since 26 Oct 2026: the Environment Agency's record has changed since it was reviewed.");
  for (const state of ['gone', 'changed']) {
    const html = ea.eaTodayOfficial(frensham({ official: [item({ state })] }));
    assert.ok(html.includes(`<p class="o-line">${LINE}</p>`) && !html.includes('Last checked'), state);
    assert.match(ea.eaTodayCover(frensham({ official: [item({ state })] })), /has not been re-checked since 26 Oct/);
  }
});

