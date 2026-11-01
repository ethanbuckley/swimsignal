// How good are the forecasts? Research Lab exhibit 3. Reads the committed files as they are:
//   data/research/ecoli_evidence.v1.json   EA samples beside hindsight estimates (docs/ECOLI-EVIDENCE-CONTRACT-v1.md)
//   exploration.json                       scripts/forecast_record_explore.py (outcomes to 30 Sep 2026 only)
// A hindsight estimate is never called the forecast the site issued. Misses and false alarms are shown as plainly as
// hits. Nothing after the exploration's cutoff is read, so no active evaluation window is scored here.

const DATA = '../../../data/research/';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const fmt = iso => new Date(iso.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const num = (v, dp = 2) => (v == null || Number.isNaN(v) ? '–' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(dp));
const pct = v => `${Math.round(v * 100)}%`;
const plural = (n, one, many = one + 's') => `${Number(n).toLocaleString('en-GB')} ${n === 1 ? one : many}`;
const dayMs = iso => Date.parse(iso.slice(0, 10) + 'T12:00:00Z');

let EV, EX, SITES = {}, REFS = {}, WARN;
const S = { bw: null, year: null, t: null };

// ------------------------------------------------------------------ outcome of one sample at the warning line
function outcome(x) {
  if (x.hindsight == null) return 'none';
  const w = x.hindsight >= WARN;
  return x.over ? (w ? 'hit' : 'miss') : (w ? 'fa' : 'quiet');
}
// 'would have flagged': these estimates were rebuilt afterwards, so nothing here was a warning issued before a sample
const WORD = { hit: 'Would have flagged, and over 900', miss: 'Would have missed: over 900, not flagged', fa: 'False alarm: would have flagged, under 900', quiet: 'Not flagged, and under 900', none: 'No estimate' };
const COL = { hit: 'var(--hit)', miss: 'var(--card)', fa: 'var(--fa)', quiet: 'var(--quiet)', none: 'var(--card)' };
const samplesOf = bw => SITES[bw].samples.filter(x => x.t.slice(0, 10) <= EX.cutoff);

// ------------------------------------------------------------------ frontispiece
function renderFront() {
  const r = EX.ecoli.river, l = EX.ecoli.lake, sp = EX.spill_2025.leads;
  const lead0 = sp.find(x => x.source === 'forecast lead 0'), lead4 = sp.find(x => x.source === 'forecast lead 4');
  const m = r.at_line.model;
  LAB.answer($('#front-answer'),
    `At rivers, better than the simple alternatives, with real misses. At lakes, no better than quoting the usual rate.`,
    `<b>Rebuilt afterwards</b>, not issued at the time: of ${r.over_900} river samples over 900, the estimate would have flagged ${m.hits} and missed ${m.misses}, ` +
    `with ${m.false_alarms} false alarms. At lakes it would have flagged none of ${l.over_900}. ` +
    `Spill forecasts beat the usual rate by ${pct(lead0.brier_skill_vs_clim)} on the day, falling to ${pct(lead4.brier_skill_vs_clim)} four days ahead.`);
  $('#front-status').innerHTML = `<b>Exploratory, on outcomes already read.</b> E. coli: ${plural(EX.ecoli.all.samples, 'sample')} at ${EX.ecoli.all.sites} bathing waters, 2024–2026, against estimates rebuilt in hindsight. Spills: one held-out year. Nothing after ${fmt(EX.cutoff)}.`;
  // One dot per sample, in date order within each block, so "play" can fill them as the summers went.
  const kindOf = r => SITES[r.bw_id].kind, warned = r => r.model >= WARN;
  const blocks = [
    ['over', r => kindOf(r) === 'river' && r.y, `<b>${r.over_900}</b>river samples over 900`],
    ['fa', r => kindOf(r) === 'river' && !r.y && warned(r), `<b>${m.false_alarms}</b>false alarms at rivers`],
    ['lake', r => kindOf(r) === 'lake' && r.y, `<b>${l.over_900}</b>lake samples over 900`],
  ];
  const rows = [...EX.ecoli.samples].sort((a, b) => a.t.localeCompare(b.t));
  $('#ledger').innerHTML = blocks.map(([k, f, lbl]) => `<div class="blk"><div class="lbl">${lbl}</div><div class="dots">${rows.filter(f).map(r =>
      `<i class="${r.y ? (warned(r) ? 'hit' : 'miss') : 'fa'}" data-t="${r.t}"></i>`).join('')}</div></div>`).join('') +
    `<div class="play"><button type="button" id="ledger-play">Play 2024 to 2026</button><span id="ledger-read" aria-live="polite"></span></div>
    <figcaption>One dot per lab sample, in date order. Estimates rebuilt in hindsight, not issued at the time. Filled: the estimate was over the ${pct(WARN)} line, so it would have flagged the sample. Hollow: it was not. Amber: it would have flagged a sample under 900.</figcaption>`;
  $('#ledger-play').onclick = playLedger;
}
let ledgerTimer = null;
function playLedger() {
  const dots = [...document.querySelectorAll('#ledger i[data-t]')].sort((a, b) => a.dataset.t.localeCompare(b.dataset.t));
  const read = $('#ledger-read'), btn = $('#ledger-play');
  if (ledgerTimer) { clearInterval(ledgerTimer); ledgerTimer = null; dots.forEach(d => d.classList.remove('off')); btn.textContent = 'Play 2024 to 2026'; read.textContent = ''; return; }
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  dots.forEach(d => d.classList.add('off'));
  const n = { hit: 0, miss: 0, fa: 0 }; let i = 0;
  btn.textContent = 'Stop';
  const step = () => {
    const end = Math.min(dots.length, i + (reduce ? dots.length : 4));
    for (; i < end; i++) { dots[i].classList.remove('off'); n[dots[i].className] = (n[dots[i].className] || 0) + 1; }
    const t = dots[Math.max(0, i - 1)].dataset.t;
    read.textContent = `${new Date(t.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })} · in hindsight: would have flagged ${n.hit} · missed ${n.miss} · false alarms ${n.fa}`;
    if (i >= dots.length) { clearInterval(ledgerTimer); ledgerTimer = null; btn.textContent = 'Play 2024 to 2026'; }
  };
  step(); ledgerTimer = setInterval(step, 70);
}

// ------------------------------------------------------------------ choosing a bathing water
function siteTag(id) {
  const s = EX.ecoli.sites[id];
  return s ? `${s.over_900} over · ${s.misses} missed · ${s.false_alarms} false` : 'no estimate';
}
function renderPicker() {
  const ids = Object.keys(SITES).sort((a, b) => SITES[a].name.localeCompare(SITES[b].name));
  const groups = [['river', 'Rivers'], ['lake', 'Lakes']];
  $('#pick-aside').textContent = `${ids.length} bathing waters, ${Object.keys(EX.ecoli.sites).length} with estimates`;
  $('#bw-select').innerHTML = groups.map(([k, t]) => `<optgroup label="${t}">${ids.filter(i => SITES[i].kind === k).map(i => `<option value="${i}">${esc(SITES[i].name)}</option>`).join('')}</optgroup>`).join('');
  $('#bw-select').onchange = e => selectSite(e.target.value);
  $('#bw-list').innerHTML = groups.map(([k, t]) => `<h4>${t}</h4>` + ids.filter(i => SITES[i].kind === k).map(i =>
    `<button type="button" data-bw="${i}"><span class="nm">${esc(SITES[i].name)}</span><span class="tg">${siteTag(i)}</span></button>`).join('')).join('');
  $('#bw-list').onclick = e => { const b = e.target.closest('[data-bw]'); if (b) selectSite(b.dataset.bw); };
}

function selectSite(id, t) {
  if (!SITES[id]) return;
  S.bw = id;
  const sm = samplesOf(id), withEst = sm.filter(x => x.hindsight != null);
  const pick = t && sm.find(x => x.t === t) || withEst.find(x => x.over && x.hindsight < WARN) || withEst[withEst.length - 1] || sm[sm.length - 1];
  S.t = pick ? pick.t : null;
  S.year = pick ? +pick.t.slice(0, 4) : null;
  document.querySelectorAll('[data-bw]').forEach(b => b.setAttribute('aria-current', b.dataset.bw === id));
  $('#bw-select').value = id;
  renderSiteHead(); renderSeasons(); renderChart(); renderSample(); writeHash();
}
function selectSample(t) { S.t = t; S.year = +t.slice(0, 4); renderSeasons(); renderChart(); renderSample(); writeHash(); }
function writeHash() { const h = new URLSearchParams(); h.set('bw', S.bw); if (S.t) h.set('t', S.t); history.replaceState(null, '', '#' + h.toString()); }

// ------------------------------------------------------------------ one bathing water
function siteBrier(id) {
  const rows = EX.ecoli.samples.filter(r => r.bw_id === id);
  if (!rows.length) return null;
  const b = k => rows.reduce((a, r) => a + (r[k] - r.y) ** 2, 0) / rows.length;
  return { n: rows.length, model: b('model'), usual: b('usual'), site_usual: b('site_usual'), last: b('last') };
}
function renderSiteHead() {
  const s = SITES[S.bw], sm = samplesOf(S.bw), x = EX.ecoli.sites[S.bw], b = siteBrier(S.bw);
  $('#bw-name').textContent = s.name;
  $('#bw-link').innerHTML = `<a href="${LAB.spotURL('bw-' + S.bw)}">Today's forecast for ${esc(s.name)}</a>`;   // back to the live forecast
  $('#bw-meta').innerHTML = `${s.kind === 'lake' ? 'Lake bathing water. The site gives no E. coli warning at lakes; the line is drawn for comparison only.' : 'River bathing water'} · ${plural(sm.length, 'EA sample')} ${fmt(sm[0].t)} to ${fmt(sm[sm.length - 1].t)}`;
  const refBest = b ? Math.min(b.usual, b.site_usual, b.last) : null;
  $('#bw-facts').innerHTML = [
    ['Samples over 900', `${sm.filter(v => v.over).length} of ${sm.length}`, 'E. coli per 100 ml'],
    ['Would have flagged', x ? `${x.hits} of ${x.over_900}` : '–', x ? `${x.misses} missed` : 'no estimate here'],
    ['False alarms', x ? String(x.false_alarms) : '–', x ? `of ${x.samples - x.over_900} samples under 900` : ''],
    ['Brier, estimate', b ? num(b.model, 3) : '–', b ? `best simple alternative ${num(refBest, 3)}; lower is better` : ''],
  ].map(([t, v, n]) => `<div><dt>${t}</dt><dd>${v}<small>${n || '&nbsp;'}</small></dd></div>`).join('');
}

function yearSpan(y) { return [Date.UTC(y, 4, 1, 12), Date.UTC(y, 8, 30, 12)]; }
function renderSeasons() {
  const sm = samplesOf(S.bw), years = [...new Set(sm.map(x => +x.t.slice(0, 4)))].sort(), W = 600, H = 22;
  $('#seasons').innerHTML = years.map(y => {
    const [a, b] = yearSpan(y), xs = sm.filter(v => v.t.startsWith(y));
    const ticks = xs.map(v => { const o = outcome(v), xx = (dayMs(v.t) - a) / (b - a) * W;
      return o === 'miss' ? `<rect x="${xx - 2}" y="3" width="4" height="15" fill="none" stroke="var(--miss)" stroke-width="1.5"/>`
        : `<rect x="${xx - 1}" y="${o === 'quiet' || o === 'none' ? 8 : 3}" width="${o === 'quiet' || o === 'none' ? 2 : 3}" height="${o === 'quiet' || o === 'none' ? 6 : 15}" fill="${o === 'none' ? 'var(--faint)' : COL[o]}"/>`; }).join('');
    const est = xs.some(v => v.hindsight != null);
    return `<button type="button" class="yr" data-year="${y}" aria-pressed="${S.year === y}"><span class="yl">${y}</span><span class="ys"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><rect class="bg" x="0" y="0.5" width="${W}" height="${H - 1}" fill="none" stroke="var(--line)"/>${ticks}</svg>${est ? '' : '<span class="yr-why">samples only: no archived forecast rain for this year</span>'}</span><span class="yc">${plural(xs.length, 'sample')}</span></button>`;
  }).join('');
  $('#seasons').querySelectorAll('.yr').forEach(b => b.onclick = () => {
    const xs = samplesOf(S.bw).filter(v => v.t.startsWith(b.dataset.year));
    if (xs.length) selectSample((xs.find(v => outcome(v) === 'miss') || xs.find(v => v.hindsight != null) || xs[0]).t);
  });
}

function renderChart() {
  const y = S.year, sm = samplesOf(S.bw).filter(v => v.t.startsWith(y));
  const W = Math.max(300, Math.round($('#chart').clientWidth || 1000)), narrow = W < 600;
  const padL = narrow ? 44 : 64, padR = narrow ? 8 : 16, A = [30, 170], B = [214, 330], H = 360;
  const [a, b] = yearSpan(y), x = iso => padL + (dayMs(iso) - a) / (b - a) * (W - padL - padR);
  const yA = p => A[1] - p * (A[1] - A[0]);
  const lo = 1, hi = 5, yB = v => B[1] - (Math.log10(Math.max(10, v)) - lo) / (hi - lo) * (B[1] - B[0]);
  let g = '';
  ['May', 'Jun', 'Jul', 'Aug', 'Sep'].forEach((m, i) => { const xm = x(`${y}-${String(i + 5).padStart(2, '0')}-01`); g += `<line x1="${xm}" x2="${xm}" y1="${A[0] - 12}" y2="${B[1]}" stroke="var(--hair)"/><text x="${xm + 4}" y="${H - 6}">${m}</text>`; });
  for (const p of [0, 0.5, 1]) g += `<line x1="${padL}" x2="${W - padR}" y1="${yA(p)}" y2="${yA(p)}" stroke="var(--hair)"/><text x="${padL - 8}" y="${yA(p) + 4}" text-anchor="end">${pct(p)}</text>`;
  g += `<line x1="${padL}" x2="${W - padR}" y1="${yA(WARN)}" y2="${yA(WARN)}" stroke="var(--pick)" stroke-dasharray="4 3"/><text x="${W - padR}" y="${yA(WARN) - 4}" text-anchor="end" style="fill:var(--pick)">warning line ${pct(WARN)}</text>`;
  for (const v of [10, 100, 1000, 10000, 100000]) g += `<line x1="${padL}" x2="${W - padR}" y1="${yB(v)}" y2="${yB(v)}" stroke="var(--hair)"/><text x="${padL - 8}" y="${yB(v) + 4}" text-anchor="end">${v >= 1000 ? v / 1000 + 'k' : v}</text>`;
  g += `<line x1="${padL}" x2="${W - padR}" y1="${yB(900)}" y2="${yB(900)}" stroke="var(--hit)" stroke-dasharray="4 3"/><text x="${W - padR}" y="${yB(900) - 4}" text-anchor="end" style="fill:var(--hit)">900</text>`;
  g += `<text class="lane-label" x="${padL}" y="${A[0] - 16}">Estimated chance of over 900 (hindsight)</text><text class="lane-label" x="${padL}" y="${B[0] - 14}">Lab E. coli per 100 ml (log scale)</text>`;
  if (!sm.some(v => v.hindsight != null)) g += `<text x="${padL + 12}" y="${(A[0] + A[1]) / 2}" style="font:12px var(--font-text);fill:var(--faint)">No estimate for ${y}: no archived forecast rain that year</text>`;
  for (const v of sm) {
    const xx = x(v.t), o = outcome(v), on = v.t === S.t, by = yB(v.ecoli);
    const est = v.hindsight != null ? `<circle cx="${xx}" cy="${yA(v.hindsight)}" r="${on ? 6.5 : 4.5}" fill="${o === 'miss' ? 'var(--card)' : COL[o]}" stroke="${o === 'miss' ? 'var(--miss)' : o === 'quiet' ? 'var(--ink)' : COL[o]}" stroke-width="${o === 'miss' ? 2 : 1}"/>` : '';
    g += `<g class="dot" tabindex="0" role="button" data-t="${v.t}" aria-label="${fmt(v.t)}: ${v.ecoli} E. coli${v.hindsight != null ? `, estimate ${pct(v.hindsight)}` : ''}. ${WORD[o]}">
      ${on ? `<line x1="${xx}" x2="${xx}" y1="${A[0] - 6}" y2="${B[1]}" stroke="var(--pick)" stroke-dasharray="3 3"/>` : `<line x1="${xx}" x2="${xx}" y1="${v.hindsight != null ? yA(v.hindsight) : A[1]}" y2="${by}" stroke="var(--hair)"/>`}
      ${est}<path d="M${xx} ${by - 5}l5 5-5 5-5-5z" fill="${v.over ? 'var(--hit)' : v.q === '<' ? 'var(--card)' : 'var(--ink)'}" stroke="${v.over ? 'var(--hit)' : 'var(--ink)'}" stroke-width="1"/>
      <rect x="${xx - 8}" y="${A[0]}" width="16" height="${B[1] - A[0]}" fill="transparent"/></g>`;
  }
  $('#chart').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Estimates and samples, ${y}">${g}</svg>`;
  $('#chart').querySelectorAll('.dot').forEach(d => {
    d.onclick = () => selectSample(d.dataset.t);
    d.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectSample(d.dataset.t); requestAnimationFrame(() => document.querySelector(`.dot[data-t="${d.dataset.t}"]`)?.focus()); } };
  });
  $('#chart-note').innerHTML = `<span><span class="sw" style="background:var(--hit)"></span>would have flagged, over 900</span><span><span class="sw" style="background:var(--card);border:2px solid var(--miss)"></span>would have missed, over 900</span><span><span class="sw" style="background:var(--fa)"></span>false alarm</span><span><span class="sw" style="background:var(--quiet)"></span>quiet, under 900</span><span>Estimates and samples are not joined: each is one dated sample.</span>`;
}

