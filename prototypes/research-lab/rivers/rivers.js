// Research Lab exhibit 7, a river's bad days. Every figure is read from reads.json (scripts/lab_river_reads.py, made from
// docs/river-unseen/result.json and docs/river-winter/result.json); nothing is typed here. Figures the winter result
// reports on summer rows already read are labelled development, as the result labels them.
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = LAB.esc;
  const n2 = v => Number(v).toFixed(2), n3 = v => Number(v).toFixed(3);
  const pct = v => Math.round(100 * v) + '%';
  const pct1 = v => (100 * v).toFixed(1) + '%';
  const int = v => Number(v).toLocaleString('en-GB');
  const ci = c => `${n3(c[0])} to ${n3(c[1])}`;
  const signed = v => (v >= 0 ? '+' : '−') + n3(Math.abs(v));
  const span = a => `${a[0]} to ${a[a.length - 1]}`;
  const COL = { est: 'var(--brand)', rain: 'var(--pick)', ov: 'var(--ink)', dev: 'var(--faint)' };

  function front(D) {
    const s = D.summer, w = D.winter, wm = w.order.month_removed;
    LAB.answer($('front-answer'),
      `It put them in order, in summer and in winter, and rain alone did nearly as well. In summer the estimate ordered a point's days at ${n2(s.order.production_deployed)} and rain in the 48 hours before at ${n2(s.order.rain_48h)}; `
      + `in winter at ${n2(wm.production.value)} and ${n2(wm.rain.value)}. Neither test shows it better than the rain. Its chance of a result over 900 was too low: `
      + `${pct(w.level.mean_production_chance)} on average in winter, where ${pct(w.level.share_over_900)} were over.`,
      `Summer: ${int(s.rows)} results at ${s.points} points in ${s.systems} river systems, May to September ${span(s.seasons)} (no kept results in 2020), ${int(s.over_900)} over 900; read ${LAB.day(s.read_at)}. `
      + `Winter: ${int(w.rows)} results at ${w.points} of the same points (${w.points_15_or_more} with 15 or more), October to April of the winters starting ${w.winters.join(', ')}, ${int(w.over_900)} over 900; read ${LAB.day(w.read_at)}. `
      + `Both passed the bar for order, ${D.bars.order}, set before the read. The summer range failed: ${pct1(s.range.inside)} of results inside an 8-in-10 range, where ${pct(D.bars.summer_range[0])} to ${pct(D.bars.summer_range[1])} was needed.`);
    $('attrib').textContent = D.credit;
  }

  function overview(D) {
    const el = $('overview'), by = {};
    for (const p of D.points) by[p.region] = (by[p.region] || 0) + 1;
    LAB.loadOutline('../').then(() => {
      LAB.drawMap(el, D.points.map(p => ({ id: p.id, lat: p.lat, lon: p.lon, name: `${p.name}, ${p.water}`, mark: '<circle r="3.4" class="rv-pt"/>' })), { inert: true });
      $('overview-cap').textContent = `The ${D.points.length} river monitoring points of the summer test: ${Object.entries(by).sort((a, b) => b[1] - a[1]).map(([r, k]) => `${k} ${r}`).join(', ')}. `
        + `The winter test used ${D.winter.points} of them. Map: ${LAB.credit()}.`;
    }).catch(() => { el.hidden = true; });
  }

  function order(D) {
    const s = D.summer, w = D.winter, wm = w.order.month_removed, ref = { v: D.bars.order, label: `bar ${D.bars.order}` };
    const max = 0.6;
    $('order').innerHTML = '<div class="fnote"></div>';   // LAB.dots sizes its charts from a note's width: one must exist first
    $('order').innerHTML = `
      <div class="fnote"><span class="tag">Note 1 · summer, May to September ${span(s.seasons)}</span>
        <p class="fig">${n3(s.order.production_deployed)} <small>the estimate; rain alone ${n3(s.order.rain_48h)}</small></p>
        ${LAB.dots([
          { label: 'The estimate', v: s.order.production_deployed, c: COL.est, strong: true },
          { label: 'Range candidate (the test)', v: s.order.candidate.value, ci: s.order.candidate.ci95, c: COL.est },
          { label: 'Rain, 48 hours, alone', v: s.order.rain_48h, c: COL.rain },
          { label: 'Overflow figure alone*', v: s.development.exposure_alone, c: COL.dev },
        ], { max, fmt: n3, ref })}
        <p>The test's own figure was a candidate model's likely reading, frozen before the read (${n3(s.order.candidate.value)}, ${ci(s.order.candidate.ci95)} over resamples of river systems): a pass for order.
          The estimate as the site used it gave ${n3(s.order.production_deployed)} and rain alone ${n3(s.order.rain_48h)}, reported beside the test with no interval.
          * Measured afterwards on these rows, already read: development.</p></div>
      <div class="fnote"><span class="tag">Note 2 · winter, October to April, ${w.winters.length} winters</span>
        <p class="fig">${n3(wm.production.value)} <small>the estimate; rain alone ${n3(wm.rain.value)}</small></p>
        ${LAB.dots([
          { label: 'The estimate', v: wm.production.value, ci: wm.production.ci95, c: COL.est, strong: true },
          { label: 'Rain, 48 hours, alone', v: wm.rain.value, ci: wm.rain.ci95, c: COL.rain },
          { label: 'Overflow figure alone', v: wm.exposure.value, ci: wm.exposure.ci95, c: COL.ov },
        ], { max, fmt: n3, ref })}
        <p>With each point's month means removed, so the season's calendar cannot do the work. Before removing them the estimate gave ${n3(w.order.production.value)} (${ci(w.order.production.ci95)}): both conditions passed.
          The estimate less rain: ${signed(wm.production_minus_rain.value)} (${signed(wm.production_minus_rain.ci95[0])} to ${signed(wm.production_minus_rain.ci95[1])}). The interval includes zero, so the estimate is not shown better than rain.</p></div>`;
  }

  function level(D) {
    const s = D.summer, w = D.winter, dl = s.development.level, b = s.brier_over_900;
    const pair = (a, o) => LAB.dots([{ label: "The estimate's average chance", v: a, c: COL.est, strong: true }, { label: 'Results over 900', v: o, c: COL.ov }], { max: 0.6, fmt: pct });
    $('level').innerHTML = `
      <div class="fnote"><span class="tag">Note 3 · winter</span>
        <p class="fig">${pct1(w.level.mean_production_chance)} <small>average chance of a result over 900; ${pct1(w.level.share_over_900)} were over</small></p>
        ${pair(w.level.mean_production_chance, w.level.share_over_900)}
        <p>The middle result was ${int(w.level.median_count)} per 100 ml. So the order is useful and the percentage is not: a river reads higher than the bathing waters the model was fitted on.</p></div>
      <div class="fnote"><span class="tag">Note 4 · summer</span>
        <p class="fig">${pct1(s.range.inside)} <small>of results inside the test's 8-in-10 range; ${pct(D.bars.summer_range[0])} to ${pct(D.bars.summer_range[1])} was needed</small></p>
        ${pair(dl.mean_production_chance, dl.share_over_900)}
        <p>The range sat too low: it was fitted on bathing waters. On the same rows, measured afterwards (development), the estimate's average chance was ${pct1(dl.mean_production_chance)} where ${pct1(dl.share_over_900)} were over 900.
          For a result over 900, a rule that only asks "more than 10 mm of rain in 48 hours?" scored ${n3(b.rain_rule)} (Brier, lower is better) against the estimate's ${n3(b.production_deployed)}.</p></div>`;
  }

  function none(D) {
    const o = D.winter.no_overflow;
    $('none').innerHTML = `
      <div class="fnote"><span class="tag">Note 5 · no monitored overflow upstream, winter</span>
        <p class="fig">${pct1(o.level.mean_production_chance)} <small>the estimate's average chance; ${pct1(o.level.share_over_900)} of results were over 900</small></p>
        <p>${int(o.rows)} results at points with no monitored overflow upstream (${o.points_15_or_more} with 15 or more). The middle result was ${int(o.level.median_count)} per 100 ml.
          With nothing upstream the estimate leans on its overflow figure, which is zero, so its chance was far too low.</p></div>
      <div class="fnote"><span class="tag">Note 6 · the order there</span>
        <p class="fig">${n3(o.rain_month_removed.value)} <small>rain alone; the estimate ${n3(o.production_month_removed.value)}</small></p>
        ${LAB.dots([{ label: 'The estimate', v: o.production_month_removed.value, ci: o.production_month_removed.ci95, c: COL.est, strong: true },
          { label: 'Rain, 48 hours, alone', v: o.rain_month_removed.value, ci: o.rain_month_removed.ci95, c: COL.rain }], { max: 0.6, fmt: n3, ref: { v: D.bars.order, label: `bar ${D.bars.order}` } })}
        <p>Month means removed. Rain ordered winter days about as well here as anywhere. For a swimmer: at a river with no overflow upstream, a low figure does not mean clean water. Field runoff, septic tanks and animals are not in the model.</p></div>`;
  }

  function where(D) {
    const s = D.summer, w = D.winter;
    const BAND = { large: 'Large stream (100 km of channel or more upstream)', medium: 'Medium (10 to 100 km)', small: 'Small (under 10 km)' };
    const PURPOSE = { MU: 'Monitoring for government policy', PI: 'Planned investigation, local', PN: 'Planned investigation, national', MS: 'Statutory monitoring' };
    const MONTHS = { oct_nov: 'October and November', dec_feb: 'December to February', mar_apr: 'March and April' };
    const row = (label, x, rho) => `<tr><td>${esc(label)}</td><td class="n">${int(x.rows)}</td><td class="n">${x.points ?? x.points_15_or_more}</td><td class="n">${n3(rho)}</td></tr>`;
    $('where').innerHTML = `
      <div class="tw"><table class="rv-t"><caption>Summer, the range candidate's order, by stream size and by why the point was sampled.</caption>
        <thead><tr><th>Group</th><th class="n">Results</th><th class="n">Points</th><th class="n">Order</th></tr></thead><tbody>
        ${Object.entries(BAND).map(([k, l]) => row(l, s.bands[k], s.bands[k].rho)).join('')}
        ${Object.entries(PURPOSE).filter(([k]) => s.purposes[k]).map(([k, l]) => row(l, s.purposes[k], s.purposes[k].rho)).join('')}
        </tbody></table></div>
      <div class="tw"><table class="rv-t"><caption>Winter, the estimate's order with month means removed, by part of the winter (points with 15 or more results).</caption>
        <thead><tr><th>Months</th><th class="n">Results</th><th class="n">Points</th><th class="n">Order</th><th class="n">Rain alone</th><th class="n">Over 900</th></tr></thead><tbody>
        ${Object.entries(MONTHS).map(([k, l]) => { const x = w.seasons_of_winter[k]; return `<tr><td>${l}</td><td class="n">${int(x.rows)}</td><td class="n">${x.points_15_or_more}</td><td class="n">${n3(x.z_prod.month_removed)}</td><td class="n">${n3(x.rain.month_removed)}</td><td class="n">${pct(x.share_over_900)}</td></tr>`; }).join('')}
        </tbody></table></div>
      <p class="note">Small streams were ordered least well in summer, and points in local investigations sat furthest above the range. These splits were reported beside each test or measured after it, and decide nothing; several rest on few points.</p>`;
  }

  fetch('reads.json').then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then(D => {
    if (D.schema !== 'swimsignal.lab-river-reads' || String(D.version).split('.')[0] !== '1') throw new Error('an unknown file version');
    front(D); overview(D); order(D); level(D); none(D); where(D);
  }).catch(err => LAB.failed($('front-answer'), err));
})();
