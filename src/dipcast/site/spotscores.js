// How the forecast has done here: one tile on a spot's page, after "What the level rests on", with the
// live scores of the spot's upstream overflows since live scoring began. The scores are per overflow,
// so these are the plain sums of its overflows' rows in data/verification_live.csv, under the Accuracy
// page's rules and warning line (src/dipcast/spot_scores.py writes data/spot_scores.json). Nothing is
// weighted by reach, so every count can be found in that CSV.
//
// Each warning count is of forecasts, as on the Accuracy page: a spill at one overflow on one day was
// forecast up to five times, from four days ahead to that morning. Below min_spills spill days (10) the
// tile gives the counts and no share, and with no spill it says there is nothing yet to judge the
// warnings by. It never says "accurate" or "safe".
//
// Not on a point clicked on the map, a spot whose forecast failed, a spot with no monitored overflow
// upstream (What the level rests on says so), or when the file is missing.
//
// A plain script, like evidence.js: in the page its names are globals (each begins scores or SCORES), and
// in Node the last lines export them (tests/site_spotscores.test.cjs, which also checks that no other
// script of the page defines one of these names).

const SCORES_FILE = 'data/spot_scores.json';
const SCORES_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h16M7 20v-6M12 20V8M17 20v-9"/></svg>';   // bars: a tally
const scoresN = x => Number(x).toLocaleString('en-GB');
const scoresPct = x => Math.round(100 * x) + '%';
const scoresPlural = (k, one, many) => `${scoresN(k)} ${k === 1 ? one : many}`;
// "29 Sept", as the evidence tile's dates.
const scoresDate = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const scoresWanted = d => !!d && !d.unlisted && !d.error && ((d.upstream_summary || {}).overflows || 0) > 0;

// The tile's sentences for one spot's counts (s, from the file's spots) and the file's own fields (g).
// Returns { say: [paragraphs], more: the fold's text }, or null when there is nothing to say.
function scoresWords(s, g) {
  if (!s || !s.overflows) return null;
  const M = s.overflows, K = s.scored_overflows || 0, min = g.min_spills || 10;
  const line = `the High risk line`;
  const rules = '<a href="verification.html#live-scoring">scoring rules</a>';
  const more = `An overflow-day is one overflow on one day. Each spill counts once for every forecast made for it, from four days ahead to that morning, as on the Accuracy page. `
    + `A warning is a spill chance of ${Math.round(100 * (g.warn_at ?? 0.4))}% or more at the overflow: where a spot right beside it reads High risk. `
    + `A share is given from ${min} spill days. Each overflow counts the same, however much of a spill would reach here. `
    + `An overflow with no live feed, or with no day that passed the ${rules}, cannot be scored.`;
  if (!K) return { more, say: [M === 1
    ? `The overflow upstream has not been scored yet. It has no live feed, or no day that passed the ${rules}.`
    : `None of the ${scoresN(M)} overflows upstream has been scored yet. They have no live feed, or no day that passed the ${rules}.`] };
  const where = K === M ? (M === 1 ? 'the overflow upstream' : M === 2 ? 'both overflows upstream' : `all ${scoresN(M)} overflows upstream`)
    : `${scoresN(K)} of the ${scoresN(M)} overflows upstream`;
  const SD = s.spill_days, fa = s.false_alarms, made = s.hits + s.misses;
  const first =`Since ${scoresDate(s.first_day || g.first_day)} the forecast has been checked at ${where}: `
    + `${scoresPlural(s.overflow_days, 'overflow-day', 'overflow-days')}, ${SD ? scoresN(SD) : 'none'} with a spill.`;
  // False alarms are forecasts too, as on the Accuracy page: one overflow-day without a spill can hold up to five.
  const falseAlarms = at => fa ? `It gave ${scoresPlural(fa, 'false alarm', 'false alarms')}: ${fa === 1 ? 'a forecast' : 'forecasts'} at ${at} on ${fa === 1 ? 'a day' : 'days'} with no spill.`
    : 'It gave no false alarms.';
  const reached = `${s.hits ? scoresN(s.hits) : 'None'} of the ${scoresN(made)} forecasts for ${SD === 1 ? 'it' : 'them'} reached ${line}.`;
  let second;
  if (!SD) second = `With no spills, there is nothing yet to judge its warnings by. ${fa ? falseAlarms(line) : `No forecast reached ${line}.`}`;
  else if (SD < min) second = `Too few spills to give a share: that takes ${min}. ${reached} ${falseAlarms('that line')}`;
  else second = `It warned of ${scoresPct(s.hits / made)} of those spills: ${reached[0].toLowerCase() + reached.slice(1)} ${falseAlarms('that line')}`
    + (s.days < 14 ? ` That is ${scoresPlural(s.days, 'day', 'days')} so far, too few to judge across different weather.` : '');
  return { more, say: [first, second] };
}

function scoresTile(d, data) {
  if (!scoresWanted(d) || !data || !data.spots) return '';
  const w = scoresWords(data.spots[d.id], data);
  if (!w) return '';
  return `<section class="tile" id="scores" aria-labelledby="scores-h"><h2 class="t-lab" id="scores-h">${SCORES_ICON}<span>How the forecast has done here</span></h2>`
    + w.say.map(p => `<p class="t-say">${p}</p>`).join('')
    + `<p class="t-say"><a href="verification.html#warnings">Every overflow's scores, on the Accuracy page</a></p>`
    + `<details class="t-more"><summary><span class="sr">How the forecast has done here: what this means</span></summary><p>${w.more}</p></details></section>`;
}

// The page asks for the file once a visit, when it first draws a spot that can have the tile.
let SCORES_LOADING = null;
const scoresLoad = () => SCORES_LOADING || (SCORES_LOADING = fetch(SCORES_FILE, { cache: 'no-cache' })
  .then(r => (r.ok ? r.json() : null)).catch(() => null));

// Called by the page as it builds a spot (index.html, render): an empty place for the tile, filled
// once the file has arrived, and left empty if another spot has been opened meanwhile.
function scoresHost(d) {
  if (!scoresWanted(d) || typeof fetch !== 'function') return '';
  scoresLoad().then(data => {
    const el = document.getElementById('scores-host');
    if (el && el.dataset.id === d.id) el.outerHTML = scoresTile(d, data);
  });
  return `<div id="scores-host" data-id="${String(d.id).replace(/[&<>"']/g, '')}"></div>`;
}

if (typeof module === 'object' && module.exports) {
  module.exports = { scoresTile, scoresWords, scoresWanted, scoresHost };
}
