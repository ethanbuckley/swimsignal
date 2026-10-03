// What to do at each level (levels.js, levelAction and dayAction): one line under the answer on a
// spot's page, on the embed card and in the alerts file. Health wording, so every line is pinned
// here, and the Method page must give the same words.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const L = require('../src/dipcast/site/levels.js');
const Embed = require('../src/dipcast/site/embed.js');

const DATES = ['2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04'];   // a Wednesday to a Sunday
const SPILL = {low: 0.01, moderate: 0.2, high: 0.5, 'very high': 0.8};
const week = (labels, extra = {}) => ({id: 'x', name: 'A river', kind: 'river', source: 'curated', upstream_summary: {overflows: 3},
  location: {mode: 'river'}, now: {label: 'low'}, contributors: [],
  days: labels.map((l, i) => ({date: DATES[i], label: l, risk: SPILL[l], p_ecoli_gt900: 0.02, in_validated_season: true})), ...extra});
const LOW = 'Usual care: cover cuts, try not to swallow water and wash your hands before eating.';
const MODERATE = 'Take more care: young children, older people and anyone with a weakened immune system may want a lower day or spot.';
const HIGH = 'Better to choose a lower day or spot. If you do swim, try not to swallow any water.';
const POOR = 'Choose a spot with a better rating if you can.';
const ALGAE = 'Stay out of any scum or bloom, and keep children and dogs away: toxic algae look like harmless ones.';
const PLAIN = 'After heavy rain, wait a couple of days before swimming if you can.';
L.setToday('2026-09-30');

test('each level has its line, and very high names the day it falls on', () => {
  assert.equal(L.levelAction(week(['low', 'low', 'low', 'low', 'low'])), LOW);
  assert.equal(L.levelAction(week(['moderate', 'low', 'low', 'low', 'low'])), MODERATE);
  assert.equal(L.levelAction(week(['high', 'low', 'low', 'low', 'low'])), HIGH);
  assert.equal(L.levelAction(week(['very high', 'low', 'low', 'low', 'low'])), 'Avoid swimming here today: choose a lower day or spot.');
  // The headline's level can be tomorrow's, or right now's: the line says which.
  assert.equal(L.levelAction(week(['low', 'very high', 'low', 'low', 'low'])), 'Avoid swimming here tomorrow: choose a lower day or spot.');
  assert.equal(L.levelAction(week(['low', 'low', 'low', 'low', 'low'], {now: {label: 'very high'}})), 'Avoid swimming here right now: choose a lower day or spot.');
  // A worse later day leaves today's level, and its line, at low: where the week goes says the rest.
  assert.equal(L.levelAction(week(['low', 'low', 'very high', 'low', 'low'])), LOW);
  // The E. coli estimate sets a level as the spills do, with the same line.
  const wet = week(['low', 'low', 'low', 'low', 'low']); wet.days[0].p_ecoli_gt900 = 0.6;
  assert.equal(L.level(wet), 'very high');
  assert.equal(L.levelAction(wet), 'Avoid swimming here today: choose a lower day or spot.');
});

test('a water rated poor and algae get lines of their own; a worse forecast still wins', () => {
  const poor = week(['low', 'low', 'low', 'low', 'low'], {source: 'designated', classification: {class: 'poor', year: 2025}});
  assert.equal(L.levelAction(poor), POOR);
  assert.equal(L.dayAction(poor, '2026-10-01'), POOR);   // out of season: still rated poor, still at least high
  assert.equal(L.levelAction({...poor, days: week(['very high', 'low', 'low', 'low', 'low']).days}), 'Avoid swimming here today: choose a lower day or spot.');
  const algae = {...week(['low', 'low', 'low', 'low', 'low']), algae: {date: '2026-09-25', level: 3, phrase: 'enough to be objectionable'}};
  assert.equal(L.level(algae), 'high');
  assert.equal(L.levelAction(algae), ALGAE);
  // Without a daily forecast: a rating of sufficient is moderate, poor is the rating's line, algae theirs.
  const still = {id: 'y', days: [], upstream_summary: {overflows: 0}, location: {mode: 'lake'}};
  assert.equal(L.levelAction({...still, classification: {class: 'sufficient'}}), MODERATE);
  assert.equal(L.levelAction({...still, classification: {class: 'poor'}}), POOR);
  assert.equal(L.levelAction({...still, classification: {class: 'good'}, algae: {date: '2026-09-25', level: 2, phrase: 'some at intervals'}}), ALGAE);
});

test('without a level the line is about rain, whatever the reason', () => {
  assert.equal(L.levelAction({days: [], upstream_summary: {overflows: 0}}), PLAIN);   // no sewage risk from monitored overflows
  assert.equal(L.levelAction({days: [], error: 'An isolated lake with no river connection in the network.'}), PLAIN);
  assert.equal(L.levelAction({days: [], error: 'No river or lake within 1.5 km of this point.'}), PLAIN);   // not covered
  assert.equal(L.levelAction({days: [], error: 'forecast failed: timeout'}), PLAIN);
  assert.equal(L.levelAction({days: [], classification: {class: 'excellent'}}), PLAIN);   // a good rating does not make it low
});