function renderSample() {
  const v = samplesOf(S.bw).find(x => x.t === S.t);
  if (!v) { $('#sample').innerHTML = ''; return; }
  const o = outcome(v), r = REFS[S.bw + '|' + v.t];
  const why = v.hindsight_reason ? EV.hindsight_reasons[v.hindsight_reason] : '';
  $('#sample').innerHTML = `<div>
      <div class="when">${fmt(v.t)}, ${v.t.slice(11, 16)}</div>
      <p class="verdict out-${o}">${WORD[o]}</p>
      <dl><dt>Lab E. coli</dt><dd>${v.q === '<' ? 'below ' : ''}${Number(v.ecoli).toLocaleString('en-GB')} per 100 ml${v.over ? ', over 900' : ''}</dd>
      <dt>Estimate</dt><dd>${v.hindsight != null ? `${pct(v.hindsight)} chance of over 900, rebuilt in hindsight` : esc(why || 'none')}</dd>
      <dt>Source</dt><dd>${v.src === 'wqa' ? 'EA Water Quality Archive' : 'EA bathing water quality service'}</dd></dl></div>
    <div>${r ? `<h3>The simple alternatives, for this sample</h3><dl>
      <dt>Usual rate</dt><dd>${pct(r.usual)} <span class="muted">(${SITES[S.bw].kind}s, other years)</span></dd>
      <dt>This water's rate</dt><dd>${pct(r.site_usual)} <span class="muted">(other years)</span></dd>
      <dt>Last sample</dt><dd>${pct(r.last)} <span class="muted">(after the previous result here)</span></dd></dl>
      <p class="note" style="margin-top:10px">${o === 'miss' && r.model < Math.max(r.usual, r.site_usual, r.last) ? 'Here a simple alternative gave a higher chance than the model did.' : o === 'miss' ? 'Every simple alternative was lower still.' : ''}</p>` : '<p class="note">No estimate, so no comparison for this sample.</p>'}</div>`;
}

