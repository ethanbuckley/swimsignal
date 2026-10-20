// What the level rests on: one tile on a spot's page listing the evidence behind the answer, each item
// with how old it is and whose it is, and saying plainly what there is none of here. Each figure is
// also in a tile above it (Right now, Rain here, the EA rating, the algae); this is the one place where
// their ages and sources sit side by side, with the latest lab sample, which no tile shows. The river
// level and the water temperature are left out: they are not part of the level, and their tiles date them.
//
// The ages are counted when the page is read, not when it was built, so an old page says so. Times are
// UK times whatever the reader's clock, as the clearing time's are.
//
// A plain script, like guide.js: in the page its names are globals (each begins evidence or EVIDENCE,
// clear of the page's own and the other scripts': experience.js has evidenceRows, the Compare table's
// rows, so these are evidenceItems), and in Node the last lines export them (tests/site_evidence.test.cjs,
// which also checks that no other script of the page defines one of these names).

const EVIDENCE_TZ = 'Europe/London';
// The level rules (levels.js): the page loads them before this file, Node requires them.
const evidenceRules = () => typeof sampleLevel === 'function' ? { sampleLevel, daily, nowUnknown, nowUnknownWhy, companyName } : require('./levels.js');
const evidenceEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const evidenceNil = v => v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v));
const evidenceCap = s => s ? s[0].toUpperCase() + s.slice(1) : '';
const evidenceIcon = () => (typeof ICON === 'object' && ICON.evidence) || '';
// The UK calendar day of an instant, as 'YYYY-MM-DD'.
const evidenceISO = ms => new Intl.DateTimeFormat('en-CA', { timeZone: EVIDENCE_TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(ms));
const evidenceDays = (a, b) => Math.round((Date.parse(b + 'T12:00:00Z') - Date.parse(a + 'T12:00:00Z')) / 864e5);   // b minus a, whole days
// "24 Sept", with the year when it is not this one; "3 Oct, 09:12"; "Wednesday".
const evidenceDate = (iso, nowMs) => new Date(iso.slice(0, 10) + 'T12:00:00Z').toLocaleDateString('en-GB',
  { day: 'numeric', month: 'short', ...(iso.slice(0, 4) === evidenceISO(nowMs).slice(0, 4) ? {} : { year: 'numeric' }), timeZone: 'UTC' });
const evidenceSince = t => new Date(t).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: EVIDENCE_TZ });   // as Right now's feedTime
const evidenceDayName = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { weekday: 'long', timeZone: 'UTC' });

// How old, in the right-hand column. Under a day, as the answer's issue time says it ("1 h 30 min ago");
// then by the calendar ("Yesterday", "10 days ago", "3 months ago"). A day (an ISO date, the algae
// check's) is counted by the calendar alone.
function evidenceAge(t, nowMs) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return evidenceAgeDays(t, evidenceISO(nowMs));
  const ms = Date.parse(t), m = Math.max(0, Math.round((nowMs - ms) / 60000));
  if (m < 24 * 60) return m < 60 ? `${m} min ago` : m % 60 ? `${Math.floor(m / 60)} h ${m % 60} min ago` : `${m / 60} h ago`;
  return evidenceAgeDays(evidenceISO(ms), evidenceISO(nowMs));
}
// From one UK day to another: whole days under 60, then whole calendar months ("4 months ago" from 20 May to 4 Oct).
function evidenceAgeDays(a, b) {
  const n = evidenceDays(a, b);
  if (n < 60) return n <= 0 ? 'Today' : n === 1 ? 'Yesterday' : `${n} days ago`;
  const [y1, m1, d1] = a.split('-').map(Number), [y2, m2, d2] = b.split('-').map(Number), k = (y2 - y1) * 12 + m2 - m1 - (d2 < d1 ? 1 : 0);
  return `${k} month${k === 1 ? '' : 's'} ago`;
}

