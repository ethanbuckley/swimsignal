// An official notice (spots.json `official`) is said in its own reviewed words and nothing more (28 Oct 2026).
// The approvals file has no field for what a notice is, so no surface may call every notice "advice against
// swimming": only the line's own words say what it is. The map's ring is a cue to open the spot and read the
// notice, not a level. The share picture carries it as the server's share card does. And where the outing's spot
// and its backup both have one, one line says so, naming each with its own notice.
// node --test tests/site_official_notice.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { join } = require('node:path');
const L = require('../src/dipcast/site/levels.js');
const ea = require('../src/dipcast/site/eatoday.js');
const O = require('../src/dipcast/site/outing.js');

const SITE = join(__dirname, '../src/dipcast/site');
const PAGE = fs.readFileSync(join(SITE, 'index.html'), 'utf8');
const AGAINST = { line: 'Environment Agency: advice against bathing (harmful algae) since 19 Jun 2026', publisher: 'Environment Agency',
  link: 'https://environment.data.gov.uk/bwq/profiles/profile.html?site=ukj2310-11945', since: '2026-06-19', checked: '2026-10-26', state: 'checked', restricts: true };
// A notice that is not advice against swimming: a fixture only, in the shape a page notice may take.
const NEUTRAL = { line: 'City of London: swimming status notice (members only this week) since 20 Oct 2026', publisher: 'City of London',
  link: 'https://www.cityoflondon.gov.uk/', since: '2026-10-20', checked: '2026-10-26', state: 'checked', restricts: false };
const BRIEF = 'EA advice against bathing (harmful algae) · since 19 Jun · checked 26 Oct';
const NEUTRAL_BRIEF = 'City of London swimming status notice (members only this week) · since 20 Oct · checked 26 Oct';
L.setToday('2026-10-27');

const col = (id, name, official = null, extra = {}) => {
  const s = { official: official ? [official] : [] };
  return { id, name, href: `spot/${id}/`, tone: 'low', headline: 'Low risk tomorrow', level: 'low',
    official: O.outingOfficial(s), notice: ea.eaTodayBrief(s), advised: !!O.outingOfficial(s), ...extra };
};
const tile = o => O.outingSection({ day: '2026-10-28', when: '', spot: 'a', groups: [], backupGroups: [], missing: [], issued: 'x', open: true, ...o });

test('the briefs are the notices\' own words, and a neutral notice is not turned into advice against swimming', () => {
  assert.equal(ea.eaTodayBrief({ official: [AGAINST] }), BRIEF);
  assert.equal(ea.eaTodayBrief({ official: [NEUTRAL] }), NEUTRAL_BRIEF);
});

test('the outing: both choices with a notice get one line naming each, above the columns, in place of "neither"', () => {
  const pond = col('a', 'Frensham Great Pond', AGAINST), heath = col('b', 'Hampstead <Mixed> Pond', NEUTRAL);
  const h = tile({ main: pond, alt: heath });
  assert.ok(h.includes('<div class="outing-notices"><p><b>Your spot and your backup both have an official notice.</b> '
    + 'Read each before you go; neither is part of the levels below.</p>'
    + `<ul><li>Your spot, Frensham Great Pond: ${BRIEF}</li><li>Backup, Hampstead &lt;Mixed&gt; Pond: ${NEUTRAL_BRIEF}</li></ul></div>`), h);
  assert.ok(h.indexOf('outing-notices') < h.indexOf('outing-pair'));
  assert.ok(!h.includes('outing-poor'));   // the combined line says it; "neither looks good" is not added to it
  assert.doesNotMatch(h, /against swimming|restrict/i);   // only the EA's own line says "against bathing"
  // Each column still carries its own tag under its name.
  assert.equal((h.match(/class="o-tag"/g) || []).length, 2);
});