// ------------------------------------------------------------------ section 3: against the simple alternatives
const noteW = LAB.noteW;
function bars(items, max, fmtv, ref) { return LAB.dots(items, { max, fmt: fmtv, ref }); }
const REFNAME = { model: 'SwimSignal estimate', usual: 'Usual rate', site_usual: "This water's own rate", last: 'Last sample' };
function brierNote(k, tag) {
  const s = EX.ecoli[k];
  const items = ['model', 'usual', 'site_usual', 'last'].map(r => ({ label: REFNAME[r], v: s.brier[r], c: r === 'model' ? 'var(--brand)' : 'var(--rule)' }));
  const d = s.model_minus;
  const better = Object.values(d).every(v => v.ci[1] < 0);
  return `<div class="fnote"><span class="tag">${tag}</span>
    <p class="fig">${num(s.brier.model, 3)} <small>Brier score, ${plural(s.samples, 'sample')} at ${s.sites} ${k === 'river' ? 'rivers' : 'lakes'}; lower is better</small></p>
    ${bars(items, Math.max(...items.map(i => i.v)) * 1.1, v => num(v, 3))}
    <p>${better ? `The estimate beat every simple alternative. Against the best of them (last sample) the difference is ${num(d.last.diff, 3)} (${num(d.last.ci[0], 3)} to ${num(d.last.ci[1], 3)}, resampling bathing waters).`
      : `The estimate did no better than the simple alternatives: against the usual rate the difference is ${num(d.usual.diff, 4)} (${num(d.usual.ci[0], 4)} to ${num(d.usual.ci[1], 4)}). Ranking samples by this water's own past rate (AUC ${num(s.auc.site_usual)}) did far better than ranking by the estimate (AUC ${num(s.auc.model)}, where 0.5 is chance).`}</p></div>`;
}
function renderRefs() {
  const r = EX.ecoli.river, m = r.at_line.model, l = r.at_line.last, me = EX.ecoli.miss_estimates;
  const misses = EX.ecoli.samples.filter(x => x.y && x.model < WARN && SITES[x.bw_id].kind === 'river').sort((a, b) => a.model - b.model).slice(0, 8);
  const yrs = Object.entries(EX.ecoli.by_year);
  $('#refs').innerHTML = brierNote('river', 'Note 1 · rivers') + brierNote('lake', 'Note 2 · lakes') + `
    <div class="fnote"><span class="tag">Note 3 · at the warning line, rivers</span>
      <p class="fig">${m.hits} of ${r.over_900} <small>samples over 900 it would have flagged; last-sample rule ${l.hits}</small></p>
      ${bars([{ label: 'Estimate: flagged, over', v: m.hits, c: 'var(--hit)' }, { label: 'Estimate: missed', v: m.misses, c: 'var(--rule)' }, { label: 'Estimate: false alarms', v: m.false_alarms, c: 'var(--fa)' },
        { label: 'Last sample: flagged, over', v: l.hits, c: 'var(--hit)' }, { label: 'Last sample: missed', v: l.misses, c: 'var(--rule)' }, { label: 'Last sample: false alarms', v: l.false_alarms, c: 'var(--fa)' }], Math.max(m.false_alarms, l.misses, l.false_alarms) * 1.1, v => String(v))}
      <p>At the ${pct(WARN)} line the rebuilt estimate would have caught ${m.hits - l.hits} more of the samples over 900 than a rule that warns after a bad sample, with ${m.false_alarms - l.false_alarms} more false alarms. Roughly one false alarm for every sample it would have caught.</p></div>
    <div class="fnote"><span class="tag">Note 4 · confident misses, rivers</span>
      <p class="fig">${me.under_0_1} of ${me.n} <small>river misses had an estimate under 10%</small></p>
      <p>Half the missed river samples had an estimate of ${pct(me.median)} or less. These are worth reading one by one; the lowest are below.</p>
      <table class="ea-table">${misses.map(x => `<tr><td><a href="#bw=${x.bw_id}&t=${encodeURIComponent(x.t)}" data-jump="${x.bw_id}|${x.t}">${esc(SITES[x.bw_id].name)}</a></td><td class="n">${fmt(x.t)}</td><td class="n">${Number(x.ecoli).toLocaleString('en-GB')}</td><td class="n">${pct(x.model)}</td></tr>`).join('')}</table></div>
    <div class="fnote wide"><span class="tag">Note 5 · by year, all bathing waters</span>
      ${bars(yrs.flatMap(([y, v]) => [{ label: `${y}: estimate`, v: v.brier.model, c: 'var(--brand)' }, { label: `${y}: usual rate`, v: v.brier.usual }]), 0.17, v => num(v, 3))}
      <p>Each year was scored by a model refitted without that year. The estimate was better than the usual rate in all three. Fewer samples went over 900 each year (${yrs.map(([y, v]) => `${v.over_900} in ${y}`).join(', ')}), so scores fall for every method; compare within a year, not across.</p></div>`;
  $('#refs').querySelectorAll('[data-jump]').forEach(a => a.onclick = e => { e.preventDefault(); const [id, t] = a.dataset.jump.split('|'); selectSite(id, t); $('#s-site').scrollIntoView({ behavior: 'smooth' }); });
}

