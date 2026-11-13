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
// Two more sets of samples share the page (docs/SAMPLE-HISTORY-CONTRACT-v1.md): every EPA sample at the Republic of
// Ireland's bathing waters since 2014, and Natural Resources Wales's at Hay-on-Wye and Llandeilo, from the files the
// build splits them into (build_site.write_sample_histories): data/research/history/<set>.json and
// data/research/history/<set>/<id>.json. They are observations only: no estimate, no forecast and no SwimSignal spot
// page beside them, the official body's rating and page first, and each source's methods and limits in its own words.
// The address picks the set and the water: #spot=<id> (England, as before), #ireland=<id>, #wales=<id>; #ireland or
// #wales alone opens that set's list.
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

// Why a sample has no hindsight estimate (1.1, `hindsight_reason`), in a few words for its table cell; the export's
// `hindsight_reasons` says each in a sentence under the table.
const SAMPLES_WHY = { before_2024: 'none: 2023, no archived rain', no_overflow_upstream: 'none: no overflow upstream',
  archive_only: 'none: only in the Water Quality Archive' };
const samplesWhy = s => SAMPLES_WHY[s && s.hindsight_reason] || 'none';
// The reasons among some samples, each once, in the export's order, with its sentence.
function samplesReasons(samples, doc) {
  const said = (doc && doc.hindsight_reasons) || {}, seen = new Set((samples || []).filter(s => typeof s.hindsight !== 'number').map(s => s.hindsight_reason));
  return Object.keys(said).filter(k => seen.has(k)).map(k => [k, said[k]]);
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
  // The limit itself where the export gives it (1.1, `below_limit_value`): "given only as below 10".
  const lim = typeof s.below_limit_value === 'number' ? samplesNum(s.below_limit_value) : "the lab's limit";
  const below = s.below_limit ? ` ${samplesNum(s.below_limit)} ${s.below_limit === 1 ? 'was' : 'were'} given only as below ${lim}.` : '';
  return `<p class="sm-counts"><b>${samplesPlural(s.samples, 'sample')}, ${samplesEsc(samplesDate(s.first))} to ${samplesEsc(samplesDate(s.last))}.</b> `
    + `${samplesNum(s.over_900 || 0)} ${s.over_900 === 1 ? 'was' : 'were'} over ${samplesNum(line)} E.&nbsp;coli per 100&nbsp;ml.${below}</p>`
    + `<p class="sm-note">${samplesNum(line)} per 100&nbsp;ml is the line of the inland "sufficient" standard, which the Environment Agency applies to up to four seasons of samples together, so one sample sets no rating. A sample is the water at that place and time only.</p>`;
}
// The hindsight estimate beside the samples: what it is, how often it agreed, and the export's own sentence.
function samplesHindsight(meta, doc) {
  const s = meta.summary || {}, warn = samplesWarn(doc), line = samplesLine(doc), pw = ((doc && doc.claim) || {}).public_wording;
  const claim = pw ? `<p class="sm-claim">${samplesEsc(pw)}</p>` : '';
  if (!s.with_hindsight) {   // the export's own reason where every sample shares one (1.1), else the general one
    // No overflow upstream outranks a year's missing rain: it holds for every sample here.
    const why = samplesReasons((meta.site && meta.site.samples) || [], doc), one = why.find(([k]) => k === 'no_overflow_upstream') || (why.length === 1 && why[0]);
    return `<p class="sm-hind">No hindsight estimate here: ${one ? samplesEsc(one[1].replace(/^./, c => c.toLowerCase())) : 'the study it comes from did not cover this bathing water.'}</p>` + claim;
  }
  const m = s.hindsight_misses || 0, f = s.hindsight_false_alarms || 0, pct = `${Math.round(warn * 100)}%`;
  return `<p class="sm-hind">${samplesNum(s.with_hindsight)} of the ${samplesPlural(s.samples, 'sample')} ${s.with_hindsight === 1 ? 'has' : 'have'} a hindsight estimate: the chance a model worked out afterwards puts on the count being over ${samplesNum(line)}. `
    + `It was not shown on the site at the time and is not the forecast the site issued. `
    + `${m ? `${samplesPlural(m, 'sample')} ${m === 1 ? 'was' : 'were'} over ${samplesNum(line)} with an estimate under ${pct} (a miss)` : `No sample over ${samplesNum(line)} had an estimate under ${pct} (a miss)`}; `
    + `${f ? `${samplesPlural(f, 'sample')} ${f === 1 ? 'was' : 'were'} not over ${samplesNum(line)} with an estimate of ${pct} or more (a false alarm)` : `no sample under it had an estimate of ${pct} or more (a false alarm)`}. `
    + `${pct} is the site's warning line for rivers.`
    // 1.1, `warn_at_note`: at a lake the same counts are for comparison only.
    + (doc && doc.warn_at_note && meta.kind !== 'river' ? ' At a lake these two counts are for comparison only: the site gives no E.&nbsp;coli warning at lakes.' : '')
    + '</p>' + claim;
}
// The samples as dots, one row a season on the same months, so a gap between samples shows as space. A log scale
// from 10 to 10,000 per 100 ml (each step up is ten times more), with the 900 line drawn and labelled. A count given
// as a limit is a hollow dot in a band of its own above or below the scale, labelled in words, so "below 10" is
// never drawn as 10. No colour but the brand's: a count is not a risk level.
const SAMPLES_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function samplesChart(samples, width, line = SAMPLES_LINE, hindsight = true) {
  const pts = (samples || []).filter(s => s && s.t && typeof s.ecoli === 'number');
  if (!pts.length) return '';
  const seen = [...new Set(pts.map(s => +s.t.slice(0, 4)))].sort(), years = [];
  for (let y = seen[0]; y <= seen[seen.length - 1]; y++) years.push(y);
  const months = pts.map(s => +s.t.slice(5, 7)), m0 = Math.min(5, ...months), m1 = Math.max(9, ...months);
  const lows = [...new Set(pts.filter(s => s.q === '<').map(s => s.ecoli))], highs = [...new Set(pts.filter(s => s.q === '>').map(s => s.ecoli))];
  const top = Math.max(4, Math.ceil(Math.log10(Math.max(10, ...pts.filter(s => !s.q).map(s => s.ecoli)))));   // decades: 10^bot to 10^top
  // From 1 where a lab gave plain counts under 10 (some Irish labs count from 1), else from 10, as before.
  const bot = pts.some(s => !s.q && s.ecoli < 10) ? 0 : 1, hasLine = typeof line === 'number';
  const W = Math.max(260, Math.min(720, Math.round(width) || 600)), padL = 56, padR = 8, head = 18, band = 12, scale = 25 * (top - bot), gap = 14;
  const rowH = head + band + scale + band, H = years.length * (rowH + gap) + 16;
  const span = (y, m) => Date.parse(`${y}-${String(m).padStart(2, '0')}-01T00:00Z`);
  const x = t => { const y = +t.slice(0, 4), t0 = span(y, m0), t1 = m1 === 12 ? span(y + 1, 1) : span(y, m1 + 1);
    return padL + (W - padL - padR) * Math.min(1, Math.max(0, (Date.parse(t.slice(0, 10) + 'T12:00Z') - t0) / (t1 - t0))); };
  const y0 = r => r * (rowH + gap) + head + band;   // the scale's top in row r
  const yv = (v, r) => y0(r) + scale * (1 - (Math.log10(Math.min(10 ** top, Math.max(10 ** bot, v))) - bot) / (top - bot));
  const yOf = (s, r) => (s.q === '<' ? y0(r) + scale + band / 2 + 1 : s.q === '>' ? y0(r) - band / 2 - 1 : yv(s.ecoli, r));
  // "below 10"; two or three limits by name ("below 1 or 10", as Irish labs' differ); more as "below the limit".
  const words = (vals, w) => { const v = [...vals].sort((a, b) => a - b).map(samplesNum);
    return v.length === 1 ? `${w} ${v[0]}` : v.length <= 3 ? `${w} ${v.slice(0, -1).join(', ')} or ${v[v.length - 1]}` : `${w} the limit`; };
  let g = '';
  years.forEach((yr, r) => {
    const t = y0(r), mine = pts.filter(s => +s.t.slice(0, 4) === yr);
    g += `<text x="0" y="${t - band - 5}" class="sm-yr">${yr}</text><rect x="${padL}" y="${t}" width="${W - padL - padR}" height="${scale}" class="sm-band"/>`
      + `<line x1="${padL}" x2="${W - padR}" y1="${yv(100, r).toFixed(1)}" y2="${yv(100, r).toFixed(1)}" class="sm-grid"/><text x="${padL - 6}" y="${(yv(100, r) + 4).toFixed(1)}" class="sm-ax">100</text>`
      + (bot === 0 ? `<line x1="${padL}" x2="${W - padR}" y1="${yv(10, r).toFixed(1)}" y2="${yv(10, r).toFixed(1)}" class="sm-grid"/><text x="${padL - 6}" y="${(yv(10, r) + 4).toFixed(1)}" class="sm-ax">10</text>` : '')
      + (hasLine ? `<line x1="${padL}" x2="${W - padR}" y1="${yv(line, r).toFixed(1)}" y2="${yv(line, r).toFixed(1)}" class="sm-line"/><text x="${padL - 6}" y="${(yv(line, r) + 4).toFixed(1)}" class="sm-ax sm-ax-line">${samplesNum(line)}</text>` : '')
      + (lows.length ? `<text x="${padL - 6}" y="${t + scale + band / 2 + 5}" class="sm-ax">${samplesEsc(words(lows, 'below'))}</text>` : '')
      + (highs.length ? `<text x="${padL - 6}" y="${t - band / 2 + 3}" class="sm-ax">above</text><text x="${padL - 6}" y="${t - band / 2 + 16}" class="sm-ax">${highs.length === 1 ? samplesNum(highs[0]) : 'a limit'}</text>` : '')
      + (mine.length ? '' : `<text x="${padL + 8}" y="${t + scale / 2 + 4}" class="sm-ax-in">No samples in this file this season</text>`)
      + mine.map(s => `<circle cx="${x(s.t).toFixed(1)}" cy="${yOf(s, r).toFixed(1)}" r="3.5" class="${s.q ? 'sm-dot-lim' : 'sm-dot'}"><title>${samplesEsc(samplesDate(s.t))}: ${samplesEsc(samplesCount(s.ecoli, s.q))} E. coli per 100 ml</title></circle>`).join('');
  });
  const bottom = years.length * (rowH + gap), mx = m => padL + (W - padL - padR) * (span(2001, m) - span(2001, m0)) / ((m1 === 12 ? span(2002, 1) : span(2001, m1 + 1)) - span(2001, m0));
  for (let m = m0; m <= m1; m++) g += `<text x="${mx(m).toFixed(1)}" y="${bottom + 2}" class="sm-mo">${SAMPLES_MONTHS[m - 1]}</text>`;
  const over = pts.filter(samplesOver).length, lim = pts.filter(s => s.q).length;
  const label = `E. coli samples by date, ${samplesPlural(pts.length, 'sample')} in ${samplesPlural(seen.length, 'season')}${hasLine ? `, ${samplesNum(over)} over ${samplesNum(line)} per 100 ml` : ''}${lim ? `, ${samplesNum(lim)} given as a limit` : ''}. The table below gives every sample in words.`;
  return `<figure class="sm-fig"><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${samplesEsc(label)}">${g}</svg>`
    + `<figcaption>Each dot is one sample; each row is one season. The scale runs from ${samplesNum(10 ** bot)} to ${samplesNum(10 ** top)} E.&nbsp;coli per 100&nbsp;ml, each step up ten times the one below${hasLine ? `, with the ${samplesNum(line)} line drawn` : ''}.`
    + (pts.some(s => !s.q && s.ecoli === 0) ? ' A count of 0 is drawn at the foot of the scale.' : '')
    + `${lim ? ` A hollow dot is a count the lab gave only as a limit: ${[lows.length ? `under the scale, ${samplesEsc(words(lows, 'below'))}` : '', highs.length ? `over it, ${samplesEsc(words(highs, 'above'))}` : ''].filter(Boolean).join('; ')}.` : ''}`
    + (hindsight ? ' The hindsight estimates are in the table only.' : '') + '</figcaption></figure>';
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
    return p ? `${p}${m ? ` (a ${m})` : ''}` : `<span class="sm-dash">${samplesEsc(samplesWhy(s))}</span>`;
  };
  return `<p class="sm-cap">Every sample here, newest first, per 100&nbsp;ml. The last column was worked out afterwards, not shown on the site at the time.</p>`
    + `<div class="tw"><table class="sm-table"><thead><tr><th scope="col">Taken</th><th scope="col">E.&nbsp;coli</th><th scope="col">Intestinal enterococci</th><th scope="col">Model in hindsight, worked out afterwards</th></tr></thead>`
    + years.map(y => {
      const g = rows.filter(s => s.t.startsWith(y)), o = g.filter(samplesOver).length;
      return `<tbody><tr><th scope="rowgroup" colspan="4" class="sm-year">${y}: ${samplesPlural(g.length, 'sample')}, ${samplesNum(o)} over ${samplesNum(line)}</th></tr>`
        + g.map(s => `<tr><td>${samplesEsc(samplesDay(s.t))}${days[s.t.slice(0, 10)] > 1 ? `, ${samplesEsc(samplesClock(s.t))}` : ''}</td><td>${cell(s)}</td>`
          + `<td>${typeof s.ie === 'number' ? samplesEsc(samplesCount(s.ie, s.ie_q)) : '<span class="sm-dash">not in this file</span>'}</td><td>${hind(s)}</td></tr>`).join('') + '</tbody>';
    }).join('') + '</table></div>'
    + samplesReasonsNote(all, doc)
    + (all.some(s => typeof s.ie !== 'number') ? '<p class="sm-note">"Not in this file": the samples from the Water Quality Archive carry E.&nbsp;coli only.</p>' : '');
}
// Under the table: why the samples without an estimate have none, each reason once in the export's words (1.1); a
// file without reasons says the study did not cover them.
function samplesReasonsNote(all, doc) {
  if (!all.some(s => typeof s.hindsight !== 'number')) return '';
  const why = samplesReasons(all, doc);
  if (!why.length) return '<p class="sm-note">"None" in the last column: the hindsight study did not cover that sample.</p>';
  return `<p class="sm-note">Why a sample has no estimate:</p><ul class="sm-why">${why.map(([, t]) => `<li>${samplesEsc(t)}</li>`).join('')}</ul>`;
}
// One bathing water whole: the official word, the counts, the chart, the hindsight estimate with the export's own
// sentence beside it, and every sample.
function samplesSite(site, meta, doc, width) {
  return `<article class="sm-site"><h2 id="sm-h">${samplesEsc(meta.name || site.name)}</h2>`
    + `<p class="sm-meta">${meta.kind === 'river' ? 'River' : 'Lake or pond'} bathing water</p>`
    + samplesOfficial(meta) + samplesCounts(meta, doc) + samplesChart(site.samples, width, samplesLine(doc))
    + samplesHindsight({ ...meta, site }, doc) + samplesTable(site, doc) + '</article>';
}