test('the outing: no combined line unless both choices have a notice', () => {
  const pond = col('a', 'Frensham Great Pond', AGAINST), lake = col('c', 'Shepperton Lake');
  for (const o of [{ main: pond, alt: lake }, { main: lake, alt: pond }, { main: pond, alt: null }, { main: lake, alt: lake }, { main: null, alt: null }]) {
    assert.ok(!tile(o).includes('outing-notices'));
    assert.equal(O.outingBoth(o), '');
  }
  // One notice and a Very high backup: the "neither" line as before, the notice named as a notice only.
  const wey = col('b', 'River Wey, Waverley', null, { tone: 'vhigh', level: 'very high' });
  assert.match(tile({ main: pond, alt: wey }),
    /<b>Neither spot looks good tomorrow\.<\/b> Frensham Great Pond has an official notice, and River Wey, Waverley is at Very high risk\./);
});

test('the page builds each outing column\'s notice from the shared helper', () => {
  const src = fs.readFileSync(join(SITE, 'outing.js'), 'utf8');
  assert.match(src, /official: outingOfficial\(s\), notice: outingBrief\(s\),/);
  assert.match(src, /\$\{outingBoth\(o\)\}\$\{outingNeither\(o\)\}<div class="outing-pair/);
});

// The page's own functions, run beside eatoday.js, as in the browser (tests/site_official_consistency.test.cjs).
const pageSrc = PAGE.slice(PAGE.indexOf('<script>\n') + 9, PAGE.lastIndexOf('</script>')).split('\n');
function pageDef(name) {
  const i = pageSrc.findIndex(l => l.startsWith(`const ${name} =`) || l.startsWith(`function ${name}(`));
  assert.ok(i >= 0, `no ${name} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n');
}

test('the share picture says the notice in the server card\'s words, and nothing without one', () => {
  const ctx = vm.createContext({});
  vm.runInContext(fs.readFileSync(join(SITE, 'eatoday.js'), 'utf8'), ctx);
  vm.runInContext(pageDef('shareNotice'), ctx);
  const say = vm.runInContext('shareNotice', ctx);
  // The same sentence as cards.py official_words (tests/test_cards.py, test_spot_share_card_carries_official_advice).
  assert.equal(say({ official: [AGAINST] }), `Official: ${BRIEF}. Follow it first; the level is SwimSignal's sewage forecast only.`);
  assert.equal(say({ official: [NEUTRAL] }), `Official: ${NEUTRAL_BRIEF}. Read the official notice first; the level is SwimSignal's sewage forecast only.`);
  assert.equal(say({ official: [] }), '');
  assert.equal(say({}), '');
  // It is drawn under the name, before the level.
  const draw = pageSrc.join('\n');
  const at = s => draw.indexOf(s);
  assert.ok(at('const notice = shareNotice(d);') > at('let y = wrapText(g, d.name') && at('const notice = shareNotice(d);') < at('const iso = DAY, ans = answerParts(d, iso)'));
});

test('the map: the ring is a cue to read the notice, on the main map and the phone\'s small map alike', () => {
  assert.match(PAGE, /<span class="advkey" hidden><span class="dot adv"><\/span>Ringed: an official notice; open the spot to read it<\/span>/);
  assert.match(pageDef('miniMap'), /color: mapAdvised\(s\) \? ADVICE_RING : PAPER, weight: mapAdvised\(s\) \? 3\.5 : 2, fillColor: colour\(level\(s\)\)/);
  assert.match(pageDef('styleMarkers'), /color: adv \? ADVICE_RING : PAPER/);
});

test('no surface calls every notice advice against swimming: only a notice\'s own line may say so', () => {
  for (const f of ['index.html', 'outing.js', 'plan.js', 'eatoday.js']) {
    assert.doesNotMatch(fs.readFileSync(join(SITE, f), 'utf8'), /advice against swimming/i, f);
  }
  assert.doesNotMatch(fs.readFileSync(join(__dirname, '../src/dipcast/cards.py'), 'utf8'), /advice against swimming/i);
});