// ------------------------------------------------------------------ section 4: spills, 2025 held out
function reliabilitySVG(rel) {
  const W = noteW(), H = Math.min(W, 320), p = 36, x = v => p + v * (W - p - 10), y = v => H - p + 6 - v * (H - p - 4);
  const maxN = Math.max(...rel.map(r => r.n));
  let g = `<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--rule)" stroke-dasharray="4 3"/><text x="${x(0.62)}" y="${y(0.7)}" style="fill:var(--faint)">perfect</text>`;
  for (const v of [0, 0.5, 1]) g += `<text x="${x(v)}" y="${H}" text-anchor="middle">${pct(v)}</text><text x="${p - 6}" y="${y(v) + 4}" text-anchor="end">${pct(v)}</text>`;
  g += rel.map(r => `<circle cx="${x(r.forecast)}" cy="${y(r.observed)}" r="${3 + 7 * Math.sqrt(r.n / maxN)}" fill="var(--brand)" fill-opacity=".75" stroke="#fff"><title>forecast ${pct(r.forecast)}, happened ${pct(r.observed)}, ${r.n.toLocaleString('en-GB')} overflow-days</title></circle>`).join('');
  g += `<text x="${W - 10}" y="${H - p - 2}" text-anchor="end">forecast chance →</text><text x="${p}" y="10">how often it spilled</text>`;
  return `<svg viewBox="0 0 ${W} ${H + 4}" style="max-width:${W}px" role="img" aria-label="Reliability of 2025 spill forecasts">${g}</svg>`;
}
function renderSpill() {
  const L = EX.spill_2025.leads, rel = EX.spill_2025.reliability, re = L.find(x => x.source.startsWith('reanalysis'));
  const leads = [0, 1, 2, 3, 4].map(k => L.find(x => x.source === `forecast lead ${k}`));
  const top = rel[rel.length - 1], n = leads[0].n;
  $('#spill').innerHTML = `
    <div class="fnote"><span class="tag">Note 6 · how far ahead</span>
      <p class="fig">${pct(leads[0].brier_skill_vs_clim)} → ${pct(leads[4].brier_skill_vs_clim)} <small>better than the usual rate, on the day and four days ahead</small></p>
      ${bars([{ label: 'Weather as it was', v: re.brier_skill_vs_clim }, ...leads.map((r, k) => ({ label: k ? `${k} day${k > 1 ? 's' : ''} ahead` : 'On the day', v: r.brier_skill_vs_clim, c: 'var(--brand)' }))], 0.45, pct)}
      <p>Skill against always forecasting the 2025 rate (${pct(leads[0].base_rate)} of ${n.toLocaleString('en-GB')} overflow-days spilled). It falls as rain forecasts get further ahead. The same-day forecast scored slightly better than the model fed with the weather as it actually was.</p></div>
    <div class="fnote"><span class="tag">Note 7 · does 70% mean 70%?</span>
      <p class="fig">${pct(top.forecast)} → ${pct(top.observed)} <small>at the top: forecast, then how often it spilled</small></p>
      ${reliabilitySVG(rel)}
      <p>Each circle is one band of forecasts, sized by how many overflow-days it holds. Above about 30% the forecasts ran high: the dots sit below the line. A winter recalibration test on this is already scheduled (fit from 10 December 2026, judged 14 December to 7 March 2027).</p></div>`;
}

