// The decision record (record.html): one printable A4 page for one spot and one day, for an organiser or
// a leader to attach to a written go/no-go decision (docs/MARKETS-2026-10.md, B3). In order:
//  1. what it is and is not, first: a forecast, not a water test, which never says the water is safe or
//     clean, with the live accuracy figures from data/verification.json (the warning table at the High
//     risk line: the share of spills warned of, and the share of warnings followed by a spill);
//  2. the spot, the day, the level and why: the headline, the overflows that matter most with how far
//     and how long away, what was discharging, the rain;
//  3. every input with its time, its age and its source;
//  4. what the forecast cannot see, in the About page's words (CANNOT_SEE; a test checks them);
//  5. blank lines for who decided what, and when.
// Outside the five days it says when the forecast for the day first appears, and gives no record.
// The wording is for Ethan's approval, and a solicitor's read before any paid use (open question 4).
//
// The level and its words are levels.js's, the spills' clause and how sure organisers.js's (the spot
// page's words), the ages and the overflow counts evidence.js's: the record never disagrees with the
// spot's page. Nothing is stored or sent: the spot and the day are after the # in the address,
// record.html#spot=<id>&day=YYYY-MM-DD.
//
// A plain script, as organisers.js: the page loads levels.js, evidence.js and organisers.js first, and
// this file finds their names there; Node requires them for the tests (tests/site_record.test.cjs).
const Record = (() => {
  const node = typeof module === 'object' && module.exports;
  const R = node ? require('./levels.js')
    : { ORDER, COVER, NO_OVERFLOWS, NO_RIVER, OTHER_RISKS, setToday, today, rank, risk, level, dayHeadline, nowBecause, daily, ecoliBand, ecoliUntested, poorAdvice };   // levels.js's globals
  const E = node ? require('./evidence.js') : { evidenceAge, evidenceOverflows, evidenceSample };
  const O = node ? require('./organisers.js') : Organisers;
  const PAGE_ID = /^[A-Za-z0-9_-]+$/;
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  const TZ = 'Europe/London';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  const nil = v => v === null || v === undefined;
  const tone = l => l === R.NO_OVERFLOWS ? 'clear' : R.ORDER[l] === undefined ? 'na' : l.replace(' ', '');
  const spotHref = id => PAGE_ID.test(id) ? `spot/${id}/` : `./?spot=${encodeURIComponent(id)}`;
  const longDate = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const shortDate = (iso, year = true) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', ...(year ? { year: 'numeric' } : {}) });
  const at = t => new Date(t).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: TZ });
  const pct = p => p > 0 && p < 0.005 ? 'under 1%' : Math.round(p * 100) + '%';
  const away = h => nil(h) ? '' : h < 1 ? 'under an hour' : `about ${Math.round(h)} h`;
  const ago = m => { const t = Math.max(0, Math.round(m)); return t < 60 ? `${t} min` : t % 60 ? `${Math.floor(t / 60)} h ${t % 60} min` : `${t / 60} h`; };
  const row = (label, body) => body ? `<dt>${label}</dt><dd>${body}</dd>` : '';

  // What the forecast cannot see: the About page's list, word for word (about.html, "What it cannot see").
  // tests/site_record.test.cjs fails when the two differ.
  const CANNOT_SEE = [
    'The spill forecast covers monitored storm overflows only. The E. coli estimate allows for rain washing in pollution from other sources on average, but knows nothing about a particular farm, road, boat, misconnected drain or incident.',
    'Dŵr Cymru Welsh Water\'s live overflow status is not shown. Its map has a public data layer, but with no licence to reuse it, and SwimSignal is waiting for Dŵr Cymru\'s terms. Its overflows, which matter at the spots on the Dee and the Wye, are forecast from rain and their yearly spill record, with no "right now".',
    'Its level does not include the Environment Agency\'s short-notice advice against bathing after pollution or an algal bloom. On a bathing water\'s page, opening "Today\'s EA advice" loads the Agency\'s own panel, which has it.',
    'It says nothing about currents, cold water or other dangers.',
    'A "low" reading means nothing the site looks at flags the day. It does not mean the water is clean, or that it is safe to swim there.',
  ];

  // ------------------------------------------------------------------ 1. what it is
  // The live scores as warnings (verification.json, live.warning_table): the share of spills warned of,
  // and the share of warnings followed by a spill, in plain words, as the Accuracy page gives them.
  function accuracy(ver, base) {
    const W = ((ver || {}).live || {}).warning_table;
    if (!W || !W.n || nil(W.hit_rate) || nil(W.warnings_true) || !W.first_day || !W.last_day)
      return `The live accuracy figures could not be loaded. They are on ${esc(base)}verification.html.`;
    const sameYear = W.first_day.slice(0, 4) === W.last_day.slice(0, 4);
    let t = `In live scoring from ${shortDate(W.first_day, !sameYear)} to ${shortDate(W.last_day)}, it warned of ${pct(W.hit_rate)} of the spills at the storm overflows it scores, `
      + `and ${pct(W.warnings_true)} of its warnings were followed by a spill. A warning is a spill chance of ${pct(W.warn_at ?? 0.4)} or more, the High risk line.`;
    if (W.hit_rate < 0.5) t += ` So it misses most spills${W.warnings_true < 0.5 ? ', and most of its warnings are false alarms' : ''}.`;
    else if (W.warnings_true < 0.5) t += ' Most of its warnings are false alarms.';
    if (W.n_days < 14) t += ` That is ${W.n_days} day${W.n_days === 1 ? '' : 's'} of scores, too few to judge across different weather.`;
    return t;
  }
  function opening(ver, base) {
    return '<p class="r-first">This page records SwimSignal\'s pollution risk forecast for one spot on one day, to attach to a written decision. '
      + 'It is a forecast, not a water test: nothing was sampled at the water for it. It never says the water is safe or clean, and no level means that. '
      + `${accuracy(ver, base)} The decision, and the reasons for it, are those of the people who sign below.</p>`
      + '<p class="r-note">This page shows the latest forecast, and changes when the forecast does. Print it, or save it as a PDF, when you decide. '
      + 'The <a href="terms.html#responsibility">terms of use</a> say what SwimSignal takes responsibility for.</p>';
  }

  // ------------------------------------------------------------------ 2. the level and why
  // The overflows most likely to affect the spot on day j (spill chance times reach, as the spot page
  // picks them), each with how far upstream and how long its sewage takes to arrive. Where none is
  // likely, the three with the most reach. Names and distances from organisers.js's table rows.
  function topOverflows(s, j) {
    const rows = new Map(O.overflowRows(s).map(o => [o.site_id, o]));
    const spill = c => c.p_spill_days ? c.p_spill_days[j] : j === 0 ? c.p_spill_today : j === 1 ? c.p_spill_tomorrow : undefined;
    const all = (s.contributors || []).map(c => ({ c, p: spill(c), o: rows.get(c.site_id) })).filter(x => x.o);
    const likely = all.filter(x => !nil(x.p) && x.c.weight * x.p >= 0.001).sort((a, b) => b.c.weight * b.p - a.c.weight * a.p).slice(0, 3);
    const list = likely.length ? likely : all.slice().sort((a, b) => b.c.weight - a.c.weight).slice(0, 3);
    if (!list.length) return '';
    const one = ({ c, p, o }) => `<li><b>${esc(o.name)}</b>: ${o.km} km upstream, sewage arrives in ${away(o.travel_h)}. `
      + `${nil(p) ? '' : `Spill chance ${pct(p)}, `}reach ${pct(o.reach)}.${c.status === 1 ? ' Discharging when the forecast was issued.' : ''}</li>`;
    return (likely.length ? '' : 'None is likely to reach the spot that day. The ones with the most reach: ') + `<ul class="r-ovs">${list.map(one).join('')}</ul>`;
  }
  function levelBlock(s, iso, w, data) {
    const x = w.x, j = w.j, total = (s.upstream_summary || {}).overflows || 0;
    const lv = !R.daily(s) ? R.level(s) : x ? R.risk(s, x).level : null;
    const head = R.dayHeadline(s, iso), lead = R.ORDER[lv] !== undefined ? `${cap(lv)} risk` : null;
    const reason = !lead ? '' : head.startsWith(lead) ? cap(head.slice(lead.length).replace(/^: /, '')) : head;
    let h = `<p class="r-level ${tone(lv)}">${esc(lead || head)}</p>`;
    if (reason) h += `<p class="r-why">${esc(reason)}</p>`;
    if (lv === R.NO_OVERFLOWS || lv === R.NO_RIVER) h += `<p class="r-why">${esc(R.OTHER_RISKS)}</p>`;
    const rows = [];
    // Right now, on the day itself, where the live feeds put it higher than the day's forecast.
    if (iso === R.today() && R.daily(s) && s.now) {
      const n = R.risk(s, s.now, true);
      if (R.rank(n.level) > R.rank(lv)) rows.push(row('Right now', `${cap(n.level)} risk: ${esc(R.nowBecause(s, n))}, from the live feeds when the forecast was issued.`));
    }
    if (R.daily(s) && x) {
      if (nil(x.risk)) rows.push(row('Sewage spills upstream', 'The rainfall forecast for this day has not arrived, so there is no figure.'));
      else { const i = x.risk * 100;
        rows.push(row('Sewage spills upstream', `${cap(x.label)} risk: ${O.spilling(x, total)}. Exposure index <b>${i > 0 && i < 0.5 ? 'under 1' : Math.round(i)}</b> of 100, after travel time, die-off and dilution.`));
        rows.push(row('The overflows that matter most', topOverflows(s, j))); }
      const ov = E.evidenceOverflows(s, data.generated_at);
      if (ov) rows.push(row('Discharging when the forecast was issued', ov.say));
      const band = R.ecoliBand(s, x);
      if (band) rows.push(row('Water quality', `Chance a water sample would show E. coli over 900 per 100 ml: <b>${Math.round(x.p_ecoli_gt900 * 100)}%</b>.`
        + (R.ecoliUntested(x) ? ' Untested from October to April, when the Environment Agency takes no samples, so it does not set the level.' : ` ${cap(band)} risk.`)));
    } else if (R.daily(s)) rows.push(row('Sewage spills upstream', 'No forecast for this day in this update.'));
    if (x && !nil(x.rain_48h_mm)) rows.push(row('Rain here', `${Math.round(x.rain_48h_mm)} mm in the 48 hours to midday on ${esc(longDate(iso))}.`));
    if (R.daily(s)) rows.push(row('How far ahead', j === 0 ? 'The day this forecast was issued for.'
      : `${j} day${j === 1 ? '' : 's'}. ${data.lead_skill ? O.howSure(data.lead_skill, j, x && !nil(R.ecoliBand(s, x))) + ' ' : ''}The rain forecast behind it can still change.`));
    return h + (rows.length ? `<dl class="fields">${rows.join('')}</dl>` : '');
  }

  // ------------------------------------------------------------------ 3. the inputs, their ages and sources
  // Each: what, what it said, when (a time or a day), and whose. Ages are counted from when the page is
  // read (now), as the spot page's are, so a printed record says how old each part was when printed.
  function inputs(s, iso, data, now) {
    const out = [], when = t => `${ISO.test(t) ? shortDate(t) : at(t)}, ${E.evidenceAge(t, now).toLowerCase()}`;
    const add = (what, say, t, src) => out.push(`<dt>${what}</dt><dd>${say}${t ? ` <span class="r-age">${t}.</span>` : ''} <span class="r-src">Source: ${src}.</span></dd>`);
    const model = (s.assumptions || {}).version;
    add('Forecast issued', 'The forecast on this page.', when(data.generated_at), `SwimSignal${model ? `, model <code>${esc(model)}</code>` : ''}`);
    // The live overflow status: when the feeds were read, and the newest and oldest update among this spot's overflows.
    const total = (s.upstream_summary || {}).overflows || 0;
    if (total) {
      const polled = ((data.build || {}).live_feeds || {}).polled_at;
      const times = (s.contributors || []).filter(c => c.has_live && c.feed_updated_at && !Number.isNaN(Date.parse(c.feed_updated_at))).map(c => Date.parse(c.feed_updated_at));
      const lo = times.length ? at(Math.min(...times)) : '', hi = times.length ? at(Math.max(...times)) : '';
      const span = !times.length ? '' : ` Of the ${(s.contributors || []).length} overflows that matter most, the feeds' latest updates ${lo === hi ? `are from ${lo}` : `run from ${lo} to ${hi}`}.`;
      add('Live overflow status', `What each overflow upstream was doing when the forecast was made.${span}`, polled ? `Feeds read ${when(String(polled).replace(' ', 'T'))}` : '',
        'the water companies\' live feeds, via the National Storm Overflow Hub');
    }
    const x = (s.days || []).find(d => d.date === iso);
    if (x && !nil(x.rain_48h_mm)) add('Rain forecast', `${Math.round(x.rain_48h_mm)} mm in the 48 hours to midday on ${esc(longDate(iso))}.`, `Read with the forecast, ${at(data.generated_at)}`,
      'Open-Meteo.com, from Met Office forecasts');
    const cl = s.classification, ea = cl && /^https:\/\//.test(cl.url || '') ? `the <a href="${esc(cl.url)}">Environment Agency</a>` : 'the Environment Agency';
    if (cl && cl.class) add('Environment Agency rating', `${cap(String(cl.class).toLowerCase())}, for ${esc(cl.year)}. ${String(cl.class).toLowerCase() === 'poor' ? R.poorAdvice(iso) : 'From its lab samples over up to four seasons.'}`, '', ea);
    else if (cl) add('Environment Agency rating', 'None yet: this bathing water is too new to have one.', '', ea);
    else add('Environment Agency rating', 'Not a designated bathing water, so the Environment Agency does not test it for bathing.', '', 'the Environment Agency\'s list of bathing waters');
    if (s.algae && s.algae.date) add('Algae at the last check', `${cap(esc(s.algae.phrase))}.`, when(s.algae.date), 'the Environment Agency\'s sampler, by eye, not a lab test');
    const sample = E.evidenceSample(s.lab_sample, now);
    if (sample) add('Latest lab sample', sample, when(s.lab_sample.taken_at), ea);
    const rs = s.river_state;
    if (rs && !nil(rs.level_m) && rs.observed_at) add('River level', `${rs.level_m.toFixed(2)} m at ${esc(rs.station)}${nil(rs.distance_km) ? '' : `, ${rs.distance_km} km away`}`
      + `${!nil(rs.typical_low_m) && !nil(rs.typical_high_m) ? `; its usual range is ${rs.typical_low_m.toFixed(2)} to ${rs.typical_high_m.toFixed(2)} m` : ''}. Not part of the pollution level.`,
      when(rs.observed_at), 'Environment Agency real-time flood and river level data');
    const wt = s.water_temp;
    if (wt && !nil(wt.temp_c) && wt.observed_at) add('Water temperature', `${Math.round(wt.temp_c)}°C, measured ${esc(wt.where || '')}${wt.river ? ` on the ${esc(wt.river)}` : ''}`
      + `${nil(wt.river_km) ? '' : `, ${wt.river_km} km ${esc(wt.direction || 'away')}`}. Not part of the pollution level.`, when(wt.observed_at), 'the Environment Agency\'s water-quality sensor');
    if (s.flood_alerts === null) add('Flood alerts', 'Not checked: the Environment Agency did not answer when this forecast was made. Check flood warnings.', '', 'the Environment Agency');
    else if (Array.isArray(s.flood_alerts)) {
      const fl = s.flood_alerts.filter(f => f && f.severity);
      add('Flood alerts', fl.length ? fl.map(f => `${esc(f.severity)} in force: ${esc(f.area)}.`).join(' ') + ' A separate hazard, not part of the pollution level.'
        : 'None in force nearby when the forecast was made.', `Checked with the forecast, ${at(data.generated_at)}`, 'the Environment Agency');
    }
    return `<dl class="fields r-inputs">${out.join('')}</dl>`;
  }

  // ------------------------------------------------------------------ the page
  const DECIDE = '<h2 id="r-decide">The decision</h2><div class="r-lines">'
    + ['Decided by', 'Role', 'Decision (circle one): go / no-go / changed plan', 'Date and time'].map(l => `<p class="r-line"><span>${l}</span></p>`).join('')
    + '<p class="r-line wide"><span>Notes</span></p><p class="r-line wide"></p><p class="r-line wide"><span>Signature</span></p></div>';
  // The whole record for a spot (s, or null when the id is not in the forecast) and a day.
  function view(s, iso, data, ver, base, now = Date.now(), id = '') {
    R.setToday(String(data.generated_at).slice(0, 10));
    const first = opening(ver, base);
    if (!s) return first + `<p class="notice">${id ? `No spot with the id <b>${esc(id)}</b> is in this forecast: it may have been renamed or removed.` : 'Choose a spot.'}</p>`;
    iso = iso && ISO.test(iso) ? iso : R.today();
    const loc = s.location || {};
    const meta = [cap(s.kind || 'river'), s.source === 'designated' ? 'Environment Agency designated bathing water' : null, loc.watercourse || null].filter(Boolean).map(esc).join(' · ');
    let h = first + `<h2 class="r-spot">${esc(s.name)}</h2><p class="r-meta">${meta} · <a href="${esc(spotHref(s.id))}">${esc(base)}${esc(spotHref(s.id))}</a></p>`
      + `<p class="r-day">${esc(longDate(iso))}</p>`;
    const w = O.when(s, iso);
    if (w.state === 'past') return h + '<p>That day has passed. This page shows only the latest forecast, which no longer covers it. Print the record, or save it as a PDF, on the day of the decision.</p>';
    if (w.state === 'later') return h + `<p>The forecast for ${esc(longDate(iso))} first appears on <b>${esc(longDate(w.from))}</b>, as the last of its five days, and is updated several times a day after that. Make the record then, as close to the decision as you can.</p>`;
    const m = (now - Date.parse(data.generated_at)) / 60000;
    if (m > O.STALE_MIN) h += `<p class="notice" role="alert"><b>Stale.</b> This forecast is ${ago(m)} old (issued ${esc(at(data.generated_at))}). The automatic update has not run since; treat everything below as out of date.</p>`;
    return h + `<h3>The level and why</h3>${levelBlock(s, iso, w, data)}`
      + `<h3>What it rests on, and how old each part is</h3><p class="r-note">Ages are counted from when this page was opened, ${esc(at(now))}.</p>${inputs(s, iso, data, now)}`
      + `<h3>What the forecast cannot see</h3><ul class="r-cannot">${CANNOT_SEE.map(t => `<li>${esc(t)}</li>`).join('')}</ul>`
      + DECIDE
      + '<p class="actions screen-only"><button type="button" class="btn" id="print">Print this record</button></p>'
      + `<p class="print-only r-foot">Printed from ${esc(base)}record.html#spot=${esc(encodeURIComponent(s.id))}&amp;day=${iso}, ${esc(at(now))}.</p>`;
  }
  // The address after the #: spot=<id>&day=<yyyy-mm-dd>.
  const fromHash = h => { const p = new URLSearchParams(String(h || '').replace(/^#/, ''));
    const day = p.get('day'); return { spot: p.get('spot') || null, day: day && ISO.test(day) ? day : null }; };
  const toHash = (id, iso) => { const p = new URLSearchParams(); if (id) p.set('spot', id); if (iso) p.set('day', iso); const q = p.toString(); return q ? '#' + q : ''; };

  async function start() {
    const sel = document.getElementById('spot'), date = document.getElementById('day'), out = document.getElementById('record');
    const base = new URL('./', location.href).href;
    let data, ver = null;
    try {
      const [res, v] = await Promise.all([fetch('data/spots.json', { cache: 'no-cache' }),
        fetch('data/verification.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).catch(() => null)]);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json(); ver = v;
    } catch (e) { sel.innerHTML = '<option value="">The spots could not be loaded</option>'; out.innerHTML = '<p class="notice">The forecasts could not be loaded. Try again later.</p>'; return; }
    R.setToday(String(data.generated_at).slice(0, 10));
    const spots = (data.spots || []).slice().sort((a, b) => a.name.localeCompare(b.name, 'en-GB'));
    sel.innerHTML = '<option value="">Choose a spot</option>' + spots.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('');
    sel.disabled = false;
    const draw = () => {
      const st = fromHash(location.hash), s = st.spot ? spots.find(x => x.id === st.spot) || null : null, iso = st.day || R.today();
      sel.value = s ? s.id : ''; date.value = iso;
      document.title = s ? `${s.name}, ${new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}: decision record · SwimSignal` : 'Decision record · SwimSignal';
      out.innerHTML = view(s, iso, data, ver, base, Date.now(), st.spot || '');
      const pr = document.getElementById('print'); if (pr) pr.addEventListener('click', () => window.print());
    };
    const go = () => { const addr = location.pathname + location.search + toHash(sel.value || null, ISO.test(date.value) ? date.value : null);
      if (addr !== location.pathname + location.search + location.hash) { history.replaceState(null, '', addr); draw(); } };
    sel.addEventListener('change', go); date.addEventListener('change', go);
    document.getElementById('pick').addEventListener('submit', e => { e.preventDefault(); go(); });
    window.addEventListener('hashchange', draw);
    draw();
  }

  return { view, opening, accuracy, levelBlock, inputs, topOverflows, fromHash, toHash, start, CANNOT_SEE };
})();

if (typeof module === 'object' && module.exports) module.exports = Record;
else Record.start();
