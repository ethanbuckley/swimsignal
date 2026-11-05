// Sampling planner (sampling-planner.html): the cost lines under the form, from the samples, the price of one sample
// and the sites to cover that the reader sets, and the simulation run nearest in samples per site. The runs are the
// form's data-runs, which build_site.write_sampling_planner copies from the export (docs/SAMPLING-PLANNER-CONTRACT-v1.md).
// Arithmetic and copied results only: it says nothing about where to sample, and every policy costs the same per sample.

const SP_WEEKS = 20;   // the simulation's season, 20 weeks
const SP_NEAR = 1.5;   // a run is near when samples per site are within this factor of its own

const spNum = (v, d = 0) => v.toLocaleString('en-GB', { maximumFractionDigits: d });
const spSmall = v => v.toFixed(6).replace('-', '−');   // a gain in P, to six places as the page's tables write it

// The run whose samples per never-sampled site is nearest the reader's, if within SP_NEAR of it; else null.
function spNearest(runs, perSite) {
  if (!(perSite > 0)) return null;
  let best = null;
  for (const r of runs) {
    const off = Math.abs(Math.log(perSite / r.per_site));
    if (off <= Math.log(SP_NEAR) && (!best || off < best.off)) best = { run: r, off };
  }
  return best && best.run;
}

// The lines under the form, as plain sentences.
function spLines(runs, samples, price, sites) {
  if (!(samples > 0) || !(price >= 0) || !(sites > 0)) return ['Enter a number of samples, a price and a number of sites.'];
  const out = [`${spNum(samples)} samples at £${spNum(price, 2)} each: £${spNum(samples * price, 2)} for the season, before travel and staff time.`,
    `Over a ${SP_WEEKS}-week season, about ${spNum(samples / SP_WEEKS, 1)} a week.`];
  out.push(samples < sites
    ? `Fewer samples than sites: at least ${spNum(sites - samples)} of the ${spNum(sites)} sites would get none.`
    : `Shared equally over ${spNum(sites)} sites, about ${spNum(samples / sites, 1)} each.`);
  const main = runs.filter(r => r.tau > 0);   // the τ = 0 run tests a world with no site differences: not a budget
  const r = spNearest(main, samples / sites);
  if (!r) {
    out.push(`The simulation tried ${main.map(x => spNum(x.per_site)).join(' and ')} samples per never-sampled site. ` +
      `About ${spNum(samples / sites, 1)} per site is outside that, so it says nothing about this budget.`);
    return out;
  }
  const c = r.info_vs.COVER;
  const clear = c.ci95[0] > 0 ? 'The interval is above 0.' : 'The interval includes 0: no clear difference.';
  out.push(`Nearest simulated case: ${spNum(r.per_site)} samples per never-sampled site (${spNum(r.budget)} samples over 12 sites). ` +
    `There the information policy had lower error than equal coverage in ${spNum(c.share_info_lower * 100, 1)}% of ` +
    `${spNum(r.replications)} made-up worlds, and its mean gain was ${spSmall(c.mean_gain)} (95% interval ` +
    `${spSmall(c.ci95[0])} to ${spSmall(c.ci95[1])}). ${clear}` +
    (r.run === 'main' ? ' The test needed 60%, so the policy failed.' : ' This run was a check that decided nothing.') +
    ' This is a simulation, not a result in real water.');
  return out;
}

function spRender(form) {
  const runs = JSON.parse(form.dataset.runs || '[]');
  const v = n => Number(form.elements[n].value);
  const box = document.getElementById('sp-out');
  box.replaceChildren(...spLines(runs, v('samples'), v('price'), v('sites')).map(t => {
    const p = document.createElement('p');
    p.textContent = t;
    return p;
  }));
}

if (typeof document !== 'undefined') {
  const form = document.getElementById('sp-calc');
  if (form) {
    form.addEventListener('input', () => spRender(form));
    form.addEventListener('submit', e => { e.preventDefault(); spRender(form); });
    spRender(form);
  }
}

if (typeof module === 'object' && module.exports) {
  module.exports = { spLines, spNearest };
}