// ------------------------------------------------------------------ section 5: beside the EA
function renderEA() {
  const e = EX.ea_comparison, b = e.both, s = e.season_samples.ea;
  $('#ea').innerHTML = `<p style="max-width:70ch">${esc(e.verdict)}</p>
    <table class="ea-table"><tr><th></th><th>Brier (lower is better)</th><th>Warned</th><th>Over 900 caught</th><th>False alarms</th></tr>
      <tr><td>Environment Agency daily prediction</td><td class="n">${num(b.ea.brier, 3)}</td><td class="n">${b.ea.n_increased}</td><td class="n">${b.ea.hits} of ${b.n_over_threshold}</td><td class="n">${b.ea.false_alarms}</td></tr>
      <tr><td>SwimSignal, as issued</td><td class="n">${num(b.swimsignal.brier, 3)}</td><td class="n">${b.swimsignal.n_warned}</td><td class="n">${b.swimsignal.hits} of ${b.n_over_threshold}</td><td class="n">${b.swimsignal.false_alarms}</td></tr>
      <tr><td>Always the usual rate</td><td class="n">${num(b.climatology_brier, 3)}</td><td class="n">–</td><td class="n">–</td><td class="n">–</td></tr></table>
    <p class="note" style="max-width:70ch">${b.n_samples} samples at ${b.n_sites} sites that both covered. These are SwimSignal's real issued estimates, logged from 15 September 2026. Over the whole season the EA raised its level before ${s.n_increased} of ${e.season_samples.n_with_ea_prediction} samples, caught ${s.hits} of the samples over 900 it covered and missed ${s.misses}; most of its raised levels were for reported pollution incidents. ${esc(e.credit)}</p>`;
}