// ------------------------------------------------------------------------------ Ireland and Wales
// The sets on the page, in the order of the "Where" picker: each one's address key, its files, its official body and
// how a water is named in the counts. England's is the E. coli evidence export; the other two are sample histories.
const SAMPLES_SETS = {
  england: { label: 'England: inland bathing waters', key: 'spot', index: 'data/research/ecoli.json', file: id => `data/research/ecoli/${id}.json`, noun: 'bathing water' },
  wales: { label: 'Wales: Hay-on-Wye and Llandeilo', key: 'wales', index: 'data/research/history/wales.json', file: id => `data/research/history/wales/${id}.json`, noun: 'bathing water', body: "Natural Resources Wales's" },
  ireland: { label: 'Republic of Ireland', key: 'ireland', index: 'data/research/history/ireland.json', file: id => `data/research/history/ireland/${id}.json`, noun: 'water', body: "the Environmental Protection Agency's" },
};
const samplesIdOf = (x, set) => (set === 'england' ? x.spot_id : x.id);
// The set and the water an address names: "#ireland=IEWEBWC010_0000_0040" -> ['ireland', id]; "#wales" -> ['wales', ''];
// anything else is England's, as before (#spot=<id>, or nothing).
function samplesWhere(hash) {
  const m = String(hash || '').match(/^#(spot|wales|ireland)(?:=([A-Za-z0-9_-]+))?$/);
  if (!m) return ['england', ''];
  return [m[1] === 'spot' ? 'england' : m[1], m[2] ? decodeURIComponent(m[2]) : ''];
}
const samplesHash = (set, id) => (set === 'england' ? (id ? `spot=${encodeURIComponent(id)}` : '') : `${SAMPLES_SETS[set].key}${id ? `=${encodeURIComponent(id)}` : ''}`);
function samplesSetPicker(set) {
  return `<label class="sm-pick">Where<select id="sm-set">${Object.entries(SAMPLES_SETS).map(([k, v]) => `<option value="${k}"${k === set ? ' selected' : ''}>${samplesEsc(v.label)}</option>`).join('')}</select></label>`;
}
// Ireland's waters by county, then by name, folding accents ("Trá" beside "Tra"); Wales's are both rivers.
const samplesFold = s => String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
function samplesHistoryGroups(index) {
  const all = ((index && index.sites) || []).slice().sort((a, b) => samplesFold(a.name).localeCompare(samplesFold(b.name), 'en-GB'));
  if (index && index.nation === 'wales') return [['Rivers', all]];
  const counties = [...new Set(all.map(x => x.county || 'County not given'))].sort((a, b) => samplesFold(a).localeCompare(samplesFold(b), 'en-GB'));
  return counties.map(c => [`County ${c.replace(/^County /, '')}`, all.filter(x => (x.county || 'County not given') === c)]);
}
function samplesHistoryPicker(index, sel) {
  const what = index && index.nation === 'ireland' ? 'Water' : 'Bathing water';
  return `<label class="sm-pick">${what}<select id="sm-select"><option value="">Choose a ${what.toLowerCase()}</option>${samplesHistoryGroups(index).map(([h, g]) => `<optgroup label="${samplesEsc(h)}">`
    + g.map(x => `<option value="${samplesEsc(x.id)}"${x.id === sel ? ' selected' : ''}>${samplesEsc(x.name)}</option>`).join('') + '</optgroup>').join('')}</select></label>`;
}
// What the set's file is, first and plainly: its dates, how many waters and samples, when it was read and that
// nothing after its last sample is in it.
function samplesHistorySummary(index) {
  const set = SAMPLES_SETS[(index && index.nation) || 'ireland'] || SAMPLES_SETS.ireland;
  if (!index || !index.available) return `<p class="sm-none">No samples are published in this update${index && index.why ? ` (${samplesEsc(index.why)})` : ''}.</p>`;
  const r = samplesRange(index), L = index.sites || [], n = L.reduce((a, x) => a + ((x.summary || {}).samples || 0), 0);
  if (!r) return '<p class="sm-none">No samples are published in this update.</p>';
  // When it was copied; NRW's archive part is a copy of its own (the zips' date, `archive.zips[].csv_modified`).
  const zips = ((index.archive || {}).zips || []).map(z => z.csv_modified).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d || '')).sort();
  const read = index.fetched_at ? ` Copied from ${samplesEsc(set.body)} published data on ${samplesEsc(samplesDate(index.fetched_at))}`
    + (zips.length ? `, its Water Quality Archive part as published on ${samplesEsc(samplesDate(zips[zips.length - 1]))}.` : '.') : '';
  return `<p class="sm-range"><b>${samplesEsc(samplesDate(r.first))} to ${samplesEsc(samplesDate(r.last))}</b>: ${samplesPlural(n, 'sample')} at ${samplesPlural(L.length, set.noun)}. `
    + `A historical record: nothing after ${samplesEsc(samplesDate(r.last))} is in it.${read}</p>`;
}
// The official word first: the body's rating and its own page for the rating, today's advice and its own copy of
// the samples. No SwimSignal spot page: SwimSignal makes no forecast here.
function samplesHistoryOfficial(meta, index) {
  const nation = index && index.nation, r = meta.rating || null, link = /^https:\/\//.test(meta.page || '');
  if (nation === 'ireland') {
    const head = meta.designated === false ? '<p class="sm-rating"><b>Not a designated bathing water</b>: a water the council monitors, so it has no EPA rating.</p>'
      : r && r.value ? `<p class="sm-rating"><b>EPA rating: ${samplesEsc(r.value)}</b>${r.year ? ` (${samplesEsc(r.year)})` : ''}.</p>`
        : `<p class="sm-rating"><b>${meta.unrated_year ? `Not classified in ${samplesEsc(meta.unrated_year)}` : 'No EPA rating listed'}</b>.</p>`;
    const page = link ? `<a href="${samplesEsc(meta.page)}">this water's page on beaches.ie</a>` : "this water's page on beaches.ie";
    return head + `<p class="sm-official">Any restriction in force, the rating and the EPA's own results are on ${page}, the EPA's site. Check it before you swim.</p>`;
  }
  const head = r && r.value ? `<p class="sm-rating"><b>Natural Resources Wales rating: ${samplesEsc(r.value)}</b>${r.year ? ` (${samplesEsc(r.year)})` : ''}.</p>`
    : '<p class="sm-rating"><b>No Natural Resources Wales rating yet</b>: a rating needs more seasons of samples.</p>';
  const page = link ? `<a href="${samplesEsc(meta.page)}">Natural Resources Wales's page for this bathing water</a>` : "Natural Resources Wales's page for this bathing water";
  return head + `<p class="sm-official">The rating, the season's advice and NRW's own sample results are on ${page}. SwimSignal makes no forecast in Wales.</p>`;
}
// The counts: how many samples, their dates, how many were over the water's line, how many were given as a limit,
// and, as each source has them, the EPA's Poor samples and out-of-season samples or NRW's investigation samples.
function samplesHistoryCounts(meta) {
  const s = meta.summary || {}, line = meta.line;
  if (!s.samples) return '<p class="sm-none">No samples here in this file.</p>';
  const parts = [`<b>${samplesPlural(s.samples, 'sample')}, ${samplesEsc(samplesDate(s.first))} to ${samplesEsc(samplesDate(s.last))}.</b>`];
  if (typeof line === 'number') parts.push(`${samplesNum(s.over_line || 0)} ${s.over_line === 1 ? 'was' : 'were'} over ${samplesNum(line)} E.&nbsp;coli per 100&nbsp;ml.`);
  if (s.below_limit) parts.push(`${samplesNum(s.below_limit)} ${s.below_limit === 1 ? 'was' : 'were'} given only as below the lab's lower limit.`);
  if (s.above_limit) parts.push(`${samplesNum(s.above_limit)} ${s.above_limit === 1 ? 'was' : 'were'} given only as above its upper limit.`);
  if (typeof s.poor === 'number') parts.push(`The EPA assessed ${samplesNum(s.poor)} as Poor.`);
  if (s.out_of_season) parts.push(`${samplesNum(s.out_of_season)} ${s.out_of_season === 1 ? 'was' : 'were'} taken out of season: voluntary, and not counted towards a rating.`);
  if (s.investigation) parts.push(`${samplesNum(s.investigation)} ${s.investigation === 1 ? 'was a planned investigation sample' : 'were planned investigation samples'}, not statutory monitoring.`);
  const coast = meta.kind === 'coast' || meta.kind === 'estuary';
  const note = typeof line !== 'number' ? '<p class="sm-note">What kind of water this is was not settled, so no line is drawn. A sample is the water at that place and time only.</p>'
    : `<p class="sm-note">${samplesNum(line)} per 100&nbsp;ml is the line of the ${coast ? 'coastal' : 'inland'} "sufficient" standard, which applies to four seasons of scheduled samples together, so one sample sets no rating. A sample is the water at that place and time only.</p>`;
  return `<p class="sm-counts">${parts.join(' ')}</p>` + note;
}
const SAMPLES_REASON = { statutory: 'Statutory monitoring', investigation: 'Planned investigation', other: 'Other' };
// Every sample, newest first, a season to a group: the date, E. coli in words with whether it was over the line, the
// enterococci, and what the source says of the sample: the EPA's word (and "out of season"), or why NRW took it.
function samplesHistoryTable(site, meta, index) {
  const all = (site.samples || []).filter(s => s && s.t), line = meta.line, ireland = index && index.nation === 'ireland';
  if (!all.length) return '';
  const rows = [...all].sort((a, b) => b.t.localeCompare(a.t)), years = [...new Set(rows.map(s => s.t.slice(0, 4)))];
  const days = all.reduce((a, s) => ({ ...a, [s.t.slice(0, 10)]: (a[s.t.slice(0, 10)] || 0) + 1 }), {});
  const cell = s => { const c = samplesCount(s.ecoli, s.q); return samplesOver(s) ? `<b>${samplesEsc(c)}</b>, over ${samplesNum(line)}` : samplesEsc(c); };
  const last = s => (ireland ? `${samplesEsc(s.status || 'none given')}${s.season === 'out' ? ', out of season' : ''}` : samplesEsc(SAMPLES_REASON[s.reason] || 'Other'));
  const when = s => `${samplesEsc(samplesDay(s.t))}${s.t.length > 10 && days[s.t.slice(0, 10)] > 1 ? `, ${samplesEsc(samplesClock(s.t))}` : ''}`;
  const head = ireland ? "The EPA's word for the sample" : 'Why it was taken';
  return `<p class="sm-cap">Every sample here, newest first, per 100&nbsp;ml.</p>`
    + `<div class="tw"><table class="sm-table"><thead><tr><th scope="col">Taken</th><th scope="col">E.&nbsp;coli</th><th scope="col">Intestinal enterococci</th><th scope="col">${head}</th></tr></thead>`
    + years.map(y => {
      const g = rows.filter(s => s.t.startsWith(y)), o = g.filter(samplesOver).length;
      return `<tbody><tr><th scope="rowgroup" colspan="4" class="sm-year">${y}: ${samplesPlural(g.length, 'sample')}${typeof line === 'number' ? `, ${samplesNum(o)} over ${samplesNum(line)}` : ''}</th></tr>`
        + g.map(s => `<tr><td>${when(s)}</td><td>${cell(s)}</td><td>${typeof s.ie === 'number' ? samplesEsc(samplesCount(s.ie, s.ie_q)) : '<span class="sm-dash">not given</span>'}</td><td>${last(s)}</td></tr>`).join('') + '</tbody>';
    }).join('') + '</table></div>';
}
// How the samples were measured and what "below" and "above" mean, in the export's own words (`methods`,
// `qualifiers`), then its approved sentence.
function samplesHistoryMethods(index) {
  const m = (index && index.methods) || [], q = (index && index.qualifiers) || {}, pw = ((index && index.claim) || {}).public_wording;
  const items = [...(q['<'] ? [`"Below": ${q['<']}`] : []), ...(q['>'] ? [`"Above": ${q['>']}`] : []), ...m];
  return (items.length ? `<h3 class="sm-h3">How these samples were measured</h3><ul class="sm-why">${items.map(x => `<li>${samplesEsc(x)}</li>`).join('')}</ul>` : '')
    + (pw ? `<p class="sm-claim">${samplesEsc(pw)}</p>` : '');
}
// One water whole: the official word, the counts, the chart, every sample, then how they were measured.
function samplesHistorySite(site, meta, index, width) {
  const ireland = index && index.nation === 'ireland';
  const kind = { coast: 'Coastal water', estuary: 'Estuary water', lake: 'Lake', river: 'River' }[meta.kind] || 'Water';
  const where = ireland ? [meta.county ? `County ${String(meta.county).replace(/^County /, '')}` : '', meta.designated === false ? 'monitored by the council' : 'designated bathing water'].filter(Boolean).join(', ')
    : `bathing water on the ${samplesEsc(meta.river || 'river')}`;
  return `<article class="sm-site"><h2 id="sm-h">${samplesEsc(meta.name || site.name)}</h2>`
    + `<p class="sm-meta">${samplesEsc(kind)}, ${samplesEsc(where)}</p>`
    + samplesHistoryOfficial(meta, index) + samplesHistoryCounts(meta)
    + samplesChart(site.samples, width, typeof meta.line === 'number' ? meta.line : null, false)
    + samplesHistoryTable(site, meta, index) + samplesHistoryMethods(index) + '</article>';
}