// The overflows upstream: discharging and stopped lately, as Right now counts them, then which report
// live and why the others do not, in #98's data states (forecast.live_counts): offline, a feed that is
// down, a feed not updated within six hours (stale), or a company with no live feed. A forecast from
// before no_feed_upstream existed cannot tell an offline monitor from no feed, and says "offline or with no
// live feed" rather than guess.
function evidenceOverflows(d, generatedAt) {
  const total = (d.upstream_summary || {}).overflows || 0;
  if (!total) return null;
  const n = d.now || {}, dis = Math.min(n.discharging_upstream || 0, total), rec = Math.min(n.recent_upstream || 0, total - dis);
  const mon = Math.min(total, n.monitored_upstream ?? total), st = n.stale_upstream || 0, fd = n.feed_down_upstream || 0;
  const nf = Number.isInteger(n.no_feed_upstream) ? n.no_feed_upstream : null;
  const rest = Math.max(0, total - mon - st - fd - (nf || 0));
  const not = [];
  if (rest) not.push(nf === null ? `${rest} offline or with no live feed` : `${rest} offline`);
  if (nf) not.push(`${nf} with no live feed`);
  for (const f of n.feed_down || []) not.push(`${f.overflows} on ${evidenceEsc(f.company)}'s feed, which is down`);
  // `records`: overflows whose own records have stopped updating while the rest of the feed has not.
  // `on_change`: a feed that stamps a record only when it changes, so a quiet spell looks stale (index.html, feedStale).
  for (const f of n.feed_stale || []) not.push(f.records
    ? `${f.overflows} whose records on ${evidenceEsc(f.company)}'s feed ${f.since ? `have not updated since ${evidenceSince(f.since)}` : 'give no update time'}`
    : f.on_change && f.since ? `${f.overflows} on ${evidenceEsc(f.company)}'s feed, where no record has changed since ${evidenceSince(f.since)} (it changes a record only when an overflow's status does)`
    : `${f.overflows} on ${evidenceEsc(f.company)}'s feed, ${f.since ? `not updated since ${evidenceSince(f.since)}` : 'which gives no update time'}`);
  const live = mon >= total ? (total === 1 ? 'It reports live.' : `All ${total} report live.`)
    : `${mon || 'None'} of ${total} report live.${not.length ? ` Not reporting: ${not.join('; ')}.` : ''}`;
  // Never "0 of 14 discharging" where none of the 14 reports (11 Oct 2026, Hereford): out of all of them
  // only where all report; where some do not, the count alone, beside how many report; with none, not known.
  const count = !mon && !dis ? 'Whether any is discharging is not known' : mon >= total ? `${dis} of ${total} discharging` : `${dis} discharging`;
  return { what: 'Overflows upstream', at: generatedAt,
    say: `${count}${rec ? `, ${rec} stopped lately` : ''}. ${live}`,
    src: "The water companies' live feeds" };
}

// The rain in the 48 h to midday on the first day, and the most ahead, from the rainfall forecast read
// with the forecast; a day with no rain figure is named among the gaps. Every figure is a 48 h total to
// midday: until 12 Oct 2026 the most ahead read "The wettest day ahead is Tuesday, with 7 mm", as if it
// were that day's rain (red-team review, 11 Oct).
function evidenceRain(d, nowMs, generatedAt) {
  const days = (d.days || []).slice(0, 5), x0 = days[0];
  if (!x0 || evidenceNil(x0.rain_48h_mm)) return null;
  const v = x0.rain_48h_mm, amount = v === 0 ? 'No rain' : v < 0.5 ? 'Under 1&nbsp;mm of rain' : `${Math.round(v)}&nbsp;mm of rain`;
  const wet = days.slice(1).filter(x => !evidenceNil(x.rain_48h_mm) && x.rain_48h_mm >= 1 && x.rain_48h_mm > v)
    .reduce((a, b) => !a || b.rain_48h_mm > a.rain_48h_mm ? b : a, null);
  const when = x0.date === evidenceISO(nowMs) ? 'today' : evidenceDayName(x0.date);
  return { what: 'Rain here', at: generatedAt,
    say: `${amount} in the 48&nbsp;h to midday ${when}.${wet ? ` The most ahead is ${Math.round(wet.rain_48h_mm)}&nbsp;mm in the 48&nbsp;h to midday ${evidenceDayName(wet.date)}.` : ''}`,
    src: `<a href="https://open-meteo.com/">Open-Meteo.com</a>'s forecast` };
}