function renderQuestions() {
  const qs = [
    ['How far apart are hindsight and the real issued record?', 'Everything in sections 2 and 3 is rebuilt afterwards. The issued estimates have been logged since 15 September 2026, but only 30 samples have been scored.', 'Score the logged issued estimates against 2027 samples as they arrive, beside the hindsight model on the same samples. This is part of the 2027 primary evaluation already registered; nothing new is needed but reporting it here.', 'Issued scores far worse than hindsight would mean the gap is forecast rain or feed failures, not the model.'],
    ['Why does a lake\'s own history beat the model?', 'At lakes the estimate ranked samples worse than chance (AUC 0.47), while each lake\'s past rate ranked them well (0.81).', 'A lake model that starts from the lake\'s own rate, judged on lake seasons it never read. The lake range work (PRs #584, #585) is the place for it.', 'A gain that comes only from the lakes with the most samples, or that disappears on unseen seasons.'],
    ['What do the confident misses have in common?', `${EX.ecoli.miss_estimates.under_0_1} river samples over 900 had an estimate under 10%.`, 'A fixed checklist, written before opening them: spill reported upstream that day, a monitor offline, rain far from the forecast, an unmonitored source, sample time against spill end.', 'Explanations chosen after looking at each case one by one, with no count of how often each cause also appears on correct days.'],
    ['Are false alarms the price of catching more?', `At rivers the estimate caught ${EX.ecoli.river.at_line.model.hits - EX.ecoli.river.at_line.last.hits} more samples over 900 than the last-sample rule, with ${EX.ecoli.river.at_line.model.false_alarms - EX.ecoli.river.at_line.last.false_alarms} more false alarms.`, 'Show the whole trade-off curve (catches against false alarms at every line), and ask swimmers which balance they would choose.', 'Moving the line on these same samples until a figure looks good: that would be choosing the answer.'],
  ];
  $('#qs').innerHTML = qs.map(([q, what, how, bad]) => `<li><div><h3>${q}</h3><p><span class="k">Where it stands.</span> ${what}</p><p><span class="k">What would settle it.</span> ${how}</p><p style="margin:0"><span class="k">Unconvincing if.</span> ${bad}</p></div></li>`).join('');
}

