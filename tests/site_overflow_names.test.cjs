// Plain overflow names (levels.js, plainName and overflowNames; markets plan B1/T1). The fixture is every
// distinct overflow name in swimsignal.co.uk/data/overflows.geojson on 6 Oct 2026: 14,064 names for
// 14,374 overflows, plus 257 with no name, which show their id. tests/test_overflow_names.py checks the
// Python copy gives the same names.
// On its own: node --test tests/site_overflow_names.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('../src/dipcast/site/levels.js');

const NAMES = fs.readFileSync(path.join(__dirname, 'fixtures', 'overflow_names.txt'), 'utf8').split('\n').filter(Boolean);
const CODE = /^(?:STW|STWs|WwTW|WWTW|WTW|WRC|WRW|SPS|SPST|PS|SP|TPS|IPS|CSO|SSO|SSTO|CEO|EO|SO|OV|PSCSOEO)\b/;

test('the examples in the markets plan, and one of each company\'s ways of writing a name', () => {
  const cases = [
    ['Addingham/NO 1 SPS/Preliminary Treatment-STW/6Xdwf Overflow', 'Addingham sewage works overflow'],
    ['ADDINGHAM/NO 1 SPS/PRELIMINARY TREATMENT-STW/3XDWF OVERFLOW', 'Addingham sewage works storm tank overflow'],
    ['RIVADALE VIEW/CSO', 'Rivadale View storm overflow'],
    ['Bridge Lane/CSO', 'Bridge Lane storm overflow'],
    ['Kettlewell/STW', 'Kettlewell sewage works overflow'],
    ['Cassington STW', 'Cassington sewage works overflow'],
    ['LOW Mill Lane 179/CSO', 'LOW Mill Lane 179 storm overflow'],             // mixed case: nameCase's, as before
    ['BOROUGHBRIDGE/NO 2 STW', 'Boroughbridge sewage works overflow 2'],
    ['SEAHAM CSO NO 8', 'Seaham storm overflow 8'],
    ['BIRMINGHAM - LIONEL STREET (CSO)', 'Birmingham, Lionel Street storm overflow'],      // Severn Trent
    ['ASHOVER STW (SSTO)', 'Ashover sewage works storm tank overflow'],
    ['ASHOVER STW (CSO)', 'Ashover sewage works overflow'],
    ['59 BARTON DRIVE_CSO_NEWTON ABBOT', '59 Barton Drive, Newton Abbot storm overflow'],  // South West Water
    ['IVYBRIDGE STW_SSO_IVYBRIDGE 1', 'Ivybridge sewage works storm tank overflow 1'],
    ['SENNEN SPS_PSCSOEO_LANDS END', 'Sennen, Lands End pumping station overflow'],
    ['STONE HILL ROAD EGERTON SSO - 115858', 'Stone Hill Road Egerton storm sewage overflow'],   // Southern
    ['ABBEY ROAD FAVERSHAM CEO - 103283', 'Abbey Road Faversham pumping station overflow'],
    ['HABROUGH-CRAVENS LA SP', 'Habrough-Cravens La pumping station overflow'],           // Anglian
    ['KINGS LYNN-FRIARS OV', 'Kings Lynn-Friars storm overflow'],
    ['Mobberley Road Combined Sewer Overflow (Site ID 272GZ) (MAC0122)', 'Mobberley Road storm overflow'],   // United Utilities
    ['250 metres d/s Ashton Road (Bardsley PS) CSO', '250 metres d/s Ashton Road storm overflow'],
    ['CSO NEW DRIVE RECREATION GROUND', 'New Drive Recreation Ground storm overflow'],    // Northumbrian
    ['FELLSIDE CSO (DER 174)', 'Fellside storm overflow'],
    ['STOKE ON TRENT - HIGH STREET (CSO)', 'Stoke on Trent, High Street storm overflow'],
    ['95/97 Craig Road CSO', '95/97 Craig Road storm overflow'],
    ['Grasmere Waste Water Treatment Works', 'Grasmere sewage works overflow'],
    ['WORTH MATRAVERS STORM TANK', 'Worth Matravers storm tank overflow'],
  ];
  for (const [name, plain] of cases) assert.equal(L.plainName(name), plain, name);
});

test('a name without a code, or with nothing left once the codes are out, is nameCase\'s: never a guessed place', () => {
  for (const n of ['BRISTOL WELLS ROAD / GREENMORE ROAD', 'Chester Greenbank', 'Streatham storm relief E', 'XX CSO', 'CSO', 'STW'])
    assert.equal(L.plainName(n), L.nameCase(n), n);
  assert.equal(L.plainName(null), '');
  assert.equal(L.plainName('   '), '');
});

test('over every name in overflows.geojson: none empty, none starting with a code, no code left in a plain name', () => {
  let fellBack = 0;
  for (const n of NAMES) {
    const p = L.plainName(n);
    assert.ok(p.trim(), `empty for ${n}`);
    assert.ok(!CODE.test(p), `${n} gives ${p}`);
    if (p === L.nameCase(n.replace(/\s+/g, ' ').trim())) { fellBack++; continue; }
    assert.match(p, /(?:overflow|overflow \d+)$/, n);
    assert.ok(!/\b(?:STW|WwTW|WWTW|SPS|CSO|SSO|SSTO|CEO|PSCSOEO)\b/.test(p), `${n} gives ${p}`);
    assert.ok(p.length <= n.length + 32, `${n} gives ${p}`);
  }
  // 1,677 of 14,064 on 6 Oct 2026, most of them Wessex Water's, whose names carry no code.
  assert.ok(fellBack <= 1700, `${fellBack} names fell back`);
});

test('a page shows the plain name with the company\'s beside it, once where they are the same', () => {
  assert.deepEqual(L.overflowNames({site_id: 'YW1', site_name: 'ILKLEY WwTW'}), {plain: 'Ilkley sewage works overflow', own: 'Ilkley WwTW'});
  assert.deepEqual(L.overflowNames({site_id: 'WX1', site_name: 'WAREHAM NORTH BRIDGE'}), {plain: 'Wareham North Bridge', own: ''});
  assert.deepEqual(L.overflowNames({site_id: 'TW9', site_name: null}), {plain: 'TW9', own: ''});
});
