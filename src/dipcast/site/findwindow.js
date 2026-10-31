// Find a window (Saved, a prototype): for each saved spot, the days of the next five whose SwimSignal pollution
// forecast, as the page shows it for that day (levels.js, dayLevel), is Low, a run of adjacent such days said as
// one range. The rules, chosen 28 Oct 2026 to be conservative:
//  - A day counts when its own displayed level is Low. Each day is taken on its own: a Low day counts even when a
//    later one is higher, and the line says that a later day may be.
//  - Today is as its day level shows it, which already takes in spills right now (levels.js, risk raises today by
//    them), so a Low today beside raised spills right now is not Low and is no window.
//  - A spot without a day-by-day forecast (no monitored overflow upstream, a standing rating, a failed forecast)
//    has no window, said so; its standing level is never Low (levels.js, level), and is not a forecast for a day.
//  - Days, never hours: one level covers a whole day. Low is not a safety check, and the tile says so.
//  - No ranking and no "best": the spots stay in the list's order. An official notice (eatoday.js, eaTodayTag) is
//    shown under the spot's name, on a line of its own and said to be no part of these levels: "official advice …
//    follow it first" where its reviewer marked it as restricting swimming (eaTodayRestricts), else "official notice
//    … read it first". A spot without one is never said to be safer or better for that.
//  - Reasons, not a score: each day that is not low risk is named with the page's own headline for it
//    (levels.js, dayHeadline: "Moderate risk: sewage spills"), days in a row with the same headline as one range.
// Two places use it: Saved, for your spots in the list's order; and Plan a swim, for the plan's spots, its area (where
// it starts and how far) and its activity (the kind chip: rivers, lakes, bathing waters), nearest first by distance,
// never by level (fwPlanSection).
// It reads only the forecast the page has loaded (spots-lite.json): no request, nothing stored.
//
// A plain script, as since.js: globals in the page (each begins fw or FW), exports in Node
// (tests/site_find_window.test.cjs).

const fwRules = () => typeof dayLevel === 'function' ? { daily, dayLevel, dayHeadline, ORDER }
  : require('./levels.js');
const fwTag = () => typeof eaTodayTag === 'function' ? eaTodayTag
  : typeof require === 'function' ? require('./eatoday.js').eaTodayTag : () => '';
const fwRestricts = () => typeof eaTodayRestricts === 'function' ? eaTodayRestricts
  : typeof require === 'function' ? require('./eatoday.js').eaTodayRestricts : () => false;
// Under a notice's tag: what it is to the levels, and what to do, by its kind.
const fwApart = s => fwRestricts()(s) ? 'The official advice is not part of these levels: follow it first.'
  : 'The official notice is not part of these levels: read it first.';
const fwEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
// "Tue 28 Oct", in the reader's calendar, whatever their clock's time of day.
const fwNext = iso => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10); };
const fwDay = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });

// One spot over the days given (the five, in order, each the next day of the one before): its Low ranges
// [{from, to, n}], the days with no level at all, and the other days with the page's headline for each.
function fwFind(s, dates) {
  const R = fwRules();
  if (!R.daily(s)) return { daily: false, ranges: [], unknown: [], not: [] };
  const ranges = [];
  const unknown = [], not = [];
  let run = null;
  for (const iso of dates) {
    const l = R.dayLevel(s, iso);
    if (R.ORDER[l] === undefined) unknown.push(iso);
    else if (l !== 'low') not.push({ date: iso, words: R.dayHeadline(s, iso) });
    if (l !== 'low') { run = null; continue; }
    if (run) { run.to = iso; run.n += 1; } else ranges.push(run = { from: iso, to: iso, n: 1 });
  }
  return { daily: true, ranges, unknown, not };
}

