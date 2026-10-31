// Every Environment Agency E. coli sample at an inland bathing water (samples.html, linked from each bathing water's
// latest lab sample, evidence.js): what the research export holds (docs/ECOLI-EVIDENCE-CONTRACT-v1.md, version 1),
// read from the files the build splits it into (build_site.write_ecoli_evidence): data/research/ecoli.json, every
// bathing water without its samples, and data/research/ecoli/<spot_id>.json, one bathing water whole.
//
// What it may say is the contract's, and only that: what the lab measured and when, how many samples were over 900,
// and how a hindsight model estimate compared with each sample. The official rating and today's advice come first
// and link to the Environment Agency's own page; everything here is under them. A count given as a limit is said in
// words ("below 10", "above 10,000"), never as the number: the chart draws it in a band of its own, off the scale.
// The hindsight estimate is never the forecast: it was worked out afterwards, the site never showed it (`issued`
// false), and every place it appears says so. A miss or a false alarm is a mismatch between model and sample, and
// the export's own sentence says so beside the counts; nothing here names a source, an overflow or a company.
// No level colours: a colour on this site means a risk level, and a count is not one.
//
// The dataset is historical: it runs to its last sample, and its date range is said first, so an old file cannot
// read as this season's.
//
// A plain script, like lakes.js: in the page its names are globals (each begins samples or SAMPLES), and in Node the
// last lines export them (tests/site_samples.test.cjs).

