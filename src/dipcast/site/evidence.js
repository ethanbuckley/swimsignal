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
  for (const f of n.feed_stale || []) not.push(`${f.overflows} on ${evidenceEsc(f.company)}'s feed, ${f.since ? `not updated since ${evidenceSince(f.since)}` : 'which gives no update time'}`);
  const live = mon >= total ? (total === 1 ? 'It reports live.' : `All ${total} report live.`)
    : `${mon || 'None'} of ${total} report live.${not.length ? ` Not reporting: ${not.join('; ')}.` : ''}`;
  return { what: 'Overflows upstream', at: generatedAt,
    say: `${dis} of ${total} discharging${rec ? `, ${rec} stopped lately` : ''}. ${live}`,
    src: "The water companies' live feeds" };
}

// The rain in the 48 h to midday on the first day, and the wettest day ahead, from the rainfall forecast
// read with the forecast; a day with no rain figure is named among the gaps.
function evidenceRain(d, nowMs, generatedAt) {
  const days = (d.days || []).slice(0, 5), x0 = days[0];
  if (!x0 || evidenceNil(x0.rain_48h_mm)) return null;
  const v = x0.rain_48h_mm, amount = v === 0 ? 'No rain' : v < 0.5 ? 'Under 1&nbsp;mm of rain' : `${Math.round(v)}&nbsp;mm of rain`;
  const wet = days.slice(1).filter(x => !evidenceNil(x.rain_48h_mm) && x.rain_48h_mm >= 1 && x.rain_48h_mm > v)
    .reduce((a, b) => !a || b.rain_48h_mm > a.rain_48h_mm ? b : a, null);
  const when = x0.date === evidenceISO(nowMs) ? 'today' : evidenceDayName(x0.date);
  return { what: 'Rain here', at: generatedAt,
    say: `${amount} in the 48&nbsp;h to midday ${when}.${wet ? ` The wettest day ahead is ${evidenceDayName(wet.date)}, with ${Math.round(wet.rain_48h_mm)}&nbsp;mm.` : ''}`,
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

// The rows and the gaps, for a spot of the list (not a point clicked on the map, nor one without a
// forecast, whose answer says why). Each row: what, how old (age), what it says (say), whose (src).
function evidenceItems(d, nowMs, generatedAt) {
  const rows = [], gaps = [], cl = d.classification || null, designated = d.source === 'designated' || !!cl;
  const ea = cl && /^https:\/\//.test(cl.url || '') ? `<a href="${evidenceEsc(cl.url)}">Environment Agency</a>` : 'Environment Agency';
  const ov = evidenceOverflows(d, generatedAt);
  if (ov) rows.push(ov);
  else gaps.push(`No monitored overflow within ${(d.assumptions || {}).max_upstream_km ?? 60}&nbsp;km upstream, so no spills to go on; farms, wildlife and unmonitored sources are not modelled.`);
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
  const s = d.lab_sample;
  if (evidenceSample(s, nowMs)) rows.push({ what: 'Latest lab sample', at: s.taken_at, say: evidenceSample(s, nowMs, true), src: ea });
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

if (typeof module === 'object' && module.exports) {
  module.exports = { evidenceTile, evidenceItems, evidenceAge, evidenceOverflows, evidenceRain, evidenceSample };
}
