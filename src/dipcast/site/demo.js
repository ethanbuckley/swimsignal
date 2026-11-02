// The organisers' demonstration (demo.html): one worked example of what SwimSignal already gives a club, an
// activity centre or an event organiser, drawn from the live forecast on four real bathing waters on Windermere.
// The centre is invented and the page says so; no organisation uses or pays for any of this
// (docs/ORGANISER-INTERVIEWS-2026-11.md). The page's prose is static; this file fills five parts of it:
//  - #d-session: the session, on the next Saturday in the forecast's five days, else tomorrow;
//  - #d-brief: the session briefing in scripts/briefing.py's words (LIMITS, DECIDES, a line a spot);
//  - #d-sites: the sites view for the four spots on the session's day (sites.js, view);
//  - #d-since: what changed at each spot since the previous update (since.js, lastParts, from
//    data/since-last.json, the file a spot's page reads);
//  - #d-kept: the issue id that a kept copy is filed under (printed.js), and the links to each tool.
// The words for a level are the site's own (levels.js through sites.js, dayWords), so the demonstration never
// disagrees with a spot's page, the sites view or the decision record.
//
// A plain script, as sites.js: the page loads levels.js, experience.js, lists.js, organisers.js, printed.js,
// eatoday.js, since.js and sites.js first, and this file finds their names there; Node requires them for the tests
// (tests/site_demo.test.cjs). Nothing is stored or sent.
const Demo = (() => {
  const node = typeof module === 'object' && module.exports;
  const R = node ? require('./levels.js') : { setToday, today, COVER, NO_OVERFLOWS, NO_RIVER };   // levels.js's globals
  const S = node ? require('./sites.js') : Sites;
  const P = node ? require('./printed.js') : Printed;
  const N = node ? require('./since.js') : { lastParts, seenRecord };
  const Li = node ? require('./lists.js') : { sitesHash };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const long = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });

  // The example: an invented activity centre's session on Windermere, a main launch point and three to fall back on.
  // The Lake District is the area the winter plan chose to focus on (25 Oct 2026), and centres that run sessions every
  // week are the first group to interview. Real spots, all EA bathing waters, so the levels are the live forecast's and
  // the EA's advice shows; an id the forecast no longer has is named as not found (sites.js, view).
  const ORG = 'Example centre (invented for this demonstration)';
  const SESSION = { time: '10:00', lead: "the centre's duty instructor" };
  const VENUES = [
    { id: 'bw-ukd1203-45650', role: 'main' },     // Windermere, Millerground Landing
    { id: 'bw-ukd1203-45675', role: 'backup' },   // Windermere, Rayrigg Meadow
    { id: 'bw-ukd1203-45700', role: 'backup' },   // Windermere, Fellfoot
    { id: 'bw-ukd1203-45625', role: 'backup' },   // Windermere, Lakeside YMCA
  ];
  // scripts/briefing.py, LIMITS and DECIDES, word for word (tests/site_demo.test.cjs checks they still are).
  const LIMITS = "This is SwimSignal's pollution risk forecast for your planned session. It is one input to your own "
    + 'risk assessment. It is a forecast, not a water test: nothing was sampled at the water for it. It never '
    + 'says the water is safe or clean, and no level means that. It counts sewage from the monitored storm '
    + 'overflows upstream and the rain that makes them spill. It does not cover algae, leptospirosis (Weil\'s '
    + 'disease), runoff from farms and roads, outfalls no one monitors, or physical dangers. Missing data '
    + 'never means low risk: treat it as unknown.';
  const DECIDES = '{org} makes the decision about this session, beside its own checks at the water, lab tests, the '
    + "Environment Agency's advice and the water companies' own spill alerts. SwimSignal does not make it.";

  // The session's day: the first Saturday among the main spot's five days, else the second day (tomorrow), else the
  // first. Null where the forecast has no days for it.
  function sessionDay(data) {
    const main = (data.spots || []).find(s => s.id === VENUES[0].id) || (data.spots || [])[0];
    const days = ((main && main.days) || []).slice(0, 5).map(x => x.date);
    if (!days.length) return null;
    return days.find(iso => new Date(iso + 'T12:00:00').getDay() === 6) || days[1] || days[0];
  }

  const recordHref = (id, iso) => `record.html#spot=${encodeURIComponent(id)}&day=${iso}&org=${encodeURIComponent(ORG)}`;
  const sitesHref = iso => `sites.html${Li.sitesHash(`Example centre, ${iso}`, VENUES.map(v => v.id))}&day=${iso}`;
  const organisersHref = (id, iso) => `organisers.html#spot=${encodeURIComponent(id)}&date=${iso}`;

  // The briefing, as briefing.py's email gives it: the limits, who decides, the session, then a line a spot.
  function briefing(data, iso) {
    const by = new Map((data.spots || []).map(s => [s.id, s]));
    const spot = v => { const s = by.get(v.id), role = v.role === 'main' ? 'Main spot' : 'Backup spot';
      if (!s) return `<li><b>${role}:</b> ${esc(v.id)} is not in this forecast.</li>`;
      const w = S.dayWords(s, iso);
      return `<li><b>${role}, ${esc(s.name)}:</b> <span class="d-lv ${esc(w.tone)}">${esc(w.head)}.</span> ${esc(w.why)}`
        + ` <a href="${esc(recordHref(s.id, iso))}">Decision record</a></li>`; };
    return `<div class="d-brief"><p class="d-subject">SwimSignal briefing for ${esc(ORG)}: ${esc(long(iso))}, ${SESSION.time}</p>`
      + `<p>${esc(LIMITS)}</p><p>${esc(DECIDES.replace('{org}', ORG))}</p>`
      + `<p>Session: ${esc(long(iso))}, ${SESSION.time} (UK time). Decision by: ${SESSION.lead}.</p>`
      + `<ul class="d-spots">${VENUES.map(spot).join('')}</ul>`
      + `<p>Issue id <b>${esc(P.issueId(data))}</b>. Quote it to have this briefing found again, as it was sent.</p></div>`;
  }

  // What changed at each spot since the previous update, in the spot page's words (since.js, lastParts). The file
  // must be for this issue: one for another (a deploy half done) is not compared with, and the page says so.
  function since(data, file, now = Date.now()) {
    if (!file) return '<p>The comparison with the previous update could not be loaded, so nothing is said about what changed.</p>';
    if (file.issued_at !== data.generated_at) return '<p>The comparison file is from a different update than the forecast on this page, so nothing is compared. Reload the page in a few minutes.</p>';
    const by = new Map((data.spots || []).map(s => [s.id, s]));
    const items = VENUES.map(v => {
      const s = by.get(v.id); if (!s) return '';
      const x = N.lastParts(file, (file.spots || {})[s.id] || null, N.seenRecord(s, data.generated_at, now));
      if (!x) return '';
      return `<li><b>${esc(s.name)}.</b> ${esc(x.head)}${x.days.map(d => ` ${d.day ? `${esc(d.day)}: ` : ''}${esc(d.text)}`).join('')}</li>`;
    }).filter(Boolean);
    return items.length ? `<ul class="d-since">${items.join('')}</ul>` : '<p>No spot of the four has a comparison in this update.</p>';
  }

  // The issue id and the tools for the main spot on the day.
  function kept(data, iso) {
    const id = VENUES[0].id;
    return `<p>This forecast's issue id is <b>${esc(P.issueId(data))}</b>: the build's commit, then the issue time in UTC to the minute. `
      + 'Every decision record and sites view printed from this update carries it.</p>'
      + `<ul><li><a href="${esc(recordHref(id, iso))}">The decision record for the main spot on ${esc(long(iso))}</a>, prepared for the example centre</li>`
      + `<li><a href="${esc(sitesHref(iso))}">The sites view as its own page</a>, to bookmark and print</li>`
      + `<li><a href="${esc(organisersHref(id, iso))}">The organisers' page for the main spot on that day</a>: the overflows upstream as a table and a CSV file, a calendar file and the checklist</li></ul>`;
  }

  // The whole demonstration from one forecast (data: spots-lite.json) and the comparison file (null if it failed).
  function draw(data, file, now = Date.now(), base = '') {
    R.setToday(String(data.generated_at).slice(0, 10));
    const iso = sessionDay(data);
    if (!iso) return null;
    return {
      session: `<p>${esc(ORG)} runs an open water session on <b>${esc(long(iso))}</b> at ${SESSION.time}. The main launch point is Millerground Landing on Windermere. `
        + 'If it looks wrong, the session moves to Rayrigg Meadow, Fellfoot or Lakeside YMCA on the same lake, or does not go on the water. '
        + `The decision is made by ${SESSION.lead}, the evening before and again on the morning.</p>`,
      brief: briefing(data, iso),
      sites: S.view(data, { ids: VENUES.map(v => v.id), name: '', day: iso }, now, base, { print: false }),
      since: since(data, file, now),
      kept: kept(data, iso),
    };
  }

  async function start() {
    const parts = ['session', 'brief', 'sites', 'since', 'kept'].map(k => [k, document.getElementById('d-' + k)]);
    const base = new URL('./', location.href).href;
    let data;
    try {
      const res = await fetch('data/spots-lite.json', { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (e) {
      for (const [, el] of parts) if (el) el.innerHTML = '<p class="notice">The forecast could not be loaded, so this part of the example is empty. Try again later. No level is shown rather than an old one.</p>';
      return;
    }
    const file = await fetch('data/since-last.json', { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
    const out = draw(data, file, Date.now(), base);
    for (const [k, el] of parts) if (el) el.innerHTML = out ? out[k] : '<p class="notice">The forecast has no days in it, so there is nothing to show.</p>';
  }

  return { ORG, VENUES, LIMITS, DECIDES, sessionDay, briefing, since, kept, draw, recordHref, sitesHref, start };
})();

if (typeof module === 'object' && module.exports) module.exports = Demo;
else if (document.getElementById('d-brief')) Demo.start();