test('a picked day gets its own line, naming that day', () => {
  const s = week(['low', 'moderate', 'very high', 'high', 'low']);
  assert.deepEqual(DATES.map(iso => L.dayAction(s, iso)),
    [LOW, MODERATE, 'Avoid swimming here on Friday: choose a lower day or spot.', HIGH, LOW]);
  assert.equal(L.dayAction(s, '2026-10-09'), PLAIN);   // no forecast for that day
  assert.equal(L.dayAction({days: [], upstream_summary: {overflows: 0}}, DATES[1]), PLAIN);   // the same on every day
});

test('no line says a spot is safe or uses a bare level word', () => {
  const all = [...Object.values(L.ACTION), L.POOR_ACTION, L.ALGAE_ACTION, L.PLAIN_ACTION, L.actionFor({level: 'very high', by: 'spill'})];
  for (const a of all) {
    assert.doesNotMatch(a, /\bsafe/i, a);
    assert.doesNotMatch(a, /\b(low|moderate|high|very high)\b(?! risk)/i, a);
    assert.ok(a.length <= 120, `${a.length} characters: ${a}`);   // one line under the answer on a desktop
  }
});

test('the Method page gives each line word for word', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/api/static/methods.html'), 'utf8');
  const sec = html.slice(html.indexOf('<h3 id="actions">'), html.indexOf('</section>', html.indexOf('<h3 id="actions">')));
  assert.ok(sec.length > 100, 'no #actions section on methods.html');
  for (const [lab, a] of [['Low risk', LOW], ['Moderate risk', MODERATE], ['High risk', HIGH], ['Very high risk', 'Avoid swimming here: choose a lower day or spot.'],
    ['Rated poor', POOR], ['Algae at the last check', ALGAE], ['No level', PLAIN]]) {
    assert.match(sec, new RegExp(`<dt>${lab}[^<]*</dt><dd>${a.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`), lab);
  }
  for (const href of ['https://www.gov.uk/government/publications/swim-healthy-leaflet/swim-healthy', 'https://www.beachwatch.nsw.gov.au/whatIsBeachwatch/safeToSwim',
    'https://environment.data.gov.uk/bwq/profiles/help-understanding-data.html', 'https://www.sas.org.uk/water-quality/sewage-pollution-alerts/',
    'https://www.nhs.uk/conditions/leptospirosis/']) assert.ok(sec.includes(`href="${href}"`), href);
});

// ------------------------------------------------------------------------------ on the page
// Top-level definitions taken from index.html's script and run beside levels.js and experience.js, as
// tests/site_planner.test.cjs does.
const pageSrc = (() => { const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
function pageContext(names, extra = {}) {
  const dir = path.join(__dirname, '../src/dipcast/site/');
  const ctx = vm.createContext({...extra});
  vm.runInContext(fs.readFileSync(dir + 'experience.js', 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(dir + 'levels.js', 'utf8') + '\nsetToday("2026-09-30");', ctx);
  vm.runInContext(pageDefs(names), ctx);
  return ctx;
}
const PAGE = ['esc', 'tone', 'headTone', 'rainSaid', 'answerParts', 'flowLine', 'ageMin', 'ago', 'issued', 'answerWords'];

test('the answer puts the line under where the week goes, for today and for a picked day', () => {
  const ctx = pageContext(PAGE, {DATA: {generated_at: '2026-09-30T08:00:00+01:00'}});
  const words = (d, iso = null) => vm.runInContext('answerWords', ctx)(d, iso);
  const s = week(['high', 'very high', 'low', 'low', 'low']);
  const h = words(s);
  assert.match(h, /<h2 class="big veryhigh" id="risk-headline">Very high risk<\/h2><p class="why">Sewage spills tomorrow<\/p><p class="next">Low risk by Friday<\/p><p class="act">Avoid swimming here tomorrow: choose a lower day or spot\.<\/p>/);
  assert.match(words(s, DATES[0]), /<p class="next">Today, Wednesday 30 September<\/p><p class="act">Better to choose a lower day or spot\. If you do swim, try not to swallow any water\.<\/p>/);
  assert.match(words(s, DATES[3]), /<h2 class="big low"[^>]*>Low risk<\/h2><p class="next">Saturday 3 October<\/p><p class="act">Usual care: cover cuts/);
  // Under a plain level: the other risks, the rain, then the line.
  const clear = {...week(['low', 'low', 'low', 'low', 'low']), upstream_summary: {overflows: 0}};
  clear.days[0].rain_48h_mm = 12;
  assert.match(words(clear), /<p class="why">Other risks apply: [^<]+<\/p><p class="next">12&nbsp;mm of rain in the last two days<\/p><p class="act">After heavy rain, wait a couple of days before swimming if you can\.<\/p>/);
  // The issue time stays the answer's last line.
  assert.match(h, /<p class="act">[^<]+<\/p><p class="issued">Issued /);
});

test('the embed card and the alerts file carry the line', () => {
  const GEN = '2026-09-30T08:00:00+01:00';
  const h = Embed.card(week(['high', 'low', 'low', 'low', 'low']), {generated_at: GEN}, Date.parse(GEN) + 3600e3);
  assert.match(h, /<p class="hl high">High risk today: sewage spills<\/p><p class="next">Low risk tomorrow<\/p><p class="act">Better to choose a lower day or spot\. If you do swim, try not to swallow any water\.<\/p>/);
  L.setToday('2026-09-30');   // the card sets the day from its data; put it back for the tests after
  const src = fs.readFileSync(path.join(__dirname, '../scripts/alerts.js'), 'utf8');
  assert.match(src, /action: L\.levelAction\(s\)/);   // the file itself is built and checked in tests/test_site_pages.py
});
