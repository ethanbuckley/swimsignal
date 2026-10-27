// Past spills upstream by month: a folded tile on a spot's page, after "How the forecast has done here".
// History, not a forecast. For each month, the share of days on which at least one monitored storm overflow
// upstream reported a spill, over the years whose records cover those overflows (src/dipcast/seasonal.py
// makes the counts; the build puts them on the spot as d.seasonal). It never says "safe" or "clear": a day
// with no spill reported says nothing else about the water.
//
// The table is the content, not an alternative to a chart: each row has the month, the share and the
// counts behind it, and the bar beside the share is decorative (aria-hidden). Three short columns fit 375 px.
//
// A plain script, like spotscores.js: its names begin seasonal or SEASONAL, and in Node the last lines
// export them (tests/site_seasonal.test.cjs).

const SEASONAL_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v15H4zM4 10h16M9 3v4M15 3v4"/></svg>';   // a calendar
const SEASONAL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const seasonalN = x => Number(x).toLocaleString('en-GB');
const seasonalYears = ys => ys.length === 1 ? String(ys[0]) : ys.every((y, i) => !i || y === ys[i - 1] + 1)
  ? `${ys[0]} to ${ys[ys.length - 1]}` : ys.slice(0, -1).join(', ') + ' and ' + ys[ys.length - 1];

// The tile's parts for one spot's d.seasonal: { lead, rows: [[month, share 0..1, spill days, days]], notes }.
// null when there is nothing to show.
function seasonalWords(s) {
  if (!s) return null;
  if (s.none) return { lead: 'No monitored storm overflow was found upstream of this spot, so there is no spill history to show.', rows: [], notes: [] };
  if (s.too_few) return { lead: `Too few of the ${seasonalN(s.overflows)} overflows upstream had a working monitor and a held record in any year from 2021 to 2025 `
    + `to give a fair count, so no history is shown.`, rows: [], notes: [] };
  if (!Array.isArray(s.years) || !s.years.length || !Array.isArray(s.days)) return null;
  const M = s.overflows, yrs = seasonalYears(s.years);
  const which = M === 1 ? 'the monitored overflow upstream' : `at least one of the ${seasonalN(M)} monitored overflows upstream`;
  const lead = `History, not a forecast. The share of days in each month, ${yrs}, when ${which} reported a spill.`;
  const rows = SEASONAL_MONTHS.map((m, i) => [m, s.days[i] ? s.spill[i] / s.days[i] : null, s.spill[i], s.days[i]]);
  const notes = [];
  notes.push(s.covered_min === M ? (M === 1 ? 'Its monitor worked through each year counted.' : `All ${seasonalN(M)} had a working monitor and a held record in each year counted.`)
    : `In each year counted, at least ${seasonalN(s.covered_min)} of the ${seasonalN(M)} had a working monitor (90% of the year or more) and a held record. The rest are left out, so the shares may be a little low.`);
  const short = Object.keys(s.short || {}).map(Number).sort((a, b) => a - b);
  if (short.length) notes.push(`Not counted: ${seasonalYears(short)}, when too few of them had a working monitor or a held record.`);
  if (M > 1) notes.push('Every overflow counts the same, from one beside the spot to one 60 km upstream, so a spot with many overflows upstream shows high shares.');
  notes.push('A spill day is any day (UTC) a spill was recorded at the overflow, however short. These are the monitors’ records only, not measurements of the water.');
  notes.push('From the Environment Agency’s event files for 2024 and 2025 and the companies’ own records before that, where held. <a href="terms.html#data">Credits and licences</a>.');
  return { lead, rows, notes };
}

const seasonalPct = x => x === null ? '–' : (x > 0 && x < 0.005 ? '<1%' : Math.round(100 * x) + '%');

function seasonalTile(d) {
  if (!d || d.unlisted || d.error) return '';
  const w = seasonalWords(d.seasonal);
  if (!w) return '';
  let h = `<details class="tile fold" id="seasonal"><summary><span class="t-lab">${SEASONAL_ICON}<span>Past spills upstream, by month</span></span></summary>`
    + `<p class="t-say">${w.lead}</p>`;
  if (w.rows.length) {
    h += `<table class="seasonal"><caption class="sr">Share of days with a spill reported upstream, by month</caption>`
      + `<tr><th scope="col">Month</th><th scope="col" class="num">Days with a spill</th><th scope="col" class="num">Of</th></tr>`
      + w.rows.map(([m, x, k, n]) => `<tr><th scope="row">${m}</th><td class="num"><span class="s-bar" aria-hidden="true">`
        + `<span style="width:${x === null ? 0 : Math.round(100 * x)}%"></span></span>${seasonalPct(x)}</td><td class="num">${seasonalN(k)} of ${seasonalN(n)}</td></tr>`).join('')
      + '</table>';
  }
  return h + w.notes.map(p => `<p class="small muted">${p}</p>`).join('') + '</details>';
}

if (typeof module === 'object' && module.exports) {
  module.exports = { seasonalTile, seasonalWords, seasonalYears };
}
