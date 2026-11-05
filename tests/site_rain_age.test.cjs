// How old the rain behind a spot is (levels.js, rainAgeLine): one sentence under "Issued" when the oldest
// rain forecast the spot used was over 6 hours old at the issue (forecast.py, assumptions.rain_age_h),
// and nothing otherwise. The page draws it in answerWords, and the build's copy of the spot's opening
// (scripts/prerender_spots.js) runs the same code. tests/test_rain_forecast_age.py has the Python side.
process.env.TZ = 'Europe/London';   // as the build runs the prerender
const {test} = require('node:test');
const assert = require('node:assert/strict');
const L = require('../src/dipcast/site/levels.js');
const spots = require('../scripts/prerender_spots.js');

// rain_issued_at as forecast.py writes it: UK time to the minute.
const rained = (iso, h, more = {}) => ({assumptions: {max_upstream_km: 60, rain_issued_at: iso, rain_age_h: h, ...more}});

test('over 6 hours old: when the rain is from, in UK time, and why', () => {
  L.setToday('2026-10-24');
  assert.equal(L.rainAgeLine(rained('2026-10-23T09:00:00+01:00', 25.5, {rain_fallback: 'no answer'})),
    'Rain forecast from 09:00 yesterday: Open-Meteo did not send a newer one.');
  // The day's limit of requests is the site's own, so Open-Meteo is not blamed; nor where no reason is known.
  assert.equal(L.rainAgeLine(rained('2026-10-24T03:10:00+01:00', 7.2, {rain_fallback: 'daily limit'})),
    'Rain forecast from 03:10 today: this update had none newer.');
  assert.equal(L.rainAgeLine(rained('2026-10-24T03:10:00+01:00', 7.2)), 'Rain forecast from 03:10 today: this update had none newer.');
  // Only some of the spot's rain is that old.
  assert.equal(L.rainAgeLine(rained('2026-10-23T09:00:00+01:00', 25.5, {rain_fallback: 'no answer', rain_mixed: true})),
    'Part of the rain forecast is from 09:00 yesterday: Open-Meteo did not send a newer one.');
  // Read the day after (the device's today), the day before yesterday is named.
  L.setToday('2026-10-25');
  assert.equal(L.rainAgeLine(rained('2026-10-23T09:00:00+01:00', 25.5, {rain_fallback: 'no answer'})),
    'Rain forecast from 09:00 on Friday: Open-Meteo did not send a newer one.');
});

test('6 hours or under, or no rain time, says nothing', () => {
  L.setToday('2026-10-24');
  assert.equal(L.rainAgeLine(rained('2026-10-24T05:00:00+01:00', 6)), '');
  assert.equal(L.rainAgeLine(rained('2026-10-24T05:00:00+01:00', 1.9, {rain_fallback: 'no answer'})), '');
  assert.equal(L.rainAgeLine(rained(undefined, 30)), '');
  assert.equal(L.rainAgeLine({assumptions: {max_upstream_km: 60}}), '');   // a forecast from before the field, or a clicked point
  assert.equal(L.rainAgeLine({}), '');
  assert.equal(L.rainAgeLine(null), '');
});

test('the time is UK time whatever the device is set to, and GMT after the clocks go back', () => {
  const tz = process.env.TZ;
  try {
    process.env.TZ = 'Pacific/Auckland';
    L.setToday('2026-10-26');
    assert.equal(L.rainAgeLine(rained('2026-10-26T08:30:00+00:00', 8, {rain_fallback: 'no answer'})),
      'Rain forecast from 08:30 today: Open-Meteo did not send a newer one.');
    assert.equal(L.rainAgeLine(rained('2026-10-25T23:30:00+00:00', 17)), 'Rain forecast from 23:30 yesterday: this update had none newer.');
  } finally { process.env.TZ = tz; }
});

const SPOT = {id: 'a', name: 'A', kind: 'river', source: 'curated', upstream_summary: {overflows: 3}, location: {mode: 'river'},
  now: {label: 'low', discharging_upstream: 0}, contributors: [],
  days: ['2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02', '2026-10-03'].map(date => ({date, risk: 0.01, label: 'low'}))};
const opening = assumptions => spots.prerender({generated_at: '2026-09-29T08:00:00+01:00', spots: [{...SPOT, assumptions}]}, 'https://example.org/swim/').a;

test("the spot's opening has the sentence straight under Issued when the rain is over 6 hours old, and not under", () => {
  const old = opening({max_upstream_km: 60, rain_issued_at: '2026-09-28T09:00:00+01:00', rain_age_h: 23, rain_fallback: 'no answer'});
  assert.ok(old.includes('<p class="issued">Issued Tue 08:00</p></div><p class="issued">Rain forecast from 09:00 yesterday: Open-Meteo did not send a newer one.</p>'),
    old.match(/<p class="issued">.*?<\/p>(<p[^>]*>.*?<\/p>)?/)[0]);
  const fresh = opening({max_upstream_km: 60, rain_issued_at: '2026-09-29T06:30:00+01:00', rain_age_h: 1.5});
  assert.ok(fresh.includes('<p class="issued">Issued Tue 08:00</p>') && !fresh.includes('Rain forecast from'));
  assert.ok(!opening({max_upstream_km: 60}).includes('Rain forecast from'));
});