// A range in words: "Tue 28 Oct", or "Tue 28 Oct to Thu 30 Oct".
const fwRange = r => r.n === 1 ? fwDay(r.from) : `${fwDay(r.from)} to ${fwDay(r.to)}`;
const fwList = xs => xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`;
// The sentences for one spot, plain text: the window, then what was left out and why.
function fwWords(f) {
  if (!f.daily) return ['This spot has no day-by-day pollution forecast, so there is no window to find here.'];
  const out = [f.ranges.length ? `Low risk: ${fwList(f.ranges.map(fwRange))}.` : 'No day in the next five is at low risk here.'];
  if (f.not && f.not.length) {
    // Days in a row with the same headline as one range: "Thu 30 Oct to Fri 31 Oct, Moderate risk: sewage spills".
    const runs = [];
    for (const x of f.not) { const last = runs[runs.length - 1];
      if (last && last.words === x.words && fwNext(last.to) === x.date) last.to = x.date; else runs.push({ from: x.date, to: x.date, words: x.words }); }
    out.push(`Other days: ${runs.map(r => `${r.from === r.to ? fwDay(r.from) : `${fwDay(r.from)} to ${fwDay(r.to)}`}, ${r.words}`).join('; ')}.`);
  }
  if (f.unknown.length) out.push(`No forecast for ${fwList(f.unknown.map(fwDay))}.`);
  return out;
}

// One row a spot, in the order given. href(s) is the spot's address on the page; meta(s), if given, a short line
// under the name (the plan's distance and kind).
function fwRows(spots, dates, href, meta = null) {
  const tag = fwTag();
  return spots.map(s => {
    const notice = tag(s, 'p');
    return `<li><a href="${fwEsc(href(s))}" data-id="${fwEsc(s.id)}" class="fw-nm">${fwEsc(s.name)}</a>`
      + (meta ? `<p class="fw-note">${fwEsc(meta(s))}</p>` : '')
      + (notice ? `${notice}<p class="fw-apart">${fwApart(s)}</p>` : '')
      + (fwRestricts()(s) ? '<p class="fw-note">Official advice restricts swimming, so no swimming window is suggested. Follow the advice above.</p><details><summary>Show the separate pollution forecast</summary>' : '')
      + fwWords(fwFind(s, dates)).map((t, i) => `<p class="${i ? 'fw-note' : 'fw-low'}">${fwEsc(t)}</p>`).join('') + (fwRestricts()(s) ? '</details>' : '') + '</li>';
  }).join('');
}
const FW_LIMITS = 'Each day is taken on its own, so a later day may be higher. One level covers a whole day, not an hour. '
  + 'Low risk is not a safety check: currents, cold water and the signs at the water still apply.';
// The tile on Saved: your spots, in the list's order.
function fwSection(spots, dates, href) {
  if (!spots.length || !dates.length) return '';
  const rows = fwRows(spots, dates, href);
  return '<section class="sec tile fw" aria-labelledby="fw-h"><h2 class="sec-h" id="fw-h">Find a window</h2>'
    + '<p class="sub">For each spot, the days in the next five when SwimSignal\'s pollution forecast is low risk, with days in a row as one range. '
    + FW_LIMITS + '</p>'
    + `<ul class="fw-list">${rows}</ul></section>`;
}
// The tile on Plan a swim: the plan's spots (its area and activity), nearest first by straight-line distance and never
// by level, at most FW_PLAN_MAX; the rest are counted. items: [{s, miles}]; what: the plan's words for its spots and
// reach ("river spots within 10 miles of Oxford"); meta(s): the row's distance and kind.
const FW_PLAN_MAX = 12;
function fwPlanSection(items, dates, href, what, meta) {
  if (!items.length || !dates.length) return '';
  const near = [...items].sort((a, b) => a.miles - b.miles || a.s.name.localeCompare(b.s.name)), shown = near.slice(0, FW_PLAN_MAX);
  const more = near.length - shown.length;
  return '<section class="sec tile fw" id="plan-fw" aria-labelledby="plan-fw-h"><h2 class="sec-h" id="plan-fw-h">Find a window</h2>'
    + `<p class="sub">The days in the next five when each of the ${fwEsc(what)} is at low risk, nearest first: an order by distance, not a ranking. `
    + 'Why the other days are not low risk is under each, in the forecast\'s words. ' + FW_LIMITS + '</p>'
    + `<ul class="fw-list">${fwRows(shown.map(o => o.s), dates, href, meta)}</ul>`
    + (more ? `<p class="small muted">And ${more} more further away: see them in the groups above.</p>` : '') + '</section>';
}

if (typeof module === 'object' && module.exports) {
  module.exports = { fwFind, fwWords, fwRange, fwDay, fwApart, fwSection, fwPlanSection, FW_PLAN_MAX };
}