const SAMPLES_LINE = 900;   // the export's `line`: the inland "sufficient" standard's E. coli line, per 100 ml
const SAMPLES_WARN = 0.25;  // the export's `warn_at`: the site's river warning line
const samplesEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
// A sample's time is the Environment Agency's, with its offset (UK time): its date and clock are read as written.
const samplesDate = iso => new Date(String(iso).slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const samplesDay = iso => samplesDate(iso).replace(/ \d{4}$/, '');
const samplesMonth = iso => new Date(String(iso).slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const samplesClock = iso => String(iso).slice(11, 16);
const samplesNum = v => Number(v).toLocaleString('en-GB');
const samplesPlural = (n, one, many = `${one}s`) => `${samplesNum(n)} ${n === 1 ? one : many}`;
const samplesLine = doc => (doc && typeof doc.line === 'number' ? doc.line : SAMPLES_LINE);
const samplesWarn = doc => (doc && typeof doc.warn_at === 'number' ? doc.warn_at : SAMPLES_WARN);

// ------------------------------------------------------------------------------ one count
// A count in words, with its qualifier: "below 10", "above 10,000", "630". Empty without a number.
function samplesCount(v, q) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '';
  return q === '<' ? `below ${samplesNum(v)}` : q === '>' ? `above ${samplesNum(v)}` : samplesNum(v);
}
// Over the line, as the export's `over` says it; a limit is never read as the count. Exactly 900 is not over.
const samplesOver = s => s.over === true;
// The hindsight estimate, a chance: "4%", "under 1%", "over 99%"; '' for none.
function samplesPct(p) {
  if (typeof p !== 'number' || !Number.isFinite(p)) return '';
  return p < 0.005 ? 'under 1%' : p > 0.995 ? 'over 99%' : `${Math.round(p * 100)}%`;
}
// How the estimate compared with the sample, the export's own two counts: a miss (over the line, estimate under the
// warning line) or a false alarm (not over, estimate at or over it); null where they agree or there is no estimate.
function samplesMatch(s, warn = SAMPLES_WARN) {
  if (typeof s.hindsight !== 'number') return null;
  if (samplesOver(s) && s.hindsight < warn) return 'miss';
  if (!samplesOver(s) && s.hindsight >= warn) return 'false alarm';
  return null;
}

// ------------------------------------------------------------------------------ the list
// The bathing waters in the picker: rivers, then lakes, by name within each. Each group as [heading, sites].
function samplesGroups(index) {
  const by = (a, b) => String(a.name).localeCompare(String(b.name), 'en-GB');
  const all = (index && index.sites) || [];
  return [['Rivers', all.filter(x => x.kind === 'river').sort(by)], ['Lakes and ponds', all.filter(x => x.kind !== 'river').sort(by)]].filter(([, g]) => g.length);
}
function samplesPicker(index, sel) {
  return `<label class="sm-pick">Bathing water<select id="sm-select"><option value="">Choose a bathing water</option>${samplesGroups(index).map(([h, g]) => `<optgroup label="${samplesEsc(h)}">`
    + g.map(x => `<option value="${samplesEsc(x.spot_id)}"${x.spot_id === sel ? ' selected' : ''}>${samplesEsc(x.name)}</option>`).join('') + '</optgroup>').join('')}</select></label>`;
}
// The first and last sample over the whole file.
function samplesRange(index) {
  const s = ((index && index.sites) || []).map(x => x.summary || {}).filter(x => x.first && x.last);
  if (!s.length) return null;
  return { first: s.map(x => x.first).sort()[0], last: s.map(x => x.last).sort().pop() };
}
// What the file is, first and plainly: its dates, how many bathing waters and samples, and that nothing after its
// last sample is in it.
function samplesSummary(index) {
  if (!index || !index.available) return `<p class="sm-none">No samples are published in this update${index && index.why ? ` (${samplesEsc(index.why)})` : ''}.</p>`;
  const r = samplesRange(index), L = index.sites || [], n = L.reduce((a, x) => a + ((x.summary || {}).samples || 0), 0);
  if (!r) return '<p class="sm-none">No samples are published in this update.</p>';
  return `<p class="sm-range"><b>${samplesEsc(samplesDate(r.first))} to ${samplesEsc(samplesDate(r.last))}</b>: ${samplesPlural(n, 'sample')} at ${samplesPlural(L.length, 'bathing water')}. `
    + `A historical record: nothing after ${samplesEsc(samplesDate(r.last))} is in it.</p>`;
}

// ------------------------------------------------------------------------------ one bathing water
// The official word first: the Environment Agency's rating in this build, and its own page for the rating, today's
// advice and its own copy of these samples; then this site's page for the spot.
function samplesOfficial(meta) {
  const r = meta.rating || null, ea = /^https:\/\//.test(meta.profile || '') ? `<a href="${samplesEsc(meta.profile)}">the Environment Agency's page for this bathing water</a>` : "the Environment Agency's page for this bathing water";
  const head = r && r.class ? `<p class="sm-rating"><b>Environment Agency rating: ${samplesEsc(String(r.class).replace(/^./, c => c.toUpperCase()))}</b>${r.year ? ` (${samplesEsc(r.year)})` : ''}.</p>`
    : '<p class="sm-rating"><b>No Environment Agency rating yet</b>: this bathing water is too new to have one.</p>';
  return head + `<p class="sm-official">The rating, today's advice and the Agency's own sample results are on ${ea}. `
    + `<a href="spot/${samplesEsc(encodeURIComponent(meta.spot_id))}/">This spot's page</a> has the forecast and today's advice beside it.</p>`;
}
// The counts: how many samples, their dates, how many were over 900 and how many were given as below the limit, then
// what 900 is. One sample sets no rating.
function samplesCounts(meta, doc) {
  const s = meta.summary || {}, line = samplesLine(doc);
  if (!s.samples) return '<p class="sm-none">No samples here in this file.</p>';
  const below = s.below_limit ? ` ${samplesNum(s.below_limit)} ${s.below_limit === 1 ? 'was' : 'were'} given only as below the lab's limit.` : '';
  return `<p class="sm-counts"><b>${samplesPlural(s.samples, 'sample')}, ${samplesEsc(samplesDate(s.first))} to ${samplesEsc(samplesDate(s.last))}.</b> `
    + `${samplesNum(s.over_900 || 0)} ${s.over_900 === 1 ? 'was' : 'were'} over ${samplesNum(line)} E.&nbsp;coli per 100&nbsp;ml.${below}</p>`
    + `<p class="sm-note">${samplesNum(line)} per 100&nbsp;ml is the line of the inland "sufficient" standard, which the Environment Agency applies to up to four seasons of samples together, so one sample sets no rating. A sample is the water at that place and time only.</p>`;
}
// The hindsight estimate beside the samples: what it is, how often it agreed, and the export's own sentence.
function samplesHindsight(meta, doc) {
  const s = meta.summary || {}, warn = samplesWarn(doc), line = samplesLine(doc), pw = ((doc && doc.claim) || {}).public_wording;
  const claim = pw ? `<p class="sm-claim">${samplesEsc(pw)}</p>` : '';
  if (!s.with_hindsight) return `<p class="sm-hind">No hindsight estimate here: the study it comes from did not cover this bathing water.</p>` + claim;
  const m = s.hindsight_misses || 0, f = s.hindsight_false_alarms || 0, pct = `${Math.round(warn * 100)}%`;
  return `<p class="sm-hind">${samplesNum(s.with_hindsight)} of the ${samplesPlural(s.samples, 'sample')} ${s.with_hindsight === 1 ? 'has' : 'have'} a hindsight estimate: the chance a model worked out afterwards puts on the count being over ${samplesNum(line)}. `
    + `It was not shown on the site at the time and is not the forecast the site issued. `
    + `${m ? `${samplesPlural(m, 'sample')} ${m === 1 ? 'was' : 'were'} over ${samplesNum(line)} with an estimate under ${pct} (a miss)` : `No sample over ${samplesNum(line)} had an estimate under ${pct} (a miss)`}; `
    + `${f ? `${samplesPlural(f, 'sample')} ${f === 1 ? 'was' : 'were'} not over ${samplesNum(line)} with an estimate of ${pct} or more (a false alarm)` : `no sample under it had an estimate of ${pct} or more (a false alarm)`}. `
    + `${pct} is the site's warning line for rivers.</p>` + claim;
}
// The samples as dots, one row a season on the same months, so a gap between samples shows as space. A log scale
// from 10 to 10,000 per 100 ml (each step up is ten times more), with the 900 line drawn and labelled. A count given
// as a limit is a hollow dot in a band of its own above or below the scale, labelled in words, so "below 10" is
// never drawn as 10. No colour but the brand's: a count is not a risk level.
const SAMPLES_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function samplesChart(samples, width, line = SAMPLES_LINE) {
  const pts = (samples || []).filter(s => s && s.t && typeof s.ecoli === 'number');
  if (!pts.length) return '';
  const seen = [...new Set(pts.map(s => +s.t.slice(0, 4)))].sort(), years = [];
  for (let y = seen[0]; y <= seen[seen.length - 1]; y++) years.push(y);
  const months = pts.map(s => +s.t.slice(5, 7)), m0 = Math.min(5, ...months), m1 = Math.max(9, ...months);
  const lows = [...new Set(pts.filter(s => s.q === '<').map(s => s.ecoli))], highs = [...new Set(pts.filter(s => s.q === '>').map(s => s.ecoli))];
  const top = Math.max(4, Math.ceil(Math.log10(Math.max(10, ...pts.filter(s => !s.q).map(s => s.ecoli)))));   // decades: 10 to 10^top
  const W = Math.max(260, Math.min(720, Math.round(width) || 600)), padL = 56, padR = 8, head = 18, band = 12, scale = 25 * (top - 1), gap = 14;
  const rowH = head + band + scale + band, H = years.length * (rowH + gap) + 16;
  const span = (y, m) => Date.parse(`${y}-${String(m).padStart(2, '0')}-01T00:00Z`);
  const x = t => { const y = +t.slice(0, 4), t0 = span(y, m0), t1 = m1 === 12 ? span(y + 1, 1) : span(y, m1 + 1);
    return padL + (W - padL - padR) * Math.min(1, Math.max(0, (Date.parse(t.slice(0, 10) + 'T12:00Z') - t0) / (t1 - t0))); };
  const y0 = r => r * (rowH + gap) + head + band;   // the scale's top in row r
  const yv = (v, r) => y0(r) + scale * (1 - (Math.log10(Math.min(10 ** top, Math.max(10, v))) - 1) / (top - 1));
  const yOf = (s, r) => (s.q === '<' ? y0(r) + scale + band / 2 + 1 : s.q === '>' ? y0(r) - band / 2 - 1 : yv(s.ecoli, r));
  const words = (vals, w) => (vals.length === 1 ? `${w} ${samplesNum(vals[0])}` : `${w} the limit`);
  let g = '';
  years.forEach((yr, r) => {
    const t = y0(r), mine = pts.filter(s => +s.t.slice(0, 4) === yr);
    g += `<text x="0" y="${t - band - 5}" class="sm-yr">${yr}</text><rect x="${padL}" y="${t}" width="${W - padL - padR}" height="${scale}" class="sm-band"/>`
      + `<line x1="${padL}" x2="${W - padR}" y1="${yv(100, r).toFixed(1)}" y2="${yv(100, r).toFixed(1)}" class="sm-grid"/><text x="${padL - 6}" y="${(yv(100, r) + 4).toFixed(1)}" class="sm-ax">100</text>`
      + `<line x1="${padL}" x2="${W - padR}" y1="${yv(line, r).toFixed(1)}" y2="${yv(line, r).toFixed(1)}" class="sm-line"/><text x="${padL - 6}" y="${(yv(line, r) + 4).toFixed(1)}" class="sm-ax sm-ax-line">${samplesNum(line)}</text>`
      + (lows.length ? `<text x="${padL - 6}" y="${t + scale + band / 2 + 5}" class="sm-ax">${samplesEsc(words(lows, 'below'))}</text>` : '')
      + (highs.length ? `<text x="${padL - 6}" y="${t - band / 2 + 3}" class="sm-ax">above</text><text x="${padL - 6}" y="${t - band / 2 + 16}" class="sm-ax">${highs.length === 1 ? samplesNum(highs[0]) : 'the limit'}</text>` : '')
      + (mine.length ? '' : `<text x="${padL + 8}" y="${t + scale / 2 + 4}" class="sm-ax-in">No samples in this file this season</text>`)
      + mine.map(s => `<circle cx="${x(s.t).toFixed(1)}" cy="${yOf(s, r).toFixed(1)}" r="3.5" class="${s.q ? 'sm-dot-lim' : 'sm-dot'}"><title>${samplesEsc(samplesDate(s.t))}: ${samplesEsc(samplesCount(s.ecoli, s.q))} E. coli per 100 ml</title></circle>`).join('');
  });
  const bottom = years.length * (rowH + gap), mx = m => padL + (W - padL - padR) * (span(2001, m) - span(2001, m0)) / ((m1 === 12 ? span(2002, 1) : span(2001, m1 + 1)) - span(2001, m0));
  for (let m = m0; m <= m1; m++) g += `<text x="${mx(m).toFixed(1)}" y="${bottom + 2}" class="sm-mo">${SAMPLES_MONTHS[m - 1]}</text>`;
  const over = pts.filter(samplesOver).length, lim = pts.filter(s => s.q).length;
  const label = `E. coli samples by date, ${samplesPlural(pts.length, 'sample')} in ${samplesPlural(seen.length, 'season')}, ${samplesNum(over)} over ${samplesNum(line)} per 100 ml${lim ? `, ${samplesNum(lim)} given as a limit` : ''}. The table below gives every sample in words.`;
  return `<figure class="sm-fig"><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${samplesEsc(label)}">${g}</svg>`
    + `<figcaption>Each dot is one sample; each row is one season. The scale runs from 10 to ${samplesNum(10 ** top)} E.&nbsp;coli per 100&nbsp;ml, each step up ten times the one below, with the ${samplesNum(line)} line drawn.`
    + `${lim ? ` A hollow dot is a count the lab gave only as a limit: ${[lows.length ? `under the scale, ${samplesEsc(words(lows, 'below'))}` : '', highs.length ? `over it, ${samplesEsc(words(highs, 'above'))}` : ''].filter(Boolean).join('; ')}.` : ''}`
    + ' The hindsight estimates are in the table only.</figcaption></figure>';
}
// Every sample, newest first, a season to a group: when it was taken, the E. coli count in words with whether it was
// over the line, the enterococci count, and the hindsight estimate in a column of its own, said to be worked out
// afterwards. Two samples on one day get their times.
function samplesTable(site, doc) {
  const all = (site.samples || []).filter(s => s && s.t), line = samplesLine(doc), warn = samplesWarn(doc);
  if (!all.length) return '';
  const days = all.reduce((a, s) => ({ ...a, [s.t.slice(0, 10)]: (a[s.t.slice(0, 10)] || 0) + 1 }), {});
  const rows = [...all].sort((a, b) => b.t.localeCompare(a.t)), years = [...new Set(rows.map(s => s.t.slice(0, 4)))];
  const cell = s => {
    const c = samplesCount(s.ecoli, s.q);
    return samplesOver(s) ? `<b>${samplesEsc(c)}</b>, over ${samplesNum(line)}` : samplesEsc(c);
  };
  const hind = s => {
    const p = samplesPct(s.hindsight), m = samplesMatch(s, warn);
    return p ? `${p}${m ? ` (a ${m})` : ''}` : '<span class="sm-dash">none</span>';
  };
  return `<p class="sm-cap">Every sample here, newest first, per 100&nbsp;ml. The last column was worked out afterwards, not shown on the site at the time.</p>`
    + `<div class="tw"><table class="sm-table"><thead><tr><th scope="col">Taken</th><th scope="col">E.&nbsp;coli</th><th scope="col">Intestinal enterococci</th><th scope="col">Model in hindsight, worked out afterwards</th></tr></thead>`
    + years.map(y => {
      const g = rows.filter(s => s.t.startsWith(y)), o = g.filter(samplesOver).length;
      return `<tbody><tr><th scope="rowgroup" colspan="4" class="sm-year">${y}: ${samplesPlural(g.length, 'sample')}, ${samplesNum(o)} over ${samplesNum(line)}</th></tr>`
        + g.map(s => `<tr><td>${samplesEsc(samplesDay(s.t))}${days[s.t.slice(0, 10)] > 1 ? `, ${samplesEsc(samplesClock(s.t))}` : ''}</td><td>${cell(s)}</td>`
          + `<td>${typeof s.ie === 'number' ? samplesEsc(samplesCount(s.ie, s.ie_q)) : '<span class="sm-dash">not in this file</span>'}</td><td>${hind(s)}</td></tr>`).join('') + '</tbody>';
    }).join('') + '</table></div>'
    + (all.some(s => typeof s.hindsight !== 'number') ? '<p class="sm-note">"None" in the last column: the hindsight study did not cover that sample.</p>' : '')
    + (all.some(s => typeof s.ie !== 'number') ? '<p class="sm-note">"Not in this file": the samples added from the Water Quality Archive carry E.&nbsp;coli only.</p>' : '');
}
// One bathing water whole: the official word, the counts, the chart, the hindsight estimate with the export's own
// sentence beside it, and every sample.
function samplesSite(site, meta, doc, width) {
  return `<article class="sm-site"><h2 id="sm-h">${samplesEsc(meta.name || site.name)}</h2>`
    + `<p class="sm-meta">${meta.kind === 'river' ? 'River' : 'Lake or pond'} bathing water</p>`
    + samplesOfficial(meta) + samplesCounts(meta, doc) + samplesChart(site.samples, width, samplesLine(doc))
    + samplesHindsight(meta, doc) + samplesTable(site, doc) + '</article>';
}

// ------------------------------------------------------------------------------ in the page
function samplesMount(root) {
  const host = root.getElementById('samples');
  if (!host) return;
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  get('data/research/ecoli.json').then(index => {
    if (!index) { host.innerHTML = '<p class="sm-none">The samples could not be loaded.</p>'; return; }
    const attrib = root.getElementById('sm-attrib');
    if (attrib && Array.isArray(index.attribution) && index.attribution.length) attrib.textContent = index.attribution.join('. ').replace(/\.?$/, '.');
    const pickId = () => decodeURIComponent((location.hash.match(/^#spot=([A-Za-z0-9_-]+)$/) || [])[1] || '');
    // The summary and the picker are drawn once, so the picker keeps its focus while a keyboard steps through it;
    // a change of bathing water redraws only the one below it.
    host.innerHTML = samplesSummary(index) + (index.available ? samplesPicker(index, pickId()) + '<div id="sm-one"></div>' : '');
    const sel = root.getElementById('sm-select'), one = root.getElementById('sm-one');
    if (sel) sel.addEventListener('change', () => { location.hash = sel.value ? `spot=${encodeURIComponent(sel.value)}` : ''; });
    const draw = () => {
      const id = pickId(), meta = (index.sites || []).find(x => x.spot_id === id);
      if (sel && sel.value !== id) sel.value = meta ? id : '';
      if (!one) return;
      if (!meta) { one.innerHTML = ''; return; }
      one.innerHTML = '<p class="sm-none">Loading…</p>';
      get(`data/research/ecoli/${encodeURIComponent(id)}.json`).then(site => {
        if (pickId() !== id) return;
        one.innerHTML = site ? samplesSite(site, meta, index, one.clientWidth) : '<p class="sm-none">This bathing water could not be loaded.</p>';
      });
    };
    window.addEventListener('hashchange', draw);
    draw();
  });
}
if (typeof document === 'object' && document.getElementById) samplesMount(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { SAMPLES_LINE, SAMPLES_WARN, samplesCount, samplesOver, samplesPct, samplesMatch, samplesGroups, samplesPicker, samplesRange,
    samplesSummary, samplesOfficial, samplesCounts, samplesHindsight, samplesChart, samplesTable, samplesSite, samplesDate, samplesMonth };
}
