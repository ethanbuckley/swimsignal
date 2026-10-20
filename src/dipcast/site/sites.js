// The sites view (sites.html): several listed spots on one page, for an activity centre, a club or a
// council, to bookmark and print before a session (docs/MARKETS-2026-10.md, B2). Each spot is one row:
// its name, its headline, the five days as the list's bars, the reason in one line, and links to the
// spot's page and to a decision record (record.html). The forecast's issue time and its issue id are said
// once at the top, with the app's stale notice, and the data credits for the listed spots close the page
// (printed.js). Printed, nine rows and the credits fit one A4 page.
//
// The words are the site's own: the headline and the reason are levels.js's (headParts, weekNext), and a
// low day's clause is organisers.js's (spilling, the spot page's words), so a row never disagrees with the
// spot's page, the list or an alert.
//
// Nothing is stored or sent: the spots and the name are after the # in the address,
// sites.html#spots=wharfe-burnsall,grasmere&name=Club%20launches (lists.js, sitesHash, makes it). An id
// that is not in the forecast, renamed or removed, is listed as not found; the page never fails on one.
//
// The same file draws "Make a sites link" on the organisers' page (maker), from the spots that page has
// already loaded into its spot list.
//
// A plain script, as organisers.js: the page loads levels.js, lists.js, organisers.js and printed.js first, and
// this file finds their names there; Node requires them for the tests (tests/site_sites.test.cjs). The
// organisers' page loads this file for the maker alone, without printed.js.
const Sites = (() => {
  const node = typeof module === 'object' && module.exports;
  const R = node ? require('./levels.js')
    : { ORDER, COVER, NO_FORECAST, NO_OVERFLOWS, NO_RIVER, OTHER_RISKS, setToday, today, rank, risk, level, dayLevel, headParts, dayHeadline, weekNext, daily, walesWords, eaUnchecked };   // levels.js's globals
  const Li = node ? require('./lists.js') : { listName, listIds, sitesHash, LINK_SPOTS_MAX };
  const O = node ? require('./organisers.js') : Organisers;
  const P = node ? require('./printed.js') : typeof Printed === 'undefined' ? null : Printed;
  const PAGE_ID = /^[A-Za-z0-9_-]+$/;   // the app and build_site.py use the same rule
  const DEFAULT_NAME = 'Sites view';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  const nil = v => v === null || v === undefined;
  const tone = l => l === R.NO_OVERFLOWS || l === R.NO_RIVER ? 'clear' : R.ORDER[l] === undefined ? 'na' : l.replace(' ', '');   // index.html's
  const spotHref = id => PAGE_ID.test(id) ? `spot/${id}/` : `./?spot=${encodeURIComponent(id)}`;
  const recordHref = (id, iso) => `record.html#spot=${encodeURIComponent(id)}&day=${iso}`;
  const initial = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'narrow' });
  const shortDay = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short' });
  const ago = m => { const t = Math.max(0, Math.round(m)); return t < 60 ? `${t} min` : t % 60 ? `${Math.floor(t / 60)} h ${t % 60} min` : `${t / 60} h`; };
  const dated = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });   // "Thu 22 Oct"
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  // The day the link asks for (day=), while view draws, where it is one of the forecast's five days; else null,
  // and the rows give the usual headline. Set as levels.js sets its today (setToday).
  let DAY = null;

  // ------------------------------------------------------------------ the address
  // What the link holds: the spots, in order, each once, and the name. Read as lists.js reads a shared
  // list: a part that cannot be decoded is dropped, not fatal; at most LINK_SPOTS_MAX spots.
  // A briefing's link also holds its session's day (scripts/briefing.py, sites_url): &day=2026-10-22.
  function fromHash(hash) {
    const parts = String(hash || '').replace(/^#/, '').split('&').map(p => { const i = p.indexOf('='); return i < 0 ? [p, ''] : [p.slice(0, i), p.slice(i + 1)]; });
    const raw = k => { const p = parts.find(([key]) => key === k); return p ? p[1] : null; };
    const dec = s => { try { return decodeURIComponent(s); } catch (e) { return ''; } };
    const spots = raw('spots');
    const ids = spots === null ? [] : Li.listIds(spots.split(',').map(dec)).slice(0, Li.LINK_SPOTS_MAX);
    const day = raw('day');
    return { ids, name: Li.listName(dec((raw('name') || '').replace(/\+/g, ' '))), ...(ISO.test(day || '') ? { day } : {}) };
  }
  // The spots in the forecast, in the link's order, and the ids that are not.
  function pick(data, ids) {
    const by = new Map((data.spots || []).map(s => [s.id, s]));
    return { found: ids.filter(id => by.has(id)).map(id => by.get(id)), missing: ids.filter(id => !by.has(id)) };
  }

  // ------------------------------------------------------------------ a row
  // The five days as the list draws them: a bar a day in its level's colour, the day's letter under it.
  // Where nothing upstream can spill there is no level to colour, so the bars show the rain (40 mm fills
  // one), as the list's do. Read out as words, since the bars alone say nothing to a screen reader.
  // Today's letter is dark; with a day asked for, that day's letter instead, underlined (.wk.on).
  const mark = (x, i) => DAY ? (x.date === DAY ? ' on' : '') : i ? '' : ' first';
  function week(s) {
    const days = (s.days || []).slice(0, 5);
    if (!days.length) return '';
    if (!R.daily(s)) {
      if (!days.some(x => !nil(x.rain_48h_mm))) return '';
      const said = days.map(x => `${shortDay(x.date)} ${nil(x.rain_48h_mm) ? 'no figure' : Math.round(x.rain_48h_mm) + ' mm'}`).join(', ');
      return `<span class="week rain" role="img" aria-label="Rain in the 48 hours to midday: ${esc(said)}">${days.map((x, i) =>
        `<span class="wk${mark(x, i)}"><i style="--h:${nil(x.rain_48h_mm) ? 3 : Math.round(3 + 21 * Math.min(1, x.rain_48h_mm / 40))}px"></i><b>${initial(x.date)}</b></span>`).join('')}</span>`;
    }
    if (R.ORDER[R.level(s)] === undefined) return '';
    const lv = days.map(x => R.risk(s, x).level);
    const said = days.map((x, i) => `${shortDay(x.date)} ${lv[i] ? lv[i] + ' risk' : 'no forecast'}`).join(', ');
    return `<span class="week" role="img" aria-label="Pollution risk, next five days: ${esc(said)}">${days.map((x, i) =>
      `<span class="wk${mark(x, i)}"><i class="${lv[i] ? tone(lv[i]) : ''}"></i><b>${initial(x.date)}</b></span>`).join('')}</span>`;
  }
  // The headline, as the list and the spot's page give it ("High risk tomorrow", "High risk: rated poor"), and the
  // reason in one line: what set it and where the five days go, or, at a low spot, how many of the
  // overflows upstream are expected to spill today, in the spot page's words.
  // Then what it cannot count or check, short, as under the list's rows: the overflows in Wales, and at a
  // bathing water the EA's advice for today (levels.js, walesWords and eaUnchecked).
  const gaps = (s, onDay = false) => [R.walesWords(s, true), R.eaUnchecked(s) ? `${onDay ? 'EA advice on the day' : "Today's EA advice"} not checked: see the EA's page` : ''].filter(Boolean).map(w => w + '.').join(' ');
  function words(s) {
    const lv = R.level(s), [head, why] = R.headParts(s), g = gaps(s);
    if (R.COVER[lv]) return { head, tone: tone(lv), why: [lv === R.NO_OVERFLOWS || lv === R.NO_RIVER ? R.OTHER_RISKS : '', g].filter(Boolean).join(' ') };
    const next = R.daily(s) ? R.weekNext(s) : '';   // left out where the headline already says it ("Low risk now · Moderate risk on Wednesday")
    const parts = [why && cap(why), next && !head.includes(next) ? next : ''].filter(Boolean);
    const x0 = (s.days || [])[0], total = (s.upstream_summary || {}).overflows || 0;
    if (!parts.length && x0 && !nil(x0.risk)) { const k = O.spilling(x0, total); if (k) parts.push(`${cap(k)} today`); }
    return { head, tone: tone(lv), why: [parts.length ? parts.join('. ') + '.' : '', g].filter(Boolean).join(' ') };
  }
  // One day's level, for a briefing (scripts/briefing.py adds the session's day to the link): the day named
  // by its date, never "today" or "tomorrow", since the printed copy is kept and read on later days. On 20 Oct
  // 2026 a Thursday briefing's sheet said "Very high risk tomorrow", meaning Wednesday, beside an email and a
  // decision record that gave Thursday's "High risk". The level and its cause are dayHeadline's, which the
  // record and alerts.json use, then how many overflows are expected to spill that day, as on the record.
  function dayWords(s, iso) {
    const lv = R.dayLevel(s, iso), g = gaps(s, true);
    if (lv === R.NO_FORECAST && R.daily(s)) return { head: `No forecast for ${dated(iso)}`, lv, tone: 'na', why: ['Treat it as unknown, never as low.', g].filter(Boolean).join(' ') };
    if (R.COVER[lv]) return { head: R.COVER[lv], lv, tone: tone(lv), why: [lv === R.NO_OVERFLOWS || lv === R.NO_RIVER ? R.OTHER_RISKS : '', g].filter(Boolean).join(' ') };
    const line = R.dayHeadline(s, iso), i = line.indexOf(': ');
    const x = (s.days || []).slice(0, 5).find(d => d.date === iso), total = (s.upstream_summary || {}).overflows || 0;
    const k = R.daily(s) && x && !nil(x.risk) ? O.spilling(x, total) : '';
    const parts = [i < 0 ? '' : cap(line.slice(i + 2)), cap(k)].filter(Boolean);
    return { head: `${i < 0 ? line : line.slice(0, i)} on ${dated(iso)}`, lv, tone: tone(lv), why: [parts.length ? parts.join('. ') + '.' : '', g].filter(Boolean).join(' ') };
  }
  function row(s) {
    const w = DAY ? dayWords(s, DAY) : words(s), loc = s.location || {};
    const meta = [cap(s.kind || 'river'), s.source === 'designated' ? 'bathing water' : null, loc.watercourse || null].filter(Boolean).map(esc).join(' · ');
    const days = DAY ? [DAY] : (s.days || []).slice(0, 2).map(x => x.date), t = R.today();
    const rec = days.length ? days.map(iso => `<a href="${esc(recordHref(s.id, iso))}">${DAY ? dated(iso) : iso === t ? 'today' : 'tomorrow'}</a>`).join(' · ')
      : `<a href="${esc(recordHref(s.id, t))}">today</a>`;
    // With a day, the row says which spot, day and level it drew, for briefing.py to check against alerts.json.
    return `<li class="site"${DAY ? ` data-spot="${esc(s.id)}" data-day="${DAY}" data-level="${esc(w.lv)}"` : ''}><div class="s-place"><a class="s-name" href="${esc(spotHref(s.id))}">${esc(s.name)}</a><span class="s-meta">${meta}</span></div>`
      + `<div class="s-say"><p class="s-head ${w.tone}">${esc(w.head)}</p>${w.why ? `<p class="s-why">${esc(w.why)}</p>` : ''}`
      + `<p class="s-rec screen-only">Decision record: ${rec}</p></div>`
      + `<div class="s-week">${week(s)}</div></li>`;
  }

  // ------------------------------------------------------------------ the page
  // The issue time and the issue id once, with the app's notice when the forecast is over 8 h old (index.html,
  // STALE_MIN), and where the latest is. Printed, this line stands for the foot the page had, which said the
  // same, so the room goes to the credits (20 Oct 2026).
  function issue(data, now, base = '') {
    const m = (now - Date.parse(data.generated_at)) / 60000;
    const at = new Date(data.generated_at).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });
    return (m > O.STALE_MIN ? `<p class="notice" role="alert"><b>Stale.</b> This forecast is ${ago(m)} old (issued ${esc(at)}). The automatic update has not run since; treat everything below as out of date.</p>` : '')
      + `<p class="s-issued">Forecast issued ${esc(at)}${m <= O.STALE_MIN ? ` (${ago(m)} ago)` : ''}, issue id <b>${esc(P.issueId(data))}</b>. It is updated several times a day${base ? ` at ${esc(base.replace(/^https?:\/\//, '').replace(/\/$/, ''))}` : ''}. A forecast, not a water test: check the signs at the water before you swim.</p>`;
  }
  function view(data, st, now = Date.now(), base = '') {
    R.setToday(String(data.generated_at).slice(0, 10));
    DAY = st.day && (data.spots || []).some(s => (s.days || []).slice(0, 5).some(x => x.date === st.day)) ? st.day : null;
    if (!st.ids.length) return '<p>This link has no spots in it. Make one from a named list on the <a href="saved/">Saved page</a>, or pick several spots on the <a href="organisers.html#sites-maker">organisers\' page</a>.</p>';
    const { found, missing } = pick(data, st.ids);
    let h = issue(data, now, base);
    if (found.length) h += `<ol class="sites">${found.map(row).join('')}</ol>`;
    if (st.day && !DAY && found.length) h += `<p class="s-missing">${esc(dated(st.day))} is not in this forecast's five days, so the levels above are the usual ones, from today.</p>`;
    if (missing.length) h += `<p class="s-missing">Not found in this forecast: ${missing.map(id => `<b>${esc(id)}</b>`).join(', ')}. ${missing.length === 1 ? 'The spot may have been renamed or removed' : 'They may have been renamed or removed'}; the link still works for the rest.</p>`;
    if (!found.length) return h;
    return h + P.credits(data, found, base)
      + '<p class="actions screen-only"><button type="button" class="btn" id="print">Print this page</button></p>';
  }

  async function start() {
    const out = document.getElementById('sites'), h1 = document.getElementById('sites-h'), base = new URL('./', location.href).href;
    let data;
    try {
      const res = await fetch('data/spots-lite.json', { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (e) { out.innerHTML = '<p class="notice">The forecasts could not be loaded. Try again later.</p>'; return; }
    const draw = () => {
      const st = fromHash(location.hash), name = st.name || DEFAULT_NAME;
      h1.textContent = name; document.title = `${name} · SwimSignal`;
      out.innerHTML = view(data, st, Date.now(), base);
      const pr = document.getElementById('print'); if (pr) pr.addEventListener('click', () => window.print());
    };
    window.addEventListener('hashchange', draw);
    draw();
  }

  // ------------------------------------------------------------------ "Make a sites link", on the organisers' page
  // The spots come from the page's own spot list (#spot), once organisers.js has filled it. Picked spots
  // keep the order they were picked in, which is the order of the rows.
  function maker() {
    const box = document.getElementById('sites-maker'), list = document.getElementById('sm-list'), find = document.getElementById('sm-find');
    const nameIn = document.getElementById('sm-name'), count = document.getElementById('sm-count'), out = document.getElementById('sm-out');
    const sel = document.getElementById('spot');
    if (!box || !list || !sel) return;
    const picked = [];
    let spots = [];
    const norm = t => t.normalize('NFD').replace(/[̀-ͯ']/g, '').toLowerCase();
    const say = () => { count.textContent = picked.length ? `${picked.length} spot${picked.length === 1 ? '' : 's'} picked.` : 'No spots picked.'; };
    const draw = () => {
      const q = norm(find.value.trim());
      const shown = spots.filter(s => !q || norm(s.name).includes(q));
      list.innerHTML = shown.length ? shown.map(s => `<label><input type="checkbox" value="${esc(s.id)}"${picked.includes(s.id) ? ' checked' : ''}> ${esc(s.name)}</label>`).join('')
        : '<p class="hint">No spot matches.</p>';
    };
    const load = () => {
      spots = [...sel.options].filter(o => o.value).map(o => ({ id: o.value, name: o.textContent }));
      if (!spots.length) return false;
      if (sel.value && !picked.length) picked.push(sel.value);   // the spot already chosen above
      draw(); say(); return true;
    };
    if (!load()) new MutationObserver((_, ob) => { if (load()) ob.disconnect(); }).observe(sel, { childList: true });
    box.addEventListener('toggle', () => { if (box.open && !picked.length && sel.value) { picked.push(sel.value); draw(); say(); } });
    find.addEventListener('input', draw);
    list.addEventListener('change', e => {
      const id = e.target.value; if (!id) return;
      const i = picked.indexOf(id);
      if (e.target.checked && i < 0) picked.push(id); else if (!e.target.checked && i >= 0) picked.splice(i, 1);
      say(); out.textContent = '';
    });
    document.getElementById('sm-make').addEventListener('click', async () => {
      if (!picked.length) { out.textContent = 'Pick at least one spot first.'; return; }
      const url = new URL('sites.html', location.href).href + Li.sitesHash(nameIn.value, picked);
      let copied = false;
      try { await navigator.clipboard.writeText(url); copied = true; } catch (e) { copied = false; }
      out.innerHTML = `${copied ? 'Link copied' : 'Copy this link'}: <a href="${esc(url)}">${esc(url)}</a>`;
    });
  }

  return { fromHash, pick, week, words, row, issue, view, start, maker, DEFAULT_NAME };
})();

if (typeof module === 'object' && module.exports) module.exports = Sites;
else {
  if (document.getElementById('sites')) Sites.start();
  if (document.getElementById('sites-maker')) Sites.maker();
}