// ------------------------------------------------------------------------------ in the page
// The page's blocks marked data-set="england" (the hindsight estimate) or "history" show only with their set; without
// the script every block shows.
function samplesShowBlocks(root, set) {
  for (const el of root.querySelectorAll('[data-set]')) el.hidden = el.dataset.set !== (set === 'england' ? 'england' : 'history');
}
function samplesMount(root) {
  const host = root.getElementById('samples');
  if (!host) return;
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const indexes = {};
  host.innerHTML = samplesSetPicker(samplesWhere(location.hash)[0]) + '<div id="sm-body"></div>';
  const setSel = root.getElementById('sm-set'), body = root.getElementById('sm-body');
  setSel.addEventListener('change', () => { location.hash = samplesHash(setSel.value, ''); });
  let shown = null;   // the set whose summary and picker are drawn, so the picker keeps its focus on a change of water
  const draw = () => {
    const [set, id] = samplesWhere(location.hash), conf = SAMPLES_SETS[set];
    if (setSel.value !== set) setSel.value = set;
    samplesShowBlocks(root, set);
    const index = indexes[set];
    if (index === undefined) {
      body.innerHTML = '<p class="sm-none">Loading…</p>';
      shown = null;
      get(conf.index).then(x => { indexes[set] = x; if (samplesWhere(location.hash)[0] === set) draw(); });
      return;
    }
    if (!index) { body.innerHTML = '<p class="sm-none">The samples could not be loaded.</p>'; shown = null; return; }
    if (shown !== set) {
      const attrib = root.getElementById('sm-attrib');
      if (attrib && set === 'england' && Array.isArray(index.attribution) && index.attribution.length) attrib.textContent = index.attribution.join('. ').replace(/\.?$/, '.');
      body.innerHTML = (set === 'england' ? samplesSummary(index) : samplesHistorySummary(index))
        + (index.available ? (set === 'england' ? samplesPicker(index, id) : samplesHistoryPicker(index, id)) + '<div id="sm-one"></div>' : '');
      const sel = root.getElementById('sm-select');
      if (sel) sel.addEventListener('change', () => { location.hash = samplesHash(set, sel.value); });
      shown = set;
    }
    const sel = root.getElementById('sm-select'), one = root.getElementById('sm-one');
    const meta = (index.sites || []).find(x => samplesIdOf(x, set) === id);
    if (sel && sel.value !== id) sel.value = meta ? id : '';
    if (!one) return;
    if (!meta) { one.innerHTML = ''; return; }
    one.innerHTML = '<p class="sm-none">Loading…</p>';
    get(conf.file(encodeURIComponent(id))).then(site => {
      const [s2, i2] = samplesWhere(location.hash);
      if (s2 !== set || i2 !== id) return;
      one.innerHTML = !site ? '<p class="sm-none">This water could not be loaded.</p>'
        : set === 'england' ? samplesSite(site, meta, index, one.clientWidth) : samplesHistorySite(site, meta, index, one.clientWidth);
    });
  };
  window.addEventListener('hashchange', draw);
  draw();
}
if (typeof document === 'object' && document.getElementById) samplesMount(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { SAMPLES_LINE, SAMPLES_WARN, samplesCount, samplesOver, samplesPct, samplesMatch, samplesGroups, samplesPicker, samplesRange,
    samplesSummary, samplesOfficial, samplesCounts, samplesHindsight, samplesChart, samplesTable, samplesSite, samplesDate, samplesMonth, samplesWhy,
    samplesReasons, samplesReasonsNote, SAMPLES_SETS, samplesWhere, samplesHash, samplesSetPicker, samplesHistoryGroups, samplesHistoryPicker,
    samplesHistorySummary, samplesHistoryOfficial, samplesHistoryCounts, samplesHistoryTable, samplesHistoryMethods, samplesHistorySite };
}
