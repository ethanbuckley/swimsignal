// Research Lab exhibit 8, a lake the model has never seen. Every figure is read from reads.json (scripts/lab_lake_reads.py,
// made from committed results); nothing is typed here. The typical-lake check on seen years is labelled development.
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const n3 = v => Number(v).toFixed(3), pct = v => Math.round(100 * v) + '%', pct1 = v => (100 * v).toFixed(1) + '%';
  const int = v => Number(v).toLocaleString('en-GB');
  const ci = (c, f = n3) => `${f(c[0])} to ${f(c[1])}`;
  const COL = { model: 'var(--brand)', prod: 'var(--ink)', dev: 'var(--faint)', bad: 'var(--pick)' };
  const SHORT = { 'Colwick Country Park (West Lake)': 'Colwick', 'Cotswold Country Park and Beach': 'Cotswold',
    'Hampstead Heath': 'Hampstead Heath (3)', 'The Serpentine - Hyde Park': 'The Serpentine', 'Henleaze Lake': 'Henleaze',
    'Frensham Great Pond': 'Frensham' };
  const short = k => SHORT[k] || k;

  function front(D) {
    const o = D.order, ow = D.own_level, a = D.average_seen;
    LAB.answer($('front-answer'),
      `It put the days in order, but a typical lake's level was wrong. At seven lakes it had no level for, the model ordered each lake's samples at ${n3(o.rho.value)}, against ${n3(o.rho_production.value)} for the site's earlier lake figure. `
      + `Treated as unknown, sampled lakes had only ${pct(a.A.overall)} of their samples inside a typical lake's 8-in-10 range. Given each lake's own level from its past samples, ${pct1(ow.inside.value)} fell inside on years it never saw.`,
      `Order: ${int(o.rows)} samples at ${o.lakes} lake bathing waters on ${o.water_bodies} water bodies, May to September 2012 to 2022, read ${LAB.day(o.read_at)}; difference ${n3(o.difference.value)} (${ci(o.difference.ci95)}). `
      + `Own levels: the same ${int(ow.rows)} samples, read ${LAB.day(ow.read_at)}: ${pct1(ow.inside.value)} inside (${ci(ow.inside.ci95, pct1)}), ${pct1(ow.below)} below, ${pct1(ow.above)} above. `
      + `The bar, set before the tests: ${pct(D.bar.inside[0])} to ${pct(D.bar.inside[1])} inside, every water body at least ${pct(D.bar.each_water_body)}.`);
    $('attrib').textContent = D.credit;
  }

  function order(D) {
    const o = D.order, k = D.known, sites = Object.keys(k.rho_by_site);
    $('order').innerHTML = '<div class="fnote"></div>';   // LAB.dots sizes its charts from a note's width
    const mean = l => l.reduce((s, v) => s + v, 0) / l.length;
    $('order').innerHTML = `
      <div class="fnote"><span class="tag">Note 1 · seven lakes it had no level for, 2012 to 2022</span>
        <p class="fig">${n3(o.rho.value)} <small>the lake model; the earlier lake figure ${n3(o.rho_production.value)}</small></p>
        ${LAB.dots([
          { label: 'The lake model', v: o.rho.value, ci: o.rho.ci95, c: COL.model, strong: true },
          { label: 'The earlier lake figure', v: o.rho_production.value, ci: o.rho_production.ci95, c: COL.prod },
        ], { min: -0.2, max: 0.6, fmt: n3, ref: { v: 0, label: 'chance' } })}
        <p>The Serpentine, Hampstead Heath's three ponds, Henleaze, Cotswold and Colwick: lakes with no monitored overflow upstream, so the model works from rain and the time of year alone.
          Intervals from resampling water-body seasons. Read once, from a statement pushed first (bench read 1).</p></div>
      <div class="fnote"><span class="tag">Note 2 · Windermere and Frensham, 2012 to 2022</span>
        <p class="fig">${n3(mean(sites.map(s => k.rho_by_site[s])))} <small>the lake model, mean over ${sites.length} sites</small></p>
        ${LAB.dots(sites.map(s => ({ label: s.replace('Windermere, ', 'Windermere: '), v: k.rho_by_site[s], c: COL.model })), { min: -0.2, max: 0.6, fmt: n3, ref: { v: 0, label: 'chance' } })}
        <p>Lakes with overflows upstream, where spills move the figure too. ${int(k.rows)} samples (#584's test). Order does not depend on level, which is why it can be carried to a lake with no samples.</p></div>`;
  }

  function level(D) {
    const a = D.average_seen, u = D.known_as_unknown, ref = { v: D.bar.claims, label: 'claims 80%' };
    const rowsA = Object.entries(a.A.by_water).map(([w, v]) => ({ label: short(w), v: v.inside, c: v.inside < D.bar.each_water_body ? COL.bad : COL.dev }));
    $('level').innerHTML = `
      <div class="fnote"><span class="tag">Note 3 · each lake treated as unknown, 2023 to 2026 (development)</span>
        <p class="fig">${pct1(a.A.overall)} <small>inside a typical lake's range, where about 80% is right</small></p>
        ${LAB.dots(rowsA, { min: 0.3, max: 1, fmt: pct, ref })}
        <p>Too low at the London ponds, Henleaze, Cotswold and Colwick, where more samples fell above it; too high at Windermere, where more fell below.
          A mix of the known lakes' levels in place of the typical lake did better overall (${pct1(a.B.overall)}) and still failed at Derwent Water.
          These are years the model saw, each lake left out of the fit in turn: development evidence, with the rule fixed before it was run.</p></div>
      <div class="fnote"><span class="tag">Note 4 · Windermere and Frensham treated as unknown, 2012 to 2022</span>
        <p class="fig">${pct1(u.inside)} <small>inside; ${pct1(u.below)} below, ${pct1(u.above)} above</small></p>
        ${LAB.dots(Object.entries(u.by_water).map(([w, v]) => ({ label: w, v, c: COL.dev })), { min: 0.3, max: 1, fmt: pct, ref })}
        <p>A refit without those two lakes, reported beside #584's test: here the typical lake sat a little high. Low at some lakes, high at others: the model cannot place a lake it has not sampled.</p></div>`;
  }

  function own(D) {
    const ow = D.own_level, k = D.known, ref = { v: D.bar.claims, label: 'claims 80%' };
    $('own').innerHTML = `
      <div class="fnote"><span class="tag">Note 5 · the seven lakes on their own levels, 2012 to 2022</span>
        <p class="fig">${pct1(ow.inside.value)} <small>inside, ${ci(ow.inside.ci95, pct1)}</small></p>
        ${LAB.dots(Object.entries(ow.by_water).map(([w, v]) => ({ label: short(w), v: v.cover80, c: COL.model })), { min: 0.3, max: 1, fmt: pct, ref })}
        <p>Each lake's level learned from its 2023 to 2026 samples, the rest of the model unchanged, then read once on 2012 to 2022 (bench read 2). A little wide: ${pct1(ow.above)} above where about 10% is right. It errs towards including high readings.</p></div>
      <div class="fnote"><span class="tag">Note 6 · Windermere and Frensham on their own levels, 2012 to 2022</span>
        <p class="fig">${pct1(k.inside)} <small>inside; ${pct1(k.below)} below, ${pct1(k.above)} above</small></p>
        ${LAB.dots(Object.entries(k.by_water).map(([w, v]) => ({ label: w, v: v.inside, c: COL.model })), { min: 0.3, max: 1, fmt: pct, ref })}
        <p>#584's test, which put the range on the site at lakes with their own samples.</p></div>`;
  }

  fetch('reads.json').then(r => { if (!r.ok) throw new Error(`reads.json ${r.status}`); return r.json(); }).then(D => {
    front(D); order(D); level(D); own(D);
  }).catch(e => LAB.failed($('front-answer'), e));
})();
