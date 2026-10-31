// Lab results an organisation sent (src/dipcast/site/measured.js): a tile of their own, set apart from
// the forecast, with who sent each result and that SwimSignal did not take or check it; never
// "verified" or "safe"; E. coli against 900 only as the page already explains it.
// node --test tests/site_measured.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const { join } = require('path');
const m = require('../src/dipcast/site/measured.js');
const ev = require('../src/dipcast/site/evidence.js');

const NOW = Date.parse('2026-10-20T17:00:00+01:00');
const sample = (extra = {}) => ({ sampled_at: '2026-10-17T08:30+01:00', ecoli: 1200, enterococci: 10, enterococci_qualifier: '<',
  lab: 'Example Water Lab', ukas: true, method: 'membrane filtration', supplier: 'Example Swim Club', received: '2026-10-19', ...extra });
const spot = (measured, extra = {}) => ({ id: 'bw-uke4100-08901', name: 'Wharfe at Cromwheel, Ilkley', measured, ...extra });
const text = html => html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');

test('a result says when, how long ago, the counts, who sent it and the lab in their words', () => {
  const html = m.measuredTile(spot([sample()]), NOW);
  assert.match(html, /^<section class="tile" id="measured" aria-labelledby="measured-h">/);
  const t = text(html);
  assert.match(t, /Measured: lab results sent to SwimSignal/);
  assert.match(t, /SwimSignal did not take or check the samples, and they do not change the forecast\./);
  assert.match(t, /Sampled 17 Oct, 08:30 3 days ago/);
  assert.match(t, /E\. coli: 1,200 per 100 ml, over 900\. Intestinal enterococci: under 10 per 100 ml\./);
  assert.match(t, /Sent by Example Swim Club, 19 Oct\. Lab: Example Water Lab, which Example Swim Club says is UKAS-accredited\. Method: membrane filtration\./);
  assert.match(t, /Each count is for the moment its sample was taken: after rain it can change within hours\./);
  // 900 is explained in the page's own words, and links to them (the About section's E. coli entry).
  assert.match(html, /900 per 100&nbsp;ml is the line the <a href="#about-ecoli">E\.&nbsp;coli estimate<\/a> uses: the threshold in the inland "sufficient" rating, which is worked out over four seasons, not a pass or fail for one sample\./);
});

test('never verified, safe, clean, certified or a pass; no level colour', () => {
  const many = [sample(), sample({ sampled_at: '2026-10-10T08:00+01:00', ecoli: 10, ecoli_qualifier: '<', ukas: false }),
    sample({ sampled_at: '2026-10-05T08:00+01:00', ecoli: undefined, lab: undefined, ukas: undefined, method: undefined })];
  const html = m.measuredTile(spot(many), NOW);
  assert.doesNotMatch(text(html), /verified|safe|clean|certified|\bpass(es|ed)?\b(?! or fail)|good to swim/i);
  assert.doesNotMatch(html, /class="[^"]*\b(low|moderate|high|veryhigh|clear)\b/, 'a count is not a level');
  assert.match(text(html), /which Example Swim Club says is not UKAS-accredited/);
  assert.match(text(html), /Sent by Example Swim Club, 19 Oct\. The lab is not named\./);
});

test('a count given as a limit is compared with 900 only where the limit settles it, as the EA sample row', () => {
  for (const [n, q, vs] of [[1200, '', 'over 900'], [900, '', 'not over 900'], [85, '', 'under 900'], [10, '<', 'under 900'],
    [1000, '<', ''], [24196, '>', 'over 900'], [100, '>', '']]) {
    assert.equal(m.measuredVs(n, q), vs, `${q}${n}`);
    // evidence.js's "Latest lab sample" says the same of the same count.
    const said = ev.evidenceSample({ taken_at: '2026-10-17T08:30+01:00', ecoli: n, ...(q ? { qualifier: q } : {}) }, NOW);
    assert.ok(vs ? said.endsWith(`: ${vs}.`) : !/900/.test(said), said);
  }
  assert.equal(m.measuredSays(sample({ ecoli: 24196, ecoli_qualifier: '>', enterococci: undefined })), 'E.&nbsp;coli: over 24,196 per 100&nbsp;ml, over 900.');
  // Enterococci have no line on the page: the count alone, and no 900 sentence when there is no E. coli.
  const ent = m.measuredTile(spot([sample({ ecoli: undefined, enterococci: 400, enterococci_qualifier: undefined })]), NOW);
  assert.match(text(ent), /Intestinal enterococci: 400 per 100 ml\./);
  assert.doesNotMatch(ent, /900/);
});

