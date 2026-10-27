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
// It reads only the forecast the page has loaded (spots-lite.json): no request, nothing stored.
//
// A plain script, as since.js: globals in the page (each begins fw or FW), exports in Node
// (tests/site_find_window.test.cjs).

const fwRules = () => typeof dayLevel === 'function' ? { daily, dayLevel, ORDER }
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
const fwDay = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });

// One spot over the days given (the five, in order, each the next day of the one before): its Low ranges
// [{from, to, n}] and the days with no level at all.
function fwFind(s, dates) {
  const R = fwRules();
  if (!R.daily(s)) return { daily: false, ranges: [], unknown: [] };
  const ranges = [];
  const unknown = [];
  let run = null;
  for (const iso of dates) {
    const l = R.dayLevel(s, iso);
    if (R.ORDER[l] === undefined) unknown.push(iso);
    if (l !== 'low') { run = null; continue; }
    if (run) { run.to = iso; run.n += 1; } else ranges.push(run = { from: iso, to: iso, n: 1 });
  }
  return { daily: true, ranges, unknown };
}

// A range in words: "Tue 28 Oct", or "Tue 28 Oct to Thu 30 Oct".
const fwRange = r => r.n === 1 ? fwDay(r.from) : `${fwDay(r.from)} to ${fwDay(r.to)}`;
const fwList = xs => xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`;
// The sentences for one spot, plain text: the window, then what was left out and why.
function fwWords(f) {
  if (!f.daily) return ['This spot has no day-by-day pollution forecast, so there is no window to find here.'];
  const out = [f.ranges.length ? `Low risk: ${fwList(f.ranges.map(fwRange))}.` : 'No day in the next five is at low risk here.'];
  if (f.unknown.length) out.push(`No forecast for ${fwList(f.unknown.map(fwDay))}.`);
  return out;
}

// The tile: one row a spot, in the order given. href(s) is the spot's address on the page.
function fwSection(spots, dates, href) {
  if (!spots.length || !dates.length) return '';
  const tag = fwTag();
  const rows = spots.map(s => {
    const notice = tag(s, 'p');
    return `<li><a href="${fwEsc(href(s))}" data-id="${fwEsc(s.id)}" class="fw-nm">${fwEsc(s.name)}</a>`
      + (notice ? `${notice}<p class="fw-apart">${fwApart(s)}</p>` : '')
      + fwWords(fwFind(s, dates)).map((t, i) => `<p class="${i ? 'fw-note' : 'fw-low'}">${fwEsc(t)}</p>`).join('') + '</li>';
  }).join('');
  return '<section class="sec tile fw" aria-labelledby="fw-h"><h2 class="sec-h" id="fw-h">Find a window</h2>'
    + '<p class="sub">For each spot, the days in the next five when SwimSignal\'s pollution forecast is low risk, with days in a row as one range. '
    + 'Each day is taken on its own, so a later day may be higher. One level covers a whole day, not an hour. '
    + 'Low risk is not a safety check: currents, cold water and the signs at the water still apply.</p>'
    + `<ul class="fw-list">${rows}</ul></section>`;
}

if (typeof module === 'object' && module.exports) {
  module.exports = { fwFind, fwWords, fwRange, fwDay, fwApart, fwSection };
}
