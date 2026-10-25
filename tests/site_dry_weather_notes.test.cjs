// The note beside an overflow that spilled on many of its dry days (index.html, dryWeatherNote, from
// build_site.attach_dry_weather and data/raw/dry_weather_spills.csv). Rows as Salisbury's list might have them:
// Hurdcott WwTW noted, Barford St Martin noted and listed for an upgrade too, Salisbury WRC not noted.
// node --test tests/site_dry_weather_notes.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const NOW = Date.parse('2026-10-25T12:00:00Z');
const html = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');
const pageSrc = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>')).split('\n');
const pageDefs = names => names.map(n => { const i = pageSrc.findIndex(l => l.startsWith(`const ${n} =`) || l.startsWith(`function ${n}(`) || l.startsWith(`let ${n} =`));
  assert.ok(i >= 0, `no ${n} in index.html`);
  let j = i + 1; while (j < pageSrc.length && /^[\s})\]+]/.test(pageSrc[j])) j++;
  return pageSrc.slice(i, j).join('\n'); }).join('\n');
class FixedDate extends Date { constructor(...a) { if (!a.length) super(NOW); else super(...a); } static now() { return NOW; } }

function page() {
  const ctx = vm.createContext({ Date: FixedDate, L: { circleMarker: () => ({ bindTooltip: () => ({ addTo() {} }) }) }, contribLayer: null });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/dipcast/site/levels.js'), 'utf8') + '\nsetToday("2026-10-25");', ctx);
  vm.runInContext(pageDefs(['esc', 'fmt', 'feedTime', 'endedOn', 'runningAtLastAnswer', 'statusText', 'colourFor', 'drawnStatus', 'sinceTime',
    'spillFor', 'statusSaid', 'glyph', 'ICON', 'PAGE_ID', 'upgradeDay', 'upgradeNote', 'EA_EVENTS', 'dryWeatherNote', 'overflowTile']), ctx);
  return ctx;
}
const text = h => h.replace(/<\/?a\b[^>]*>/g, '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;| /g, ' ').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

const EA = 'https://environment.data.gov.uk/dataset/e9677ac1-fd32-4ceb-88a0-2735be5f27c7';
const row = extra => ({ company: 'Wessex Water', receiving_watercourse: 'River Bourne', lat: 51.07, lon: -1.78, status: 0, has_live: true,
  data_state: 'live', latest_event_start: '2026-10-20T08:00:00+00:00', latest_event_end: '2026-10-20T09:00:00+00:00', lta_spills: 60,
  snap_confidence: 'high', position_source: 'live', distance_km: 3, lake_distance_km: 0, travel_h: 4, weight: 0.4,
  p_spill_today: 0.3, p_spill_days: [0.3, 0.3, 0.3, 0.3, 0.3], now_contribution: 0, ...extra });
const hurdcott = row({ site_id: 'WXW00571', site_name: 'HURDCOTT WASTEWATER TREATMENT WORKS', dry_weather: { year: 2025, days: 48, dry_days: 94 } });
const salisbury = row({ site_id: 'WXW00700', site_name: 'SALISBURY WRC', distance_km: 1, travel_h: 1, weight: 0.6 });
const barford = row({ site_id: 'WXW00104', site_name: 'BARFORD ST MARTIN WRC', distance_km: 12, travel_h: 15, weight: 0.2,
  dry_weather: { year: 2025, days: 21, dry_days: 91 },
  upgrade: { company: 'Wessex Water', stage: 'upgrading', match: 'name', source_name: 'Barford St Martin WRC',
    url: 'https://www.wessexwater.co.uk/example', checked: '2026-10-25', returns_to: 2025 } });
const HURDCOTT = 'Spilled on 48 of 94 dry days in 2025 (EA records).';

test('the note sits under the noted overflow only, in the stated words, with the definition and the data linked', () => {
  const h = vm.runInContext('overflowTile', page())({ id: 'x', contributors: [hurdcott, salisbury, barford] }, 3);
  const li = h.split(/<li[^>]*>/).slice(1);
  assert.equal(li.length, 3);
  assert.ok(text(li[0]).includes(HURDCOTT), text(li[0]));
  assert.doesNotMatch(text(li[1]), /dry days|EA records/, 'an overflow without counts gets no note');
  assert.ok(text(li[2]).includes('Spilled on 21 of 91 dry days in 2025 (EA records).'), text(li[2]));
  assert.equal((h.match(/Spilled on/g) || []).length, 2, 'once per noted overflow, nowhere else in the tile');
  assert.equal((h.match(new RegExp(EA.replace(/[.]/g, '\\.'), 'g')) || []).length, 2);
  assert.ok(li[0].includes(`<div class="ov-meta">Spilled on 48 of 94 <a href="methods.html#dry-weather">dry days</a> in 2025 (<a href="${EA}">EA records</a>).</div>`));
  // Inside its own row, after the row's status line; below an upgrade note where there is one.
  assert.ok(li[0].indexOf('Spilled on') > li[0].indexOf('not discharging'));
  assert.ok(li[2].indexOf('Spilled on') > li[2].indexOf('says it is upgrading'));
  // Not in the tile's caption.
  assert.doesNotMatch(text(h.slice(h.indexOf('<p class="sub">'))), /dry/);
});

test('counts the page could not say truthfully give no note', () => {
  const note = vm.runInContext('dryWeatherNote', page());
  assert.equal(text(note(hurdcott)), HURDCOTT);
  for (const d of [undefined, null, {}, { year: 2025, days: 0, dry_days: 94 }, { year: 2025, days: 95, dry_days: 94 },
    { year: 2025, days: '48', dry_days: 94 }, { year: 2025, days: 4.5, dry_days: 94 }, { days: 48, dry_days: 94 }])
    assert.equal(note({ ...hurdcott, dry_weather: d }), '', JSON.stringify(d));
});