test('only the last 30 days, newest first; nothing at all without a recent result', () => {
  const rows = m.measuredRecent(spot([sample({ sampled_at: '2026-09-15T08:00+01:00' }), sample({ sampled_at: '2026-10-03T08:00+01:00' }), sample()]), NOW);
  assert.deepEqual(rows.map(s => s.sampled_at), ['2026-10-17T08:30+01:00', '2026-10-03T08:00+01:00']);
  assert.equal(m.measuredTile(spot([sample({ sampled_at: '2026-09-15T08:00+01:00' })]), NOW), '');
  assert.equal(m.measuredTile(spot(undefined), NOW), '');
  assert.equal(m.measuredTile(spot([sample()], { unlisted: true }), NOW), '', 'a point clicked on the map');
  assert.equal(m.measuredTile(spot([sample()], { detail_missing: true }), NOW), '', "its file did not arrive: not \"none\"");
  assert.equal(m.measuredTile(spot([{ sampled_at: 'soon', ecoli: 5, supplier: 'x' }, { sampled_at: '2026-10-17T08:30+01:00', ecoli: 'lots', supplier: 'x' }]), NOW), '');
  // A year other than this one is named.
  assert.equal(m.measuredWhen('2025-12-30T08:30+00:00', Date.parse('2026-01-02T12:00:00Z')), '30 Dec 2025, 08:30');
  assert.equal(m.measuredWhen('2026-07-01T07:05:00Z', NOW), '1 Jul, 08:05', 'UK time');
});

test('past four results, three show and "Show all" opens the rest', () => {
  const six = [17, 15, 13, 11, 9, 7].map(d => sample({ sampled_at: `2026-10-${String(d).padStart(2, '0')}T08:00+01:00` }));
  const html = m.measuredTile(spot(six), NOW);
  const shown = html.slice(0, html.indexOf('<div class="m-more" hidden>'));
  assert.equal((shown.match(/class="factor"/g) || []).length, 3);
  assert.equal((html.match(/class="factor"/g) || []).length, 6);
  assert.match(html, /<button type="button" class="btn quiet" id="m-all" aria-expanded="false">Show all 6 results<\/button>/);
  assert.doesNotMatch(m.measuredTile(spot(six.slice(0, 4)), NOW), /m-all|m-more/, 'four show whole: the button never hides one');
  // The click: the box shows and the button goes.
  const box = { hidden: true }, button = { removed: false, remove() { this.removed = true; },
    closest: q => (q === '#m-all' ? button : { querySelectorAll: () => [box] }) };
  m.measuredClick({ target: button });
  assert.equal(box.hidden, false); assert.ok(button.removed);
});

test('what a sender writes is escaped', () => {
  const html = m.measuredTile(spot([sample({ supplier: '<img src=x onerror=alert(1)>', lab: 'A & B "Labs"', method: "<b>'x'</b>" })]), NOW);
  assert.doesNotMatch(html, /<img|<b>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /A &amp; B &quot;Labs&quot;/);
});

test("the page draws the tile at the water, after the EA's rating and before the guide, and loads the script", () => {
  const site = join(__dirname, '../src/dipcast/site');
  const html = fs.readFileSync(join(site, 'index.html'), 'utf8');
  const at = html.indexOf("typeof measuredTile === 'function' ? measuredTile(d, Date.now()) : ''");
  assert.ok(at > html.indexOf('atWater = fx.filter(o => o.icon === ICON.rating)') && at < html.indexOf("typeof guideTile === 'function' ? guideTile(d, serverToday)"));
  assert.ok(html.indexOf('src="evidence.js"') < html.indexOf('src="measured.js"') && html.indexOf('src="measured.js"') < html.indexOf('<script>\n'));
  // The page's scripts share one global scope: no other defines one of these names.
  const names = src => new Set([...src.matchAll(/^(?:const|let|var|function|async function|class)\s+([A-Za-z_$][\w$]*)/gm)].map(x => x[1]));
  const mine = names(fs.readFileSync(join(site, 'measured.js'), 'utf8'));
  const others = [html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')),
    ...fs.readdirSync(site).filter(f => f.endsWith('.js') && !['measured.js', 'sw.js'].includes(f)).map(f => fs.readFileSync(join(site, f), 'utf8'))];
  assert.deepEqual(others.flatMap(src => [...names(src)].filter(n => mine.has(n))), []);
  assert.ok([...mine].every(n => /^(measured|MEASURED)/.test(n)), [...mine].join(', '));
});

test("the spot pages' prerender does not reach the tile: it draws when the spot's file arrives", () => {
  const { reached } = require('../scripts/prerender_spots.js');
  assert.doesNotMatch(reached(fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8')), /measuredTile/);
});

test('a result without a time is said as its day, never as midnight', () => {
  const html = m.measuredTile(spot([sample({ sampled_at: '2026-10-17', time_known: false })]), NOW);
  assert.match(text(html), /Sampled 17 Oct, time not given 3 days ago/);
  assert.doesNotMatch(html, /00:00|01:00/);
});