// ------------------------------------------------------------------ start
Promise.all([DATA + 'ecoli_evidence.v1.json', 'exploration.json'].map(u => fetch(u).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); })))
  .then(([ev, ex]) => {
    EV = ev; EX = ex; WARN = ex.warn_at;
    for (const s of EV.sites) SITES[s.bw_id] = s;
    for (const r of EX.ecoli.samples) REFS[r.bw_id + '|' + r.t] = r;
    $('#attrib').textContent = [...EV.attribution, EX.ea_comparison.credit].join(' ');
    renderFront(); renderPicker(); renderRefs(); renderSpill(); renderEA(); renderQuestions();
    const h = new URLSearchParams(location.hash.slice(1));
    const first = Object.keys(EX.ecoli.sites).sort((a, b) => EX.ecoli.sites[b].over_900 - EX.ecoli.sites[a].over_900)[0];
    // a bathing water this record lacks is said, not swapped for another quietly; a link opened in an open page does the same
    const open = (bw, t, fallback) => {
      $('#bw-note').textContent = bw && !SITES[bw] ? `That bathing water is not in this record, which holds the ${EV.sites.length} inland bathing waters the Environment Agency samples. Showing ${SITES[fallback].name} instead; choose another below.` : '';
      selectSite(SITES[bw] ? bw : fallback, t);
    };
    open(h.get('bw'), h.get('t'), first);
    window.addEventListener('hashchange', () => {
      const k = new URLSearchParams(location.hash.slice(1));
      if (k.get('bw') !== S.bw || (k.get('t') && k.get('t') !== S.t)) open(k.get('bw'), k.get('t'), S.bw);
    });
    let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { renderChart(); renderRefs(); renderSpill(); }, 150); });
  })
  .catch(err => { LAB.failed($('#front-answer'), err); });
