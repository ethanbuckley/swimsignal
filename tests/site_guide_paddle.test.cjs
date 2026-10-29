// The guides' three topics for boats and boards (guides.py and guide.js): launch, carry and paddle. Shown after the
// swimmer's topics where a guide has them; never listed as missing, since most spots are swim spots.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const g = require('../src/dipcast/site/guide.js');

test('the paddling topics come after the swimmer\'s, with their headings', () => {
  const keys = g.GUIDE_TOPICS.map(([k]) => k);
  assert.deepEqual(keys.slice(-3), ['launch', 'carry', 'paddle']);
  assert.ok(keys.indexOf('rules') < keys.indexOf('launch'));
  assert.deepEqual(Object.fromEntries(g.GUIDE_TOPICS.slice(-3)), {launch: 'Launching a boat or board', carry: 'Carrying to the water', paddle: 'Paddling here'});
});

test('a swim spot\'s guide does not list the paddling topics as missing; a paddling fact shows under its heading', () => {
  const swim = [{topic: 'parking', text: 'A car park.', status: 'confirmed', source: 'https://example.org/', source_name: 'Owner'}];
  const gaps = g.guideGaps({facts: swim});
  assert.match(gaps, /Not in this guide yet: path to the water, getting in, getting out, toilets, changing, fees and booking, opening times, who can swim\./);
  assert.doesNotMatch(gaps, /launch|carry|paddling/i);
  const src = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/guide.js'), 'utf8');
  assert.match(src, /!have\.has\(k\) && !GUIDE_PADDLE\.has\(k\)/);
});

test('the guides that have them say so in the National Trust\'s words', () => {
  const read = id => fs.readFileSync(path.join(__dirname, '../guides', `${id}.toml`), 'utf8');
  assert.match(read('bw-ukd1203-45700'), /topic = "launch"\ntext = "You can launch your own canoes, kayaks, inflatable dinghies and paddleboards from the south end of the park/);
  for (const id of ['bw-ukd1101-45800', 'derwent-water-calfclose'])
    assert.match(read(id), /topic = "paddle"\ntext = "Do not land on Lord's Island, and keep out of the no-paddle zone/);
});