// The latest lab sample in one sentence, the panel's and the Compare table's (experience.js): the count,
// the day it was taken, and whether the count is over 900 E. coli per 100 ml, the line the site's E. coli
// estimate is about ("a water sample would show E. coli over 900 per 100 ml"). A fact about the number,
// not advice: 900 is the inland "sufficient" standard's (Bathing Water Regulations 2013, schedule 5, on a
// 90-percentile evaluation of the samples over four seasons), so one sample sets no rating. On the page
// the comparison links to the About section's E. coli entry, which says so. A count given as a limit
// ("<10", ">10000") is compared only where the limit settles it. Empty without a usable sample.
function evidenceSample(s, nowMs, html = false) {
  if (!s || !s.taken_at || evidenceNil(s.ecoli) || s.ecoli === '' || !Number.isFinite(Number(s.ecoli))) return '';
  const n = Math.round(Number(s.ecoli)), k = n.toLocaleString('en-GB'), q = s.qualifier, sp = html ? '&nbsp;' : ' ';
  const count = q === '<' ? `Under ${k}` : q === '>' ? `Over ${k}` : k;
  const cmp = q === '<' ? (n <= 900 ? 'under 900' : '') : q === '>' ? (n >= 900 ? 'over 900' : '')
    : n > 900 ? 'over 900' : n === 900 ? 'not over 900' : 'under 900';
  return `${count} E.${sp}coli per 100${sp}ml, taken ${evidenceDate(s.taken_at, nowMs)}`
    + (cmp ? `: ${html ? `<a href="#about-ecoli">${cmp}</a>` : cmp}` : '') + '.';
}

// Runoff from farms, which the forecast does not model at a particular spot, where the Environment Agency
// lists it on the spot's water body: agriculture and rural land management as a confirmed or probable
// reason the water body does not reach good status, under "Pollution from rural areas", in the Catchment
// Data Explorer (build_site.attach_water_body, from data/raw/rnags.json). The Agency's words and its
// certainty, and a link to its page for the water body. A fact about the river, not about today's water:
// the reasons are for its ecological and chemical status (plants, algae, fish, phosphate), not bacteria.
// `said`: the no-overflow gap above already says farms are not modelled. Empty where nothing is listed.
function evidenceRunoff(d, said = false) {
  const w = d.water_body || {}, how = w.agriculture;
  if (!/^GB[0-9A-Z]+$/.test(w.id || '') || !['confirmed', 'probable'].includes(how)) return '';
  const where = d.kind === 'lake' ? 'this lake' : 'this stretch of river';
  return `${said ? '' : 'Runoff from farms here is not modelled. '}The <a href="https://environment.data.gov.uk/catchment-planning/WaterBody/${w.id}">Environment Agency</a> `
    + `lists agriculture and rural land management as a ${how} reason ${where} does not reach good status.`;
}

