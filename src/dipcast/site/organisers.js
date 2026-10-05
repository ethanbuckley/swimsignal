// The organisers' page (organisers.html): an event organiser picks a listed spot and the day of the
// event. Within the five days the page gives that day's level, why and how sure, by the site's own
// rules (levels.js, so it never disagrees with the spot's page, the embed or an alert); further ahead
// it says when the forecast for that day first appears and what is known now. Always: the storm
// overflows upstream, from the spot's forecast (contributors and upstream_summary in spots.json, and
// every one of them from data/upstream/<id>.json where there are more), as a table and as a CSV file
// that carries the credits. The checklist and the print layout are in the page.
// Nothing is stored or sent: the spot and the day are after the # in the address.
//
// A plain script, as embed.js: organisers.html loads levels.js first, and this file finds its names
// there; Node requires both for the tests (tests/site_organisers.test.cjs). Everything sits inside
// `Organisers`, so no name here can clash with one of levels.js's.
const Organisers = (() => {
  const R = typeof module === 'object' && module.exports ? require('./levels.js')
    : { ORDER, COVER, NO_FORECAST, NO_OVERFLOWS, NO_RIVER, OTHER_RISKS, setToday, today, rank, risk, level, dayHeadline, daily, ecoliBand, ecoliUntested, poorAdvice };   // levels.js's globals
  const PAGE_ID = /^[A-Za-z0-9_-]+$/;   // the app and build_site.py use the same rule
  const DAYS = 5, AHEAD = DAYS - 1;      // the forecast's days: the day it is issued for and the four after it
  const STALE_MIN = 8 * 60;              // the app's "Stale" notice waits as long (index.html, STALE_MIN)
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const nil = v => v === null || v === undefined;
  const localISO = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return localISO(d); };
  const longDate = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
  const pct = p => p > 0 && p < 0.005 ? 'under 1%' : Math.round(p * 100) + '%';
  const hoursAway = h => h < 1 ? 'under an hour' : `about ${Math.round(h)} h`;
  const ago = m => { const t = Math.max(0, Math.round(m)); return t < 60 ? `${t} min` : t % 60 ? `${Math.floor(t / 60)} h ${t % 60} min` : `${t / 60} h`; };
  // Overflow names that arrive in capitals ("GRASSINGTON/STW") in normal case: index.html's nameCase.
  const nameCase = s => String(s ?? '').replace(/[A-Za-z']+/g, w => /^[A-Z']{4,}$/.test(w) ? w[0] + w.slice(1).toLowerCase() : w);
  const tone = l => l === R.NO_OVERFLOWS ? 'clear' : R.ORDER[l] === undefined ? 'na' : l.replace(' ', '');
  const isolated = s => R.level(s) === R.NO_RIVER;
  const spotHref = id => PAGE_ID.test(id) ? `spot/${id}/` : `./?spot=${encodeURIComponent(id)}`;

  // How many of the overflows upstream are expected to spill on a day, as a clause, and how good a
  // forecast this far ahead has been: index.html's spilling() and howSure(), word for word, so that a
  // day reads here as it does in the spot's own day detail. tests/site_organisers.test.cjs checks
  // that index.html still has the same words.
  const spilling = (x, total) => { const e = x.expected_spilling_overflows; if (nil(e)) return '';
    const k = Math.round(e);
    return k >= total ? (total === 1 ? 'the overflow upstream is expected to spill' : `all ${total} overflows upstream are expected to spill`)
      : k >= 1 ? `about ${k} of the ${total} overflows upstream ${k === 1 ? 'is' : 'are'} expected to spill`
      : R.ORDER[x.label] ? 'a spill from a nearby overflow upstream is possible'
      : `under one spill is expected from the ${total === 1 ? 'overflow' : `${total} overflows`} upstream`; };
  const r5 = x => Math.round(x * 20) * 5 + '%';
  const howSure = (k, j, water) => `In tests on past years, spill forecasts this far ahead were about ${r5(k.spill[j])} as good as same-day ones`
    + (water ? `, and water-quality ones about ${r5(k.water[j])}` : '') + '.';
  // An overflow's chance of a spill on day j, and the three most likely to affect the spot that day
  // (chance times reach), as index.html's dayOverflows() picks them.
  const spillOn = (c, j) => c.p_spill_days ? c.p_spill_days[j] : j === 0 ? c.p_spill_today : j === 1 ? c.p_spill_tomorrow : undefined;
  const topOn = (s, j) => (s.contributors || []).map(c => [c, spillOn(c, j)]).filter(([c, p]) => !nil(p) && c.weight * p >= 0.001)
    .sort((a, b) => b[0].weight * b[1] - a[0].weight * a[1]).slice(0, 3);

  // ------------------------------------------------------------------ the event day
  // Where the day (iso) falls against the forecast: 'past', 'in' one of its five days (x, the day's
  // forecast, null for a spot that has none; j, days ahead), or 'later', with the day its forecast
  // first appears.
  function when(s, iso) {
    const t = R.today();
    if (iso < t) return { state: 'past' };
    if (iso > addDays(t, AHEAD)) return { state: 'later', from: addDays(iso, -AHEAD) };
    const days = (s.days || []).slice(0, DAYS), x = days.find(d => d.date === iso) || null;
    return { state: 'in', x, j: x ? days.indexOf(x) : Math.round((Date.parse(iso) - Date.parse(t)) / 864e5) };
  }
  const row = (label, body) => body ? `<dt>${label}</dt><dd>${body}</dd>` : '';
  // The Environment Agency's rating, on the event day: advice against bathing is named as levels.js
  // words it for that day (poorAdvice), in or out of the bathing season.
  function rating(s, iso) {
    const cl = s.classification; if (!cl) return s.source === 'designated' ? '' : row('Bathing water', 'Not a designated bathing water, so the Environment Agency does not test it for bathing.');
    const page = cl.url ? ` <a href="${esc(cl.url)}">The Environment Agency's page</a> has its samples and any advice against bathing after pollution or algae, which SwimSignal does not include.` : '';
    if (!cl.class) return row('Environment Agency rating', `A designated bathing water too new to have a rating.${page}`);
    const c = String(cl.class).toLowerCase();
    return row(`Environment Agency rating, ${esc(cl.year)}`, `${c === 'poor' ? R.poorAdvice(iso) : `${cap(c)}, from its samples over up to four seasons.`}${page}`);
  }
  // A day inside the forecast: the level with "risk" and what set it (levels.js, dayHeadline), then
  // the rows of the spot's day detail: the spills, the water, the rain, how far ahead, the rating.
  function within(s, iso, w, data) {
    const total = (s.upstream_summary || {}).overflows || 0, x = w.x, head = R.dayHeadline(s, iso);
    const lv = !R.daily(s) ? R.level(s) : x ? R.risk(s, x).level : null;
    let h = `<p class="ev-level ${tone(lv)}">${esc(head)}</p>`;
    if (lv === R.NO_OVERFLOWS || lv === R.NO_RIVER) h += `<p class="ev-say">${esc(R.OTHER_RISKS)}</p>`;
    const rows = [];
    if (R.daily(s) && x) {
      if (nil(x.risk)) rows.push(row('Sewage spills upstream', 'The rainfall forecast for this day has not arrived, so there is no figure.'));
      else { const i = x.risk * 100, top = topOn(s, w.j);
        rows.push(row('Sewage spills upstream', `${cap(x.label)} risk: ${spilling(x, total)}. Exposure index <b>${i > 0 && i < 0.5 ? 'under 1' : Math.round(i)}</b> of 100, after travel time, die-off and dilution.`
          + (top.length ? ` Most likely to reach the spot: ${top.map(([c, p]) => `${esc(nameCase(c.site_name ?? c.site_id))} (spill chance ${pct(p)}, reach ${pct(c.weight)})`).join('; ')}.` : ''))); }
      const band = R.ecoliBand(s, x);
      if (band) rows.push(row('Water quality', `Chance a water sample would show E. coli over 900 per 100 ml: <b>${Math.round(x.p_ecoli_gt900 * 100)}%</b>.`
        + (R.ecoliUntested(x) ? ' Untested from October to April, when the Environment Agency takes no samples, so it does not set the level.' : ` ${cap(band)} risk.`)));
      else if ((s.location || {}).mode === 'lake') rows.push(row('Water quality', 'Not estimated: the E. coli model showed no skill on lakes.'));
      if (!nil(x.rain_48h_mm)) rows.push(row('Rain here', `${Math.round(x.rain_48h_mm)} mm in the 48 hours to midday.`));
    } else if (R.daily(s)) rows.push(row('Sewage spills upstream', 'No forecast for this day in this update.'));
    if (s.algae && /algae/.test(head)) rows.push(row('Algae at the last check', `The Environment Agency's sampler saw ${esc(s.algae.phrase)} on ${esc(s.algae.date)}. Some algae are toxic; the check cannot tell which.`));
    rows.push(rating(s, iso));
    if (R.daily(s)) rows.push(row('How far ahead', w.j === 0 ? 'The day this forecast was issued for.'
      : `${w.j} day${w.j === 1 ? '' : 's'}. ${data.lead_skill ? howSure(data.lead_skill, w.j, x && !nil(R.ecoliBand(s, x))) + ' ' : ''}The rain forecast behind it can still change.`));
    return h + `<dl class="fields">${rows.join('')}</dl>`;
  }
  // A day beyond the forecast: when its forecast first appears, and what is known now.
  function later(s, iso, from) {
    const total = (s.upstream_summary || {}).overflows || 0, km = (s.assumptions || {}).max_upstream_km || 60;
    let h = `<p>The forecast for ${longDate(iso)} first appears on <b>${longDate(from)}</b>, as the last of its five days, and is updated several times a day after that.</p>`;
    const rows = [];
    if (isolated(s)) rows.push(row('Storm overflows', `No river flows into this lake in the river network, so no overflow can reach it. ${esc(R.OTHER_RISKS)}`));
    else if (s.error) rows.push(row('Forecast', esc(R.COVER[R.level(s)] || 'No forecast in this update')));
    else if (!total) rows.push(row('Storm overflows', `None monitored within ${km} km upstream, so there will be no spill forecast here. ${esc(R.OTHER_RISKS)}`));
    else rows.push(row('Storm overflows', `${total} monitored upstream, listed below with how often each spills in a year.`));
    rows.push(rating(s, iso));
    return h + `<p class="ev-say">What is known now:</p><dl class="fields">${rows.join('')}</dl>`;
  }
  function forecast(s, iso, data, now) {
    const w = when(s, iso), age = (now - Date.parse(data.generated_at)) / 60000;
    const issued = new Date(data.generated_at).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    let h = `<h3 id="day-h">${longDate(iso)}</h3>`;
    if (w.state === 'past') return h + '<p>That day has passed. Pick the day of your event.</p>';
    if (w.state === 'later') return h + later(s, iso, w.from);
    if (age > STALE_MIN) h += `<p class="notice" role="alert"><b>Stale.</b> This forecast is ${ago(age)} old: the automatic update has not run since. Treat it as out of date.</p>`;
    return h + within(s, iso, w, data)
      + `<p class="check">A forecast, not a water test: check the signs at the water before you swim. Issued ${esc(issued)}; it is updated several times a day, so look again the evening before and on the morning of the event.</p>`;
  }

  // ------------------------------------------------------------------ the overflows upstream
  // The spot's overflows, most reach first. The forecast file keeps the ten with the most reach and
  // spill chance this week (build_site.KEEP_CONTRIBUTORS); where there are more, the page loads every
  // one from data/upstream/<id>.json (build_site.write_upstream) and passes them as `full`: an array,
  // or 'loading' or 'failed' while it has not got them. An event weeks away is better ordered by reach
  // alone, which does not change with the weather.
  const listOf = (s, full) => Array.isArray(full) && full.length ? full : (s.contributors || []);
  function overflowRows(s, full) {
    return listOf(s, full).slice().sort((a, b) => b.weight - a.weight).map(c => ({
      site_id: c.site_id, site_name: c.site_name ?? c.site_id, name: nameCase(c.site_name ?? c.site_id), company: c.company || '', into: c.receiving_watercourse || '',
      km: Math.round(((c.distance_km || 0) + (c.lake_distance_km || 0)) * 10) / 10, travel_h: c.travel_h, reach: c.weight,
      spills: c.lta_spills, spill_hours: c.spill_hours, live: !!c.has_live, lat: c.lat, lon: c.lon }));
  }
  const num = (v, d = 0) => nil(v) || Number.isNaN(Number(v)) ? '–' : Number(v).toFixed(d);
  // A feed's name escaped, and free to break after its _, / or &, and nowhere else inside a word:
  // "North_CSO_Princetown" and "WEIR BROOK&TRIB OF WEIR BROOK" widened the table past its column.
  const brk = s => esc(s).replace(/(_|\/|&amp;)(?=\S)/g, '$1<wbr>');
  function overflows(s, full) {
    const u = s.upstream_summary || {}, total = u.overflows || 0, km = (s.assumptions || {}).max_upstream_km || 60, list = overflowRows(s, full);
    let h = '<h3 id="ov-h">Storm overflows upstream</h3>';
    if (isolated(s)) return h + '<p>No river flows into this lake in the river network, so no storm overflow can reach it.</p>';
    if (s.error) return h + '<p>This spot has no forecast in this update, so its overflows are not listed.</p>';
    if (!total) return h + `<p>No monitored storm overflow is within ${km} km upstream along the river network.</p>`;
    h += `<p>${total === 1 ? 'One monitored storm overflow is' : `${total} monitored storm overflows are`} within ${km} km upstream along the river network`
      + (u.without_live_feed ? `: ${u.with_live_feed} report their status live, and ${u.without_live_feed} ${u.without_live_feed === 1 ? 'has' : 'have'} no live feed, so SwimSignal forecasts ${u.without_live_feed === 1 ? 'it' : 'them'} from rain and their yearly record alone`
        : total === 1 ? ', with a live feed' : ', all with a live feed') + '.'
      + (u.max_travel_h ? ` Sewage from the farthest takes ${hoursAway(u.max_travel_h)} to arrive.` : '') + '</p>';
    if (list.length < total) h += full === 'loading' ? `<p>The table lists the ${list.length} that matter most in the current forecast while the other ${total - list.length} load.</p>`
      : `<p>The table lists the ${list.length} that matter most in the current forecast: the full list of ${total} could not be loaded. Try again later.</p>`;
    const cell = (l, v, cls = '') => `<td${cls ? ` class="${cls}"` : ''} data-l="${l}">${v}</td>`;
    h += '<div class="tw"><table class="ovt"><thead><tr><th scope="col">Overflow</th><th scope="col">Company</th><th scope="col">Discharges into</th>'
      + '<th scope="col" class="num">Upstream</th><th scope="col" class="num">Travel</th><th scope="col" class="num">Reach</th>'
      + '<th scope="col" class="num">Spills a year</th><th scope="col" class="num">Hours spilling</th><th scope="col">Live feed</th></tr></thead><tbody>'
      + list.map(o => `<tr><th scope="row" class="ov">${brk(o.name)}</th>${cell('Company', esc(o.company))}${cell('Into', brk(o.into))}`
        + cell('Upstream', `${num(o.km, 1)} km`, 'num') + cell('Travel', o.travel_h < 1 ? 'under 1 h' : `${num(o.travel_h)} h`, 'num')
        + cell('Reach', o.reach > 0 && o.reach < 0.005 ? '&lt;1%' : pct(o.reach), 'num')   // "under 1%" widened the column
        + cell('Spills a year', num(o.spills), 'num') + cell('Hours spilling', num(o.spill_hours), 'num')
        + cell('Live feed', o.live ? 'Yes' : 'No') + '</tr>').join('') + '</tbody></table></div>';
    if (PAGE_ID.test(s.id)) h += `<p><a href="spot/${esc(s.id)}/profile/">Overflow history, 2021 to 2025</a>: each overflow's spills and spill hours a year.</p>`;   // build_site.write_profiles
    return h + '<p class="small muted"><b>Upstream</b>: along the river network. <b>Travel</b>: how long sewage takes to arrive, at the model\'s river speed. '
      + '<b>Reach</b>: the chance a spill there affects this spot, from die-off over the travel time and dilution by the size of the river network upstream. '
      + '<b>Spills a year</b>: its long-term average, from the Environment Agency\'s annual returns. <b>Hours spilling</b>: the total in its latest annual return. '
      + '<b>Live feed</b>: whether its water company reports its status as it happens.</p>';
  }

  // The table as a CSV file: one row an overflow, under comment lines that say what it is and carry
  // the credits, as data/verification_live.csv does (the water companies' data is CC BY 4.0, the
  // Environment Agency's OGL v3.0; build_site.data_credits). base is the site's address.
  const COLS = ['site_id', 'site_name', 'company', 'receiving_watercourse', 'km_upstream', 'travel_hours', 'reach', 'spills_a_year', 'spill_hours_latest_return', 'live_feed', 'lat', 'lon'];
  // A field a spreadsheet could read as a formula is prefixed with ' (a name from a feed is not trusted).
  const field = v => { let t = nil(v) ? '' : String(v); if (typeof v === 'string' && /^[=+\-@\t\r]/.test(t)) t = "'" + t;
    return /[",\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
  function csv(s, data, base, full) {
    const u = s.upstream_summary || {}, list = overflowRows(s, full), cr = data.credits || {}, km = (s.assumptions || {}).max_upstream_km || 60;
    const lic = Object.entries(cr.licences || {}).map(([k, v]) => `${k} ${v}`).join('; ');
    const notes = [
      `SwimSignal: storm overflows upstream of ${s.name} (${s.id}), from the forecast issued ${data.generated_at}. ${base}${spotHref(s.id)}`,
      `${u.overflows || 0} monitored overflows within ${km} km upstream along the river network` + (list.length < (u.overflows || 0) ? `; these are the ${list.length} that matter most in that forecast.` : '.'),
      'Columns: site_id and site_name, the water company\'s id and name for the overflow; company; receiving_watercourse, as the company names it;',
      'km_upstream, along the river network; travel_hours, at the model\'s river speed; reach, 0 to 1, the chance a spill there affects the spot;',
      'spills_a_year, its long-term average from the Environment Agency\'s annual returns; spill_hours_latest_return, the hours it spilled in its',
      'latest annual return; live_feed, 1 if its water company reports its status live; lat, lon.',
      'Lines that start with # are notes: skip them when reading (pandas: comment=\'#\'; R: comment.char=\'#\').',
      ...(cr.attribution ? [`Credits: ${cr.attribution}`] : []), ...(cr.modified ? [cr.modified] : []),
      ...(s.source === 'openstreetmap' && cr.spot_locations ? [cr.spot_locations] : []),
      `${lic ? `Licences: ${lic}. ` : ''}Full credits: ${cr.full || base + 'terms.html#data'}`,
    ];
    const rows = list.map(o => [o.site_id, o.site_name, o.company, o.into, o.km, o.travel_h, o.reach, o.spills, o.spill_hours, o.live ? 1 : 0, o.lat, o.lon].map(field).join(','));
    return notes.map(n => `# ${n.replace(/[\r\n]+/g, ' ')}\n`).join('') + COLS.join(',') + '\n' + rows.map(r => r + '\n').join('');
  }

  // ------------------------------------------------------------------ the page
  // A spot and, if chosen, the event day (iso): the forecast for the day, then the overflows.
  function view(s, iso, data, base, now = Date.now(), full) {
    R.setToday(String(data.generated_at).slice(0, 10));
    const loc = s.location || {}, page = spotHref(s.id), own = PAGE_ID.test(s.id);
    const meta = [cap(s.kind || 'river'), s.source === 'designated' ? 'Environment Agency designated bathing water' : null, loc.watercourse ? esc(loc.watercourse) : null].filter(Boolean);
    const links = [`<a href="${esc(page)}">The spot's forecast</a>`, ...(own ? [`<a href="spot/${esc(s.id)}/sign/">A sign to print</a>`] : []),
      `<a href="embed.html?spot=${esc(encodeURIComponent(s.id))}&amp;screen">A live sign for a screen</a>`];
    const total = (s.upstream_summary || {}).overflows || 0, n = (s.contributors || []).length;
    return `<h2 class="ev-name" id="ev-name">${esc(s.name)}</h2><p class="ev-meta">${meta.join(' · ')}</p><p class="ev-links">${links.join(' · ')}</p>`
      + (iso ? forecast(s, iso, data, now) : '<p class="ev-say">Pick the day of your event for its forecast.</p>')
      + overflows(s, full)
      + `<p class="actions screen-only">${n && !s.error && total ? '<button type="button" class="btn" id="csv">Download the overflows as CSV</button>' : ''}<button type="button" class="btn" id="print">Print this page</button></p>`
      + `<p class="print-only small muted">Printed from ${esc(base)}organisers.html. Look at ${esc(base)}${esc(page)} for the latest forecast.</p>`;
  }
  // The address after the #: spot=<id>&date=<yyyy-mm-dd>.
  const fromHash = h => { const p = new URLSearchParams(String(h || '').replace(/^#/, ''));
    const date = p.get('date'); return { spot: p.get('spot') || null, date: date && ISO.test(date) ? date : null }; };
  const toHash = (id, iso) => { const p = new URLSearchParams(); if (id) p.set('spot', id); if (iso) p.set('date', iso); const q = p.toString(); return q ? '#' + q : ''; };

  // In the page: fill the spot list, read the spot and the day from the address, and redraw when
  // either changes. The forecast is fetched once (no-cache: the server is asked, as the app does).
  async function start() {
    const sel = document.getElementById('spot'), date = document.getElementById('date'), out = document.getElementById('event');
    const base = new URL('./', location.href).href;
    let data;
    try {
      const res = await fetch('data/spots.json', { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (e) { sel.innerHTML = '<option value="">The spots could not be loaded</option>'; out.innerHTML = '<p class="notice">The forecasts could not be loaded. Try again later.</p>'; return; }
    R.setToday(String(data.generated_at).slice(0, 10));
    const spots = (data.spots || []).slice().sort((a, b) => a.name.localeCompare(b.name, 'en-GB'));
    sel.innerHTML = '<option value="">Choose a spot</option>' + spots.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
    sel.disabled = false; date.min = R.today();
    const st = fromHash(location.hash);
    if (st.spot && spots.some(s => s.id === st.spot)) sel.value = st.spot;
    if (st.date) date.value = st.date;
    // Every overflow upstream of a spot, by id: asked for once, when the spot has more than the forecast
    // file lists, then the page is drawn again.
    const FULL = {};
    const fullOf = s => {
      if (!s || s.error || !PAGE_ID.test(s.id) || ((s.upstream_summary || {}).overflows || 0) <= (s.contributors || []).length) return undefined;
      if (FULL[s.id] === undefined) {
        FULL[s.id] = 'loading';
        fetch(`data/upstream/${encodeURIComponent(s.id)}.json`, { cache: 'no-cache' })
          .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
          .then(j => { FULL[s.id] = Array.isArray(j.overflows) && j.overflows.length ? j.overflows : 'failed'; })
          .catch(() => { FULL[s.id] = 'failed'; })
          .then(() => { if (sel.value === s.id) draw(); });
      }
      return FULL[s.id];
    };
    const draw = () => {
      const s = spots.find(x => x.id === sel.value), iso = ISO.test(date.value) ? date.value : null;
      const addr = location.pathname + location.search + toHash(s ? s.id : null, iso);
      if (addr !== location.pathname + location.search + location.hash) history.replaceState(null, '', addr);
      const full = fullOf(s);
      out.innerHTML = s ? view(s, iso, data, base, Date.now(), full) : '';
      const dl = document.getElementById('csv');
      if (dl) dl.addEventListener('click', () => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([csv(s, data, base, full)], { type: 'text/csv;charset=utf-8' }));
        a.download = `swimsignal-overflows-${s.id}.csv`; document.body.append(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      });
      const pr = document.getElementById('print'); if (pr) pr.addEventListener('click', () => window.print());
    };
    sel.addEventListener('change', draw); date.addEventListener('change', draw);
    document.getElementById('pick').addEventListener('submit', e => { e.preventDefault(); draw(); });
    draw();
  }

  return { when, view, forecast, overflows, overflowRows, csv, fromHash, toHash, spilling, howSure, start, STALE_MIN };
})();

if (typeof module === 'object' && module.exports) module.exports = Organisers;
else Organisers.start();
