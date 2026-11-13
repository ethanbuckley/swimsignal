// A first visit (30 Oct 2026) had a line under the day strip saying what to do ("Open a spot to see why. Save the ones
// you use to keep them at the top."). It went on 12 Nov 2026 (docs/DESIGN.md, "The home page, tightened"): the day's
// count and the spots at very high risk now say what the page is, and the line stood between the controls and them.
// The built page showed it to everyone until the script hid it, so a returning visitor saw it come and go.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const build = fs.readFileSync(path.join(__dirname, '../scripts/build_site.py'), 'utf8');

test('no hint line under the day strip, in the page or in the built opening', () => {
  for (const s of [app, build]) { assert.doesNotMatch(s, /strip-note/); assert.doesNotMatch(s, /Open a spot to see why/); }
});
test('the day\'s count is not said twice on a first visit', () => {
  assert.match(app, /items\.length && !\(first && !first\.hidden\) \? overview\(items\)/);
});
test('the saved visitor\'s feed is drawn at once, with its heading, and goes only when no saved spot has an overflow', () => {
  assert.match(app, /class="group tile home-feed loading" id="home-feed" aria-labelledby="feed-h">\$\{feedHead\(saved\.length\)\}/);
  assert.match(app, /if \(!have\.length\) \{ host\.innerHTML = ''; host\.hidden = true; return; \}/);
});

// 12 Nov 2026, second part: a way to a place of one's own, the research in one line, and a phone's spot page shorter.
test('a first visit has a worded "Spots near me" button that does what the pin does, and goes once a place is given', () => {
  assert.match(app, /const homeNear = \(\) => 'geolocation' in navigator && !VIEW\.here\n\s+\? `<p class="near-first"><button type="button" class="btn" data-near-first>/);
  assert.match(app, /first\.innerHTML = first\.hidden \? '' : homeNear\(\) \+ homeNow\(DATA\.spots\) \+ homeWorst\(DATA\.spots\)/);
  assert.match(app, /nf\.addEventListener\('click', \(\) => locate\('cta'\)\)/);
});
test('the research line counts only candidates in shadow whose test is still to be read, and names the first date', () => {
  const src = app.slice(app.indexOf('function researchNow(doc, iso) {'), app.indexOf('function researchLine() {'));
  const researchNow = new Function(src + '; return researchNow;')();
  const doc = {models: [{stage: 'live', window: null}, {stage: 'shadow', window: {read_on: '2026-11-16'}}, {stage: 'shadow', window: {read_on: '2026-11-23'}},
    {stage: 'shadow', window: {read_on: '2026-11-01'}}, {stage: 'scheduled', window: {read_on: '2027-03-09'}}]};
  assert.equal(researchNow(doc, '2026-11-12'), 'Research: 2 candidate models are being scored beside the live forecast, without changing it. The next test is read on 16 November.');
  assert.equal(researchNow(doc, '2026-11-20'), 'Research: 1 candidate model is being scored beside the live forecast, without changing it. The next test is read on 23 November.');
  assert.equal(researchNow(doc, '2026-12-01'), '');   // nothing running: the line keeps its standing words
  assert.equal(researchNow(null, '2026-11-12'), '');
  assert.match(app, /<a href="models\.html">What is being tested now<\/a> · <a href="lab\/">Research Lab<\/a>/);
});
test('a phone shortens a long sentence over the five days and holds the guide\'s photos behind one button', () => {
  assert.match(app, /const SENT_LINES = 5, SENT_KEEP = 3;/);
  assert.match(app, /if \(sent\.scrollHeight > line \* \(SENT_LINES \+ 0\.5\)\)/);
  assert.match(app, /id="sent-more" aria-expanded="false">Read the rest<\/button>/);
  assert.match(app, /id="g-photos" aria-expanded="false">Show \$\{photos\.length === 1 \? 'the photo' : `\$\{photos\.length\} photos`\} of the place<\/button>/);
  assert.match(app, /\n  phoneShort\(stack\);\n/);   // from phoneFolds, so a desktop is untouched
});
test('the record line under the five days gives the share of High risk forecasts followed by a spill, from ten spill days', () => {
  const s = require('../src/dipcast/site/spotscores.js'), g = {min_spills: 10, first_day: '2026-09-29'};
  const row = {overflows: 16, scored_overflows: 16, spill_days: 15, hits: 23, misses: 42, false_alarms: 53, first_day: '2026-09-29'};
  const t = s.scoresLine(row, g).replace(/<[^>]+>/g, '');
  assert.equal(t, 'Record here since 29 Sept: 23 of the 76 forecasts at the High risk line upstream (30%) were followed by a spill. How the forecast has done here');
  assert.equal(s.scoresLine({...row, spill_days: 9}, g), '');          // too few spills for a share, as in the tile
  assert.equal(s.scoresLine({...row, hits: 0, false_alarms: 0}, g), '');   // no forecast reached the line
  assert.equal(s.scoresLine({...row, scored_overflows: 0}, g), '');
  assert.equal(s.scoresLine(undefined, g), '');
  assert.doesNotMatch(s.scoresLine(row, g), /\b(safe|clean|accurate)\b/i);
});
