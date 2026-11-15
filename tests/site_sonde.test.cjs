// The Ammonium sensor tile (index.html, sondeTile; build_site.attach_sondes, docs/SONDE-READINGS-CONTRACT-v1.md), run in
// Node beside levels.js as in the browser: a reading is shown only with the sensor's name, how far up the river it is,
// how old the reading is now and the EA's own word for it. Never a level, a colour or advice; no reading is not clean.
// On its own: node --test tests/site_sonde.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

const pageSrc = (() => { const html = fs.readFileSync(join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
  return html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n'); })();
function pageDefs(names) {
  return names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`));
    assert.ok(i >= 0, `no ${n} in index.html`);
    let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
    return pageSrc.slice(i, j).join('\n'); }).join('\n');
}
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(join(__dirname, '../src/dipcast/site/levels.js'), 'utf8'), ctx);
vm.runInContext(pageDefs(['esc', 'fmt', 'glyph', 'ICON', 'ago', 'agoSpan', 'SONDE_SAID', 'SONDE_NONE', 'SONDE_NAMES', 'sondeNum',
  'sondeVal', 'sondeAgeH', 'sondeFresh', 'sondeQual', 'sondeLine', 'sondeTile']), ctx);
const sondeTile = vm.runInContext('sondeTile', ctx), sondeLine = vm.runInContext('sondeLine', ctx);
const plain = x => x.replace(/<span data-ago="\d+">([^<]*)<\/span>/g, '$1').replace(/&nbsp;/g, ' ');

const hoursAgo = h => new Date(Date.now() - h * 3600e3).toISOString();
const reading = (value, unit, h = 0.4) => ({ value, unit, observed_at: hoursAgo(h), age_hours: 0.3, quality: 'Unchecked' });
const series = (n, v = 1.9) => Array.from({ length: n }, (_, i) => [hoursAgo(n - i - 0.6), v + (i % 3) * 0.05]);
// As build_site.attach_sondes wrote it for River Stour, Dedham on 13 Nov 2026.
const boxted = { station_id: 'E06651A', station: 'Boxtedmill', where: 'at Boxtedmill', river: 'Stour',
  url: 'https://environment.data.gov.uk/hydrology/station/E06651A', direction: 'upstream', river_km: 7.4,
  readings: { ammonium: reading(1.89, 'mg/L'), 'dissolved-oxygen': reading(86.0, '% saturation'), turbidity: reading(4.38, 'NTU') },
  series: series(24) };

test('a reading: the sensor, how far up the river, how old, the EA\'s word, and what ammonium is not', () => {
  const t = sondeTile(boxted);
  assert.equal(t.label, 'Ammonium sensor');
  assert.equal(t.fig, '1.89');
  assert.equal(t.unit, 'mg/L, measured');
  assert.ok(t.live && t.wide);
  assert.match(plain(t.say), /^Measured at Boxtedmill on the Stour, 7\.4 km upstream, 24 min ago\. The Environment Agency labels it Unchecked\./);
  assert.match(t.say, /not a count of bacteria and not a sign that the water is fit to swim in/);
  assert.equal(plain(t.note), 'The same sensor: dissolved oxygen 86% of saturation (Unchecked, 24 min ago); turbidity 4.38 NTU (Unchecked, 24 min ago).');
  assert.match(t.more, /No reading does not mean clean water\./);
  assert.match(t.more, /Not part of the pollution level/);
  assert.match(t.more, /href="https:\/\/environment\.data\.gov\.uk\/hydrology\/station\/E06651A"/);
  assert.match(t.more, /Open Government Licence v3\.0/);
  assert.match(t.vis, /<svg class="sline"/);
});

test('no level, colour or advice comes from it', () => {
  const t = sondeTile(boxted);
  for (const k of ['word', 'wordTone', 'figTone', 'rel']) assert.equal(t[k], undefined, k);
  assert.doesNotMatch(Object.values(t).join(' '), /\b(safe|clean water to|low risk|high risk|avoid)\b/i);
});

test('the at-the-spot wording, and at the spot within reach either way', () => {
  assert.match(plain(sondeTile({ ...boxted, direction: 'at', river_km: 0.2 }).say), /^Measured at Boxtedmill on the Stour, at the spot, /);
});

test('a reading over a day old shows no figure and says how old it is', () => {
  const t = sondeTile({ ...boxted, readings: { ammonium: reading(1.89, 'mg/L', 26) } });
  assert.equal(t.fig, '–');
  assert.equal(plain(t.say), 'Last reading at Boxtedmill on the Stour, 7.4 km upstream, 26 h ago: too old to use. No reading does not mean clean water.');
});

test('a quiet sensor says so, and that no reading is not clean water', () => {
  const t = sondeTile({ ...boxted, readings: {} });
  assert.equal(t.fig, '–');
  assert.equal(plain(t.say), 'No ammonium reading in the last day from the sensor at Boxtedmill on the Stour, 7.4 km upstream. No reading does not mean clean water.');
});

test('the others ride along only while fresh', () => {
  const t = sondeTile({ ...boxted, readings: { ammonium: reading(0.05, 'mg/L'), turbidity: reading(4.38, 'NTU', 30) } });
  assert.equal(t.fig, '0.05');
  assert.equal(t.note, '');
});

test('downstream, no distance or no name: no tile', () => {
  assert.equal(sondeTile({ ...boxted, direction: 'downstream' }), null);
  assert.equal(sondeTile({ ...boxted, river_km: null }), null);
  assert.equal(sondeTile({ ...boxted, station: '' }), null);
  assert.equal(sondeTile(null), null);
});

test('the day\'s line needs eight readings and draws from zero', () => {
  assert.equal(sondeLine(series(5)), '');
  const svg = sondeLine(series(24, 2));
  assert.match(svg, /aria-hidden="true"/);
  assert.doesNotMatch(svg, /fill="|stroke="#/);   // no colour in the markup: the stylesheet's ink
});