// The rows and the gaps, for a spot of the list (not a point clicked on the map, nor one without a
// forecast, whose answer says why). Each row: what, how old (age), what it says (say), whose (src).
function evidenceItems(d, nowMs, generatedAt) {
  const rows = [], gaps = [], cl = d.classification || null, designated = d.source === 'designated' || !!cl;
  const ea = cl && /^https:\/\//.test(cl.url || '') ? `<a href="${evidenceEsc(cl.url)}">Environment Agency</a>` : 'Environment Agency';
  const ov = evidenceOverflows(d, generatedAt);
  if (ov) rows.push(ov);
  else gaps.push(`No monitored overflow within ${(d.assumptions || {}).max_upstream_km ?? 60}&nbsp;km upstream, so no spills to go on; farms, wildlife and unmonitored sources are not modelled.`);
  const runoff = evidenceRunoff(d, !ov);
  if (runoff) gaps.push(runoff);
  const rain = evidenceRain(d, nowMs, generatedAt);
  if (rain) rows.push(rain);
  const dry = (d.days || []).slice(0, 5).filter(x => evidenceNil(x.rain_48h_mm)).map(x => x.date === evidenceISO(nowMs) ? 'today' : evidenceDayName(x.date));
  if (dry.length) gaps.push(`No rain forecast arrived for ${dry.length > 1 ? dry.slice(0, -1).join(', ') + ' or ' + dry[dry.length - 1] : dry[0]}.`);
  if (cl && cl.class) rows.push({ what: 'Environment Agency rating', age: String(cl.year ?? ''),
    say: `${evidenceCap(cl.class)}.`, src: `${ea}, from its lab samples over up to four seasons` });
  else if (cl) gaps.push('No Environment Agency rating yet: this bathing water is too new to have one.');
  const a = d.algae;
  if (a && a.date) rows.push({ what: 'Algae at the last check', at: a.date, say: `${evidenceCap(evidenceEsc(a.phrase))}, ${evidenceDate(a.date, nowMs)}.`,
    src: "The Environment Agency sampler's look, not a lab test" });
  else if (designated) gaps.push('No algae check here this season.');
  // A sample over 900 counts in the level for 14 days (levels.js, sampleLevel): the row says whether it does.
  const s = d.lab_sample, counted = evidenceRules().sampleLevel(d), over = /: (<a [^>]*>)?over 900/.test(evidenceSample(s, nowMs));
  if (evidenceSample(s, nowMs)) rows.push({ what: 'Latest lab sample', at: s.taken_at, src: ea,
    say: evidenceSample(s, nowMs, true) + (counted ? ' It makes the level at least moderate risk.' : over ? ' Over two weeks old, so not counted in the level.' : '') });
  else if (designated && s === null) gaps.push('No lab sample here this season.');
  else if (designated) gaps.push(`The latest lab sample is not in this forecast's data${cl && /^https:\/\//.test(cl.url || '') ? `: <a href="${evidenceEsc(cl.url)}">the Environment Agency's page</a> has it` : ''}.`);
  // The facts only: the line under the five days (check, in index.html) already says why.
  if (!designated) gaps.push('No lab samples, algae checks or rating here.');
  for (const r of rows) if (r.at) r.age = evidenceAge(r.at, nowMs);
  return { rows, gaps };
}

// The tile: a row for each item, its age on the right, as a picked day's rows (factorRow in index.html),
// then the gaps under a hairline, a line each. Folded whole, as the day-by-day numbers are: its figures
// are on the tiles above it, so the page's "why" part stays short until a reader asks for the sources.
function evidenceTile(d, nowMs, generatedAt) {
  if (!d || d.unlisted || d.error) return '';
  const { rows, gaps } = evidenceItems(d, nowMs, generatedAt);
  if (!rows.length && !gaps.length) return '';
  return `<details class="tile fold" id="evidence"><summary><span class="t-lab" id="evidence-h">${evidenceIcon()}<span>What the level rests on</span></span></summary>`
    + (rows.length ? `<div class="factors">${rows.map(r => `<div class="factor"><div class="f-l">${r.what}</div><div class="f-v">${r.age}</div>`
      + `<div class="f-d">${r.say}</div><div class="f-src">${r.src}.</div></div>`).join('')}</div>` : '')
    + (gaps.length ? `<div class="ev-gap">${gaps.map(g => `<p>${g}</p>`).join('')}</div>` : '') + '</details>';
}

// How much evidence sits behind a level, as one quiet line beside it (outside review, 20 Oct 2026: show the
// pollution signals and the evidence coverage as two things). Plan a swim gives it under each row. Two parts,
// each only where it applies:
//  - live: on a plan for today, a low level whose right now is not known (levels.js, nowUnknown) is a forecast
//    only, in the words a saved card uses;
//  - the track record: whose overflows these are, by their reach (evidenceCompanies), and the share of spills
//    the live warnings caught there, from the Accuracy page's own figures (verification.json,
//    live.warning_table: by_company and trained_on), the share linking to its table. The spill model learned
//    from one company's spills, United Utilities'. On 20 Oct 2026 its warnings had caught 37% of United
//    Utilities' spills and 2% of the other companies', so the line says which side of that the spot is on. A
//    share is of forecasts, as on the Accuracy page: each spill was forecast up to five times, from four days
//    ahead to that morning.
// Short, since every row in a place says much the same: the counts are a tap away. A spot with no daily
// forecast (a plain level, a failed forecast) has no track record to give. W is the warning table, or null
// while it loads or when it failed; the live part does not need it. Returns HTML, or ''.
const EVIDENCE_VERIFICATION = 'data/verification.json';
const evidencePct = p => p > 0 && p < 0.005 ? 'under 1%' : Math.round(p * 100) + '%';   // as the decision record's
const evidenceOwners = names => names.map(n => `${evidenceEsc(evidenceRules().companyName(n))}'`.replace(/([^s])'$/, "$1's")).join(' and ');   // "Yorkshire Water's", "United Utilities'", "Dŵr Cymru Welsh Water's"
// Whose overflows a spot's are, by reach: company -> weight. From the contributors where the spot has them
// (spots.json, a spot's own file), or from the lite file's reach_by_company (build_site.py), which the list
// and the planner load in their place.
function evidenceCompanies(s) {
  const by = new Map();
  if (s.contributors) for (const c of s.contributors) by.set(c.company || 'unknown', (by.get(c.company || 'unknown') || 0) + (Number(c.weight) || 0));
  else for (const [n, w] of s.reach_by_company || []) by.set(n, Number(w) || 0);
  return by;
}
function evidenceCoverage(s, W, isToday = false) {
  const R = evidenceRules(), out = [];
  if (!s || s.unlisted || s.error || !R.daily(s)) return '';
  if (isToday && R.nowUnknown(s)) out.push(`Forecast only: ${R.nowUnknownWhy(s)}.`);
  const by = evidenceCompanies(s), total = [...by.values()].reduce((a, b) => a + b, 0), own = W && W.trained_on;
  if (own && total > 0 && W.first_day) {
    const since = evidenceDate(W.first_day, Date.parse(W.last_day || W.first_day)), mine = (by.get(own) || 0) >= total / 2;
    const rows = (W.by_company || []).filter(r => (r.company === own) === mine);
    const hits = rows.reduce((a, r) => a + (r.hits || 0), 0), made = rows.reduce((a, r) => a + (r.hits || 0) + (r.misses || 0), 0);
    // Whose: the company the model learned from alone, or the others holding most of the reach, at most two,
    // each with a quarter of it or more. "Mostly" when those named hold under nine tenths of it.
    const named = mine ? [[own, by.get(own)]] : [...by].filter(([n, w]) => n !== 'unknown' && n !== own && w >= total / 4).sort((a, b) => b[1] - a[1]).slice(0, 2);
    const whose = named.length ? `${named.reduce((a, [, w]) => a + w, 0) < 0.9 * total ? 'Mostly ' : ''}${evidenceOwners(named.map(([n]) => n))} overflows` : '';
    const share = `<a href="verification.html#warnings">${evidencePct(made ? hits / made : 0)} of ${mine ? 'their' : 'other companies\''} spills</a>`;
    if (made && mine) out.push(`${evidenceCap(whose)}, whose spills the model learned from. Since ${since} it has warned of ${share}.`);
    else if (made) out.push(`${whose ? whose + '. ' : ''}The model learned from ${evidenceOwners([own])}; since ${since} it has warned of ${share}.`);
  }
  return out.join(' ');
}
// The warning table, once a visit: a promise of it, or of null when it could not be had.
let EVIDENCE_WARNINGS = null;
const evidenceWarnings = () => EVIDENCE_WARNINGS || (EVIDENCE_WARNINGS = fetch(EVIDENCE_VERIFICATION, { cache: 'no-cache' })
  .then(r => (r.ok ? r.json() : null)).then(v => ((v || {}).live || {}).warning_table || null).catch(() => null));

if (typeof module === 'object' && module.exports) {
  module.exports = { evidenceTile, evidenceItems, evidenceAge, evidenceOverflows, evidenceRain, evidenceSample, evidenceRunoff, evidenceCoverage, evidenceCompanies };
}
