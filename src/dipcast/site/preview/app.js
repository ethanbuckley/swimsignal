// SwimSignal, the redesign preview: the page. model.js (window.PV) works everything out; this file draws it and
// answers taps and keys. Two screens: the opening ("Where do you swim?") and a place. A place's page keeps one date
// for everything on it: the tabs, the answer, what is behind the level, the line upstream and the places elsewhere.
(function () {
'use strict';
const P = window.PV, app = document.getElementById('app'), saidEl = document.getElementById('said');
const { esc, capFirst, num } = P;
let DATA = null, HERO = {}, PLACES = null, POSTCODES = null, here = null, hereNote = '', route = null;
let miles = 20;
const expanded = new Set(), LINE_FIRST = 6;   // the places whose line upstream is shown whole
const details = new Map();                    // id -> { detail, up } once fetched; undefined while reading
const now = () => Date.now();
const spotOf = id => DATA.spots.find(p => p.id === id);
const say = t => { saidEl.textContent = ''; setTimeout(() => { saidEl.textContent = t; }, 60); };

// Saved places: ids kept on this device only. Its own key, so the preview never changes what the live site keeps.
const KEY = 'swimsignal.preview.places';
const kept = () => { try { const v = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(v) ? v.filter(x => typeof x === 'string') : []; } catch (e) { return []; } };
const keep = ids => { try { localStorage.setItem(KEY, JSON.stringify(ids.slice(0, 12))); } catch (e) { /* a private window: the page works without it */ } };

// ------------------------------------------------------------------------------------------------ icons and small parts
// The live site's stroke set: 1.75 px, round caps, inheriting the text colour.
const glyph = d => `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const IC = {
  search: glyph('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>'),
  pin: glyph('<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>'),
  back: glyph('<path d="m14.5 5-7 7 7 7"/>'),
  go: glyph('<path d="m9.5 5 7 7-7 7"/>'),
  down: glyph('<path d="m5 9.5 7 7 7-7"/>'),
  save: glyph('<path d="M6 3h12v18l-6-4-6 4Z"/>'),
  share: glyph('<path d="M12 15V3.5M8 7l4-3.5L16 7"/><path d="M6 11.5H5a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7.5a1 1 0 0 0-1-1h-1"/>'),
  water: glyph('<path d="M3 9c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0 3-1.2 4.5 0 3 1.2 4.5 0M3 14c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0 3-1.2 4.5 0 3 1.2 4.5 0M3 19c1.5-1.2 3-1.2 4.5 0s3 1.2 4.5 0 3-1.2 4.5 0 3 1.2 4.5 0"/>'),
};
const MARK = '<svg viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" fill="#0f5a61"/><path d="M430-20C330 110 470 230 300 290S110 380 190 540" fill="none" stroke="#5CC2B5" stroke-width="70" stroke-linecap="round"/><circle cx="318" cy="138" r="38" fill="#F08A4B"/><circle cx="165" cy="358" r="46" fill="none" stroke="#fff" stroke-width="22"/></svg>';
const link = r => P.queryFor(r);
const bar = (onPlace = false) => `<header class="bar"><a class="brand" href="${link({ day: route.day })}">${MARK}SwimSignal</a><span class="tag">Preview</span>
  <nav aria-label="Site">${onPlace ? `<a class="hbtn" href="${link({ day: route.day })}#find" aria-label="Find another place">${IC.search}<span class="wide-only">Find a place</span></a>` : ''}
  <a class="hlink wide-only" href="../verification.html">Accuracy</a><a class="hlink wide-only" href="../about.html">About</a><a class="hlink wide-only" href="../">Current site</a></nav></header>`;
const photoOf = id => HERO[id] || null;
const thumb = id => { const p = photoOf(id);
  return p ? `<img class="thumb" src="../guides/photos/${encodeURIComponent(p.file)}" width="${p.w}" height="${p.h}" alt="" loading="lazy" decoding="async">` : `<span class="thumb none">${IC.water}</span>`; };
// A place's five days as five marks, the day shown ringed. The words beside it carry the level; these are a glance.
const week = r => r.week.length ? `<span class="week" aria-hidden="true">${r.week.map(d => `<i class="${d.cls}${d.on ? ' on' : ''}"></i>`).join('')}</span>` : '';
const rowHtml = (r, day) => `<li><a class="row" href="${link({ id: r.id, day })}">${thumb(r.id)}<span class="row-main"><b>${esc(r.name)}</b>`
  + `<span class="row-level ${r.cls}">${esc(r.words)}</span>`
  + (r.notice ? `<span class="row-notice">Official: ${esc(r.notice)}</span>` : '')
  + `<span class="row-sub">${esc([r.said, r.water || (r.said ? '' : r.area)].filter(Boolean).join(' · '))}</span></span>${week(r)}</a></li>`;
const rows = (list, day) => `<ul class="rows">${list.map(r => rowHtml(r, day)).join('')}</ul>`;
// The day control: every date the forecast covers. On the opening it sets the day the lists show; on a place, the page.
function dayTabsHtml(tabs, day, label, hrefFor) {
  return `<nav class="daytabs" aria-label="${esc(label)}"><ol>${tabs.map(t => { const on = t.date === day;
    return `<li><a class="daytab ${t.cls || ''}${on ? ' on' : ''}" href="${hrefFor(t.date)}" data-day="${t.date}"${on ? ' aria-current="true"' : ''} aria-label="${esc(t.said || P.longDate(t.date))}">`
      + `<span class="dt-top"><span class="dt-name">${esc(t.name)}</span> <span class="dt-dom">${t.dom}</span></span>${t.short ? `<span class="dt-mark" aria-hidden="true"></span><span class="dt-level">${esc(t.short)}</span>` : ''}</a></li>`; }).join('')}</ol></nav>`;
}
const stale = () => { const i = P.issuedWords(DATA, now()); return i.stale ? `<p class="notice" role="note"><b>Older forecast.</b> ${esc(i.note)}</p>` : ''; };
const foot = () => { const c = (DATA && DATA.credits) || {};
  return `<footer class="foot"><p>This is a preview of a redesign, kept beside <a href="../">the current SwimSignal</a>. Both read the same forecast. Saved places stay on this device.</p>
    <p><a href="../methods.html">Method and limits</a> · <a href="../verification.html">How accurate it has been</a> · <a href="../privacy.html">Privacy</a> · <a href="../terms.html">Terms</a></p>
    <details><summary>Data sources and licences</summary><p>${esc(c.attribution || '')}</p><p>${esc(c.modified || '')} ${esc(c.endorsement || '')} <a href="../terms.html#data">Full credits</a></p></details></footer>`; };
// One quiet line under a photo, the day first since the photo is of that day. Each part keeps to one line with its
// dot after it, so a narrow phone's second line never starts with a dot (the live page's rule).
const credit = p => [`Photo from ${esc(P.shortDate(p.taken))}`, esc(p.credit), p.licence_name ? `<a href="${esc(p.licence)}">${esc(p.licence_name)}</a>` : '',
  P.httpsLink(p.source) ? `<a href="${esc(p.source)}">Geograph</a>` : ''].filter(Boolean).map((t, i, a) => `<span class="cr">${t}${i < a.length - 1 ? ' ·' : ''}</span>`).join(' ');

// ------------------------------------------------------------------------------------------------ the opening
const homeDay = () => { const ds = P.dates(DATA); return ds.includes(route.day) ? route.day : ds[0] || today(); };
function homeHtml() {
  const day = homeDay(), tabs = P.dates(DATA).map(d => ({ date: d, name: P.tabName(d), dom: new Date(d + 'T12:00:00').getDate() }));
  const n = DATA.spots.length, issued = P.issuedWords(DATA, now());
  return `${bar()}<main id="main" class="home">
    <section class="opening">
      <h1 id="title" tabindex="-1">Where do you swim?</h1>
      <p class="lede">Sewage pollution risk for the next five days at ${n} rivers and lakes. A forecast, not a water test.</p>
      <form class="ask" role="search" onsubmit="return false" id="find">
        <label class="sr" for="q">A river, lake, town or postcode</label>
        <div class="field">${IC.search}<input id="q" type="search" placeholder="River, lake, town or postcode" autocomplete="off" autocapitalize="none" spellcheck="false" enterkeyhint="search" value="${esc(route.q || '')}">
          </div>
        <p class="near"><button type="button" class="textbtn" data-do="locate">${IC.pin}Places near me</button><span class="meta" id="here-note">${esc(hereNote)}</span></p>
      </form>
    </section>
    ${stale()}
    <div class="home-body">
      ${dayTabsHtml(tabs, day, 'Day shown', d => link({ q: route.q, area: route.area, day: d }))}
      <div id="results">${resultsHtml(day)}</div>
      <p class="issued">${esc(issued.text)}. Levels are for ${esc(P.headDay(day) === 'today' ? 'today' : P.longDate(day))}.</p>
    </div>
    ${foot()}
  </main>`;
}
// Everything under the day control: what was searched for, or a picked area, or the first look.
function resultsHtml(day) {
  const q = (route.q || '').trim(); let out = '';
  if (here) out += `<section class="block"><h2>Nearest to you</h2>${rows(P.nearest(DATA.spots, here, day, 6), day)}<p class="meta">Miles in a straight line.</p></section>`;
  if (q.length >= 2) {
    const hits = P.findSpots(DATA.spots, q).slice(0, 8).map(p => P.placeRow(p, day));
    if (hits.length) out += `<section class="block"><h2>${hits.length === 1 ? 'One place matches' : `${hits.length} places match`}</h2>${rows(hits, day)}</section>`;
    const pc = P.postcodeKeys(q); let points = [];
    if (pc && POSTCODES) { const at = (pc.sector && POSTCODES.sectors[pc.sector]) || POSTCODES.districts[pc.district];
      if (at) points.push({ name: pc.sector && POSTCODES.sectors[pc.sector] ? pc.sector : pc.district, lat: at[0], lon: at[1] }); }
    if (!points.length && PLACES) points = P.findTowns(PLACES.places, q);
    const shown = new Set(hits.map(p => p.id));
    for (const t of points) out += `<section class="block"><h2>Near ${esc(t.name)}</h2>${rows(P.nearest(DATA.spots.filter(p => !shown.has(p.id)), t, day, 5), day)}<p class="meta">Miles in a straight line from ${esc(t.name)}.</p></section>`;
    if (!hits.length && !points.length) out += `<p class="none">${(pc ? POSTCODES : PLACES) ? `Nothing found for “${esc(q)}”. Try a river, a lake, a town or the first half of a postcode.` : 'Looking…'}</p>`;
    return out;
  }
  if (route.area) {
    const ps = DATA.spots.filter(p => p.area === route.area);
    if (ps.length) return `<section class="block area-page"><p class="backline"><a href="${link({ day })}">${IC.back}All areas</a></p><h2 class="area-h" tabindex="-1">${esc(route.area)}</h2>
      ${P.waters(ps, day).map(w => `<div class="water${w.ordered ? ' ordered' : ''}">${w.rows.length > 1 ? `<h3>${esc(w.name)}${w.ordered ? ' <span class="meta">from the top of the river down</span>' : ''}</h3>` : ''}${rows(w.rows.map(r => ({ ...r, area: '' })), day)}</div>`).join('')}</section>`;
  }
  const mine = kept().map(spotOf).filter(Boolean);
  if (mine.length) out += `<section class="block"><h2>Your places</h2>${rows(mine.map(p => P.placeRow(p, day)), day)}</section>`;
  const used = [];
  out += `<section class="block"><h2>${mine.length || here ? 'Every area' : 'Or pick an area'}</h2><ul class="areas">${P.areas(DATA.spots, day).map(a => {
    const id = a.ids.find(i => photoOf(i) && photoOf(i).w / photoOf(i).h >= 1.3) || a.ids.find(photoOf), p = id && photoOf(id);
    if (p) used.push([id, p]);
    return `<li><a class="area" href="${link({ area: a.name, day })}">${p ? `<img src="../guides/photos/${encodeURIComponent(p.file)}" width="${p.w}" height="${p.h}" alt="" loading="lazy" decoding="async">` : `<span class="noimg">${IC.water}</span>`}
      <span class="area-name">${esc(a.name)}</span><span class="area-n">${a.n} places · ${a.low} at low risk ${esc(dayWord(day))}</span></a></li>`; }).join('')}</ul>
    <details class="credits"><summary>Photo credits</summary><ul>${used.map(([id, p]) => `<li>${esc(spotOf(id).name)}: ${credit(p)}</li>`).join('')}</ul><p>Older photos, each of one day. The place may have changed.</p></details></section>`;
  return out;
}
const loadJson = async path => { const r = await fetch(path); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); };
async function typed(v) {
  route.q = v; route.area = '';
  history.replaceState(null, '', link(route));
  const day = homeDay(), box = document.getElementById('results'); if (box) box.innerHTML = resultsHtml(day);
  if (v.trim().length < 2) return;
  try {
    if (P.postcodeKeys(v) && !POSTCODES) POSTCODES = await loadJson('../data/postcodes.json');
    else if (!PLACES) PLACES = await loadJson('../data/places.json');
  } catch (e) { PLACES = PLACES || { places: [] }; POSTCODES = POSTCODES || { sectors: {}, districts: {} }; }
  const again = document.getElementById('results'); if (again && route.q === v) again.innerHTML = resultsHtml(day);
}
function locate(after) {
  const note = t => { hereNote = t; const n = document.getElementById('here-note'); if (n) n.textContent = t; };
  if (!navigator.geolocation) { note('This browser cannot give a location. Type a town or postcode instead.'); return; }
  note('Asking this browser where you are…');
  navigator.geolocation.getCurrentPosition(p => { here = { lat: p.coords.latitude, lon: p.coords.longitude }; hereNote = 'Using where you are. It stays in this browser.'; after(); },
    () => note('No location was given. Type a town or postcode instead.'), { maximumAge: 600000, timeout: 15000 });
}

// ------------------------------------------------------------------------------------------------ one place
const placeDay = s => { const ds = P.dates(DATA); return ds.includes(route.day) ? route.day : ds[0] || today(); };
function kindLine(s) {
  const lake = s.kind === 'lake' && !/\b(water|mere|tarn|lake|loch|pond|reservoir|llyn)\b/i.test(s.name + ' ' + (s.river || ''));
  return [s.river, lake ? 'Lake' : '', s.area, s.source === 'designated' ? 'Designated bathing water' : ''].filter(Boolean).join(' · ');
}
function officialHtml(o) {
  return !o ? '' : `<section class="official" aria-labelledby="official-h"><h2 id="official-h">${esc(o.title)}</h2>`
    + o.items.map(i => `<p class="o-line">${esc(i.line)}</p><p class="o-src">${i.link ? `<a href="${esc(i.link)}">Open the ${esc(i.publisher)} page</a>. ` : ''}${esc(i.checked)}</p>`).join('')
    + `<p class="o-first">${esc(o.first)}</p></section>`;
}
function answerHtml(s, day) {
  const a = P.answer(s, day, DATA, now()), o = P.official(s), issued = P.issuedWords(DATA, now()), steps = P.nextSteps(s, day, DATA.spots, miles);
  const [first, ...rest] = String(a.act || '').split(/(?<=[.:])\s+/), raised = rank(a.level) >= 1 || !!o;
  const btn = (st, primary) => st.kind === 'nearby' ? `<a class="btn${primary ? ' primary' : ''}" href="#nearby" data-do="jump" data-to="nearby">${esc(st.label)}${IC.down}</a>`
    : st.kind === 'day' ? `<a class="btn${primary ? ' primary' : ''}" href="${link({ id: s.id, day: st.date })}" data-day="${st.date}">${esc(st.label)}</a>`
    : `<p class="act-none">${esc(st.label)}. <a href="#nearby" data-do="jump" data-to="nearby">See what is nearby</a></p>`;
  const unchecked = a.unchecked ? `<p class="unchecked">${esc(a.unchecked.text)} ${a.unchecked.link ? `<a href="${esc(a.unchecked.link)}">${esc(a.unchecked.words)}</a>.` : ''}</p>` : '';
  return `<section class="answer" aria-labelledby="answer-h">
    <p class="when" id="when">${esc(a.dateLabel)}${a.everyDay ? ' <span class="when-note">The level here is the same every day.</span>' : ''}</p>
    ${a.lead ? `<p class="lead">${esc(a.lead)}</p>` : ''}
    <h2 class="level ${a.cls}" id="answer-h">${esc(a.head)}</h2>
    ${a.modelled ? `<p class="why">${esc(a.modelled)}</p>` : ''}
    ${a.why.length ? `<p class="why">${a.why.map(esc).join(' ')}</p>` : ''}
    ${a.clears ? `<p class="why">${esc(a.clears)}</p>` : ''}
    ${a.apart ? `<p class="apart">${esc(a.apart)}</p>` : ''}
    ${raised ? `<div class="act"><p class="act-line"><b>${esc(first)}</b>${rest.length ? ' ' + esc(rest.join(' ')) : ''}</p>${steps.length ? `<div class="act-go">${steps.map((st, i) => btn(st, i === 0)).join('')}</div>` : ''}${unchecked}</div>`
      : `<p class="act-plain">${esc(a.act)} <a href="#nearby" data-do="jump" data-to="nearby">Compare places nearby</a></p>${unchecked}`}
    ${a.notes.map(t => `<p class="scope">${esc(t)}</p>`).join('')}
    <p class="issued">${esc(issued.text)} · A forecast, not a water test: check the signs at the water.</p>
  </section>`;
}
// The day's conditions at the place: rain, air, daylight and, for today, the water's temperature. Under the answer on
// a phone; under the photo on a wide screen, where they describe the place as the photo does.
function condsHtml(s, day) {
  const a = P.answer(s, day, DATA, now());
  return a.conditions.length ? `<section class="condbox" aria-label="Conditions ${esc(dayWord(day))}"><h2 class="conds-h">Conditions ${esc(dayWord(day))}</h2><dl class="conds">${a.conditions.map(c => `<div><dt>${esc(c.k)}</dt><dd>${esc(c.v)}${c.note ? `<span>${esc(c.note)}</span>` : ''}</dd></div>`).join('')}</dl></section>` : '';
}
function behindHtml(s, day) {
  const L = P.ledger(s, day, DATA, now());
  // The score on its four bands (levels.js, SPILL_CUTS): the band it falls in takes its colour, a mark sits at the
  // score, and on days 3 to 5 a line under the bands gives the range from the other rain runs.
  const meter = (m, c) => { const edges = [0, ...m.cuts, 100], names = ['low', 'moderate', 'high', 'very high'];
    const at = names.findIndex((_, i) => m.score >= edges[i] && (m.score < edges[i + 1] || i === 3));
    return `<span class="meter" aria-hidden="true">${names.map((n, i) => `<i class="seg${i === at ? ' on ' + c : ''}" style="width:${edges[i + 1] - edges[i]}%"></i>`).join('')}<i class="at" style="left:${Math.min(99, Math.max(1, m.score))}%"></i>${m.band ? `<i class="band" style="left:${m.band[0]}%;width:${Math.max(2, m.band[1] - m.band[0])}%"></i>` : ''}</span>
      <span class="meter-key" aria-hidden="true">${names.map((n, i) => `<span style="width:${edges[i + 1] - edges[i]}%">${n}</span>`).join('')}</span>`; };
  // The score on each of the five days, the day shown marked: at a water rated poor every tab reads "High", and this
  // is where the days differ.
  const spark = w => `<span class="spark" role="img" aria-label="${esc('Sewage spill risk by day: ' + w.map(d => `${d.name} ${d.score === null ? 'none' : d.score}`).join(', '))}">${w.map(d =>
    `<span class="sp${d.on ? ' on' : ''}"><i class="${d.cls}" style="height:${d.score === null ? 2 : Math.max(3, Math.round(d.score * 0.56))}px"></i><b>${d.score === null ? '–' : d.score}</b><span>${esc(d.name)}</span></span>`).join('')}</span>`;
  return `<section class="behind" aria-labelledby="behind-h"><h2 id="behind-h">Behind the level</h2>
    <dl class="ledger">${L.map(r => `<div class="lg lg-${r.key}"><dt>${esc(r.label)}</dt>
      <dd>${r.value ? `<span class="lg-value ${r.cls}">${esc(r.value)}${r.word ? `<span class="lg-word"> · ${esc(r.word)} on its own</span>` : ''}</span>` : ''}${r.meter ? meter(r.meter, r.cls) : ''}${r.lines.slice(0, 1).map(t => `<span class="lg-line">${esc(t)}</span>`).join('')}${r.week ? spark(r.week) : ''}${r.lines.slice(1).map(t => `<span class="lg-line dim">${esc(t)}</span>`).join('')}</dd></div>`).join('')}</dl>
    <p class="meta"><a href="../methods.html">How the forecast is made</a> · <a href="../verification.html">How accurate it has been</a></p></section>`;
}
// The space before a stop on the line, in px, from the water between it and the one before: the square root keeps a
// 30 km gap readable beside a 300 m one.
const gapPx = km => Math.round(Math.min(72, 6 + 16 * Math.sqrt(Math.max(0, km))));
function upstreamHtml(s, day) {
  const got = details.get(s.id), head = '<h2 id="upstream-h">Upstream</h2>';
  if (!daily(s)) return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}<p class="sec-lede">${isolated(s) ? 'No river or beck is drawn into this lake, so no monitored overflow can be traced to it.' : 'The trace found no monitored storm overflow on the river network upstream of here.'}</p>
    <ol class="line"><li class="stop is-here"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><b>${esc(s.name)}</b><span class="st">This place.</span></span></li>
    <li class="stop is-end" style="margin-top:28px"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><span class="st">Nothing monitored upstream within ${(s.assumptions || {}).max_upstream_km ?? 60} km. Unmonitored outfalls and runoff are not traced.</span></span></li></ol></section>`;
  if (got === undefined) return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}<p class="meta">Reading the overflows upstream…</p></section>`;
  const L = P.riverLine(s, got && got.up, got && got.detail, DATA.spots, now(), day);
  if (!L.items.length) return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}<p class="sec-lede">The list of overflows upstream could not be read just now. Try again in a minute.</p></section>`;
  // A long line is cut after the nearest few: the Avon at Warleigh Weir has 185 overflows upstream. What is left out
  // is counted by its status, and any overflow discharging further up is still drawn, so nothing spilling is hidden.
  const whole = expanded.has(s.id) || L.items.length <= LINE_FIRST + 2;
  const shown = whole ? L.items : L.items.slice(0, LINE_FIRST), rest = whole ? [] : L.items.slice(LINE_FIRST);
  const restO = rest.filter(i => i.kind === 'overflow'), count = m => restO.filter(i => i.mark === m).length;
  let prev = 0;
  const item = (it, tail = false) => { const gap = it.km - prev; prev = it.km; const mt = tail ? 16 : gapPx(gap);
    if (it.kind === 'place') return `<li class="stop is-place" style="margin-top:${mt}px"><span class="km">${esc(it.kmSaid)}</span><span class="node" aria-hidden="true"></span><span class="stop-body"><a href="${link({ id: it.id, day })}"><b>${esc(it.name)}</b></a><span class="st">Another listed place. <span class="${it.cls}">${esc(it.level)}</span> ${esc(dayWord(day))}.</span></span></li>`;
    const more = [it.company + (it.own ? `, as “${it.own}”` : ''), it.into ? `Into ${it.into}` : '', capFirst(it.where),
      it.spills === null ? '' : `${num(it.spills, 1)} spills a year, long-term average`, it.hours === null ? '' : `${num(it.hours, 1)} hours spilling in its latest annual return`,
      it.weight === null ? '' : `Model weight here: ${Math.round(it.weight * 100)}%`, it.upgrade && it.upgrade.stage ? `Upgrade: ${it.upgrade.stage}, by the company's own page` : ''].filter(Boolean);
    return `<li class="stop is-${it.mark}" style="margin-top:${mt}px"><span class="km">${esc(it.kmSaid)}</span><span class="node" aria-hidden="true"></span><span class="stop-body">
      <b>${esc(it.name)}</b><span class="st">${esc(capFirst(it.status))}${it.ended ? `. Last spill ended ${esc(it.ended)}` : ''}.${it.long ? ' ' + esc(it.long) : ''}</span>
      <span class="st st-row">${it.chance === null ? '' : `<span>Chance of a spill ${esc(dayWord(day))}: ${it.chance < 0.01 ? 'under 1' : Math.round(it.chance * 100)}%</span>`}<button type="button" class="textbtn" data-do="more" aria-expanded="false" aria-label="Details of ${esc(it.name)}">Details</button></span><span class="more-box" hidden>${more.map(esc).join('<br>')}<br><a href="../overflow/${encodeURIComponent(it.id)}/">This overflow's record</a></span></span></li>`; };
  const below = L.below.length ? `<p class="below">Downstream of here: ${L.below.map(b => `<a href="${link({ id: b.id, day })}">${esc(b.name)}</a> <span class="meta">${num(b.km, 1)} km, ${esc(b.level.toLowerCase())} ${esc(dayWord(day))}</span>`).join('; ')}.</p>` : '';
  const counts = [L.spilling ? `<b class="lv-veryhigh">${L.spilling} discharging now</b>` : 'none discharging now', `${L.quiet} not discharging at the last poll`, L.unknown ? `${L.unknown} with no current reading` : ''].filter(Boolean).join(', ');
  return `<section class="upstream" id="upstream" aria-labelledby="upstream-h">${head}
    <p class="sec-lede">${L.total === 1 ? 'One monitored storm overflow' : `${L.total} monitored storm overflows`} within ${L.reach} km upstream: ${counts}.${L.more ? ' ' + esc(L.more) : ''}</p>
    <ol class="line" aria-label="The water upstream of here, nearest first">
      <li class="stop is-here"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><b>${esc(s.name)}</b><span class="st">This place. Each step down the line is further upstream.</span></span></li>
      ${shown.map(it => item(it)).join('')}
      ${rest.length ? `<li class="stop is-rest" style="margin-top:20px"><span class="km"></span><span class="node" aria-hidden="true"></span><span class="stop-body"><b>${restO.length} more further upstream</b><span class="st">${[count('spilling') ? `${count('spilling')} discharging, drawn below` : '', count('quiet') ? `${count('quiet')} not discharging at the last poll` : '', count('unknown') ? `${count('unknown')} with no current reading` : ''].filter(Boolean).join('; ')}.</span><button type="button" class="textbtn" data-do="all">Show all ${L.total}</button></span></li>` : ''}
      ${rest.filter(i => i.mark === 'spilling').map(it => item(it, true)).join('')}
      <li class="stop is-end" style="margin-top:20px"><span class="km">${L.reach} km</span><span class="node" aria-hidden="true"></span><span class="stop-body"><span class="st">The trace stops here. Overflows further up are not counted.</span></span></li>
    </ol>
    <p class="key"><span class="k is-spilling"><i></i>discharging</span><span class="k is-quiet"><i></i>not discharging at the last poll</span><span class="k is-unknown"><i></i>no current reading</span></p>
    ${below}
    <p class="meta">A monitor reports when an overflow spills, not how much or what is in it. Live readings are from the last poll${P.pollAt(DATA) ? ` (${esc(P.pollAt(DATA))})` : ''}, whichever day is shown. <a href="../spot/${encodeURIComponent(s.id)}/">These overflows on a map, on the current site</a></p></section>`;
}
function nearbyHtml(s, day) {
  const from = here || s, E = P.elsewhere(DATA.spots, from, day, miles, here ? null : s.id, dayLevel(s, day)), when = dayWord(day);
  const group = (title, list, note = '') => list.length ? `<h3>${esc(title)}</h3>${note ? `<p class="meta">${esc(note)}</p>` : ''}${rows(list, day)}` : '';
  const chip = m => `<button type="button" class="chip${miles === m ? ' on' : ''}" data-do="miles" data-miles="${m}" aria-pressed="${miles === m}">${m} miles</button>`;
  return `<section class="nearby" id="nearby" aria-labelledby="nearby-h"><h2 id="nearby-h" tabindex="-1">Elsewhere ${esc(when)}</h2>
    <p class="sec-lede">${E.widened ? 'The nearest listed places to' : `Listed places within ${E.miles} miles of`} ${here ? 'where you are' : esc(s.name)}, ${esc(day === today() ? 'today' : P.longDate(day))}.</p>
    <p class="chips" role="group" aria-label="How far">${[10, 20, 40].map(chip).join('')}
      ${here ? '<button type="button" class="textbtn" data-do="unlocate">Measure from this place</button>' : `<button type="button" class="textbtn" data-do="locate">${IC.pin}From where I am</button>`}</p>
    ${group(`Low risk ${when}, nearest first`, E.low) || `<p class="none">No listed place ${E.widened ? 'nearby' : `within ${E.miles} miles`} is forecast at low risk ${esc(when)}.</p>`}
    ${E.lowerThan ? group(`Moderate risk ${when}: lower than here`, E.moderate) : ''}
    ${group('No daily level', E.plain, 'No monitored overflow was found upstream of these. That is not the same as low risk.')}
    ${group('Under official advice', E.advice, 'Follow the advice first, whatever the level beside it.')}
    ${E.folded.length ? `<details class="raised"><summary>${E.folded.length === 1 ? 'One place' : `${E.folded.length} places`} ${E.lowerThan ? 'at high or very high risk' : 'at moderate risk or higher'} ${esc(when)}</summary>${rows(E.folded, day)}</details>` : ''}
    <p class="meta">Miles in a straight line. Low risk is the forecast for sewage pollution, not a safety check.</p></section>`;
}
const TOPICS = { parking: 'Parking', transport: 'Bus and train', path: 'Path to the water', entry: 'Getting in', exit: 'Getting out', toilets: 'Toilets', changing: 'Changing',
  fees: 'Fees and booking', hours: 'Opening times', rules: 'Who can swim', launch: 'Launching a boat or board', carry: 'Carrying to the water', paddle: 'Paddling here' };
function placeFactsHtml(s) {
  const got = details.get(s.id), g = got && got.detail ? got.detail.guide : null, hero = photoOf(s.id), facts = [], guide = [];
  const c = s.classification;
  if (c && c.class) { const poor = String(c.class).toLowerCase() === 'poor';
    facts.push(['Rating', `Rated <b>${esc(String(c.class).toLowerCase())}</b> for ${esc(c.year)} by the Environment Agency. ${poor ? esc(poorAdvice(today())) + ' ' : ''}${P.httpsLink(c.url) ? `<a href="${esc(c.url)}">Its Environment Agency page</a>` : ''}`]); }
  else if (s.sepa && s.sepa.rating) facts.push(['Rating', `Rated <b>${esc(String(s.sepa.rating.value).toLowerCase())}</b> for ${esc(s.sepa.rating.year)} by SEPA. ${P.httpsLink(s.sepa.page) ? `<a href="${esc(s.sepa.page)}">Its SEPA page</a>` : ''}`]);
  const ls = s.lab_sample;
  if (ls && ls.taken_at && !P.isNil(ls.ecoli)) facts.push(['Last sample', `${esc(ls.qualifier || '')}${num(ls.ecoli)} E. coli per 100 ml on ${esc(P.shortDate(String(ls.taken_at).slice(0, 10)))}, by the Environment Agency. The line for a rating of sufficient is 900.`
    + (s.ecoli_typical ? ` Of ${s.ecoli_typical.samples} samples from ${s.ecoli_typical.first_year} to ${s.ecoli_typical.last_year}, ${s.ecoli_typical.over_line} were over it.` : '')]);
  if (s.algae && s.algae.date && s.algae.phrase) facts.push(['Algae', `At the Environment Agency's last check, ${esc(P.shortDate(s.algae.date))}: ${esc(s.algae.phrase)}. The check cannot tell blue-green algae from harmless kinds.`]);
  const rs = s.river_state;
  if (rs && !P.isNil(rs.level_m) && !rs.stale) { const word = ({ low: 'low water', normal: 'its usual level', high: 'high water', 'very high': 'very high water, above its usual range' })[rs.label];
    facts.push([rs.water === 'lake' ? 'Lake level' : 'River level', `${num(rs.level_m, 2)} m${word ? `, ${word}` : ''}. Gauge at ${esc(rs.station)}, ${esc(rs.distance_km)} km away${rs.same_river === false ? ', on a different watercourse' : ''}. Not part of the level.`]); }
  for (const f of s.flood_alerts || []) facts.push([esc(f.severity || 'Flood alert'), `${esc(f.area || '')}, from the Environment Agency. ${P.httpsLink(f.url) ? `<a href="${esc(f.url)}">Read it</a>` : ''}`]);
  if (s.access && s.access.text) facts.push(['Access', `${esc(s.access.text)} ${P.httpsLink(s.access.url) ? `<a href="${esc(s.access.url)}">Source</a>` : ''}`]);
  for (const f of (g && g.facts) || []) guide.push([TOPICS[f.topic] || esc(capFirst(f.topic)), `${esc(f.text)} ${f.status === 'confirmed' ? (P.httpsLink(f.source) ? `<a href="${esc(f.source)}">${esc(f.source_name || 'Source')}</a>` : esc(f.source_name || '')) : 'A swimmer’s suggestion, not checked.'}`]);
  const merge = list => { const out = []; for (const [k, v] of list) { const last = out[out.length - 1]; if (last && last[0] === k) last[1].push(v); else out.push([k, [v]]); } return out; };
  const dl = list => `<dl class="facts">${merge(list).map(([k, vs]) => `<div><dt>${k}</dt>${vs.map(v => `<dd>${v}</dd>`).join('')}</div>`).join('')}</dl>`;
  const photos = (g && Array.isArray(g.photos) ? g.photos : []).filter(p => !hero || p.file !== hero.file);
  return `<section class="theplace" id="place" aria-labelledby="place-h"><h2 id="place-h">The place</h2>
    ${got === undefined ? '<p class="meta">Reading what is known about this place…</p>' : ''}
    ${facts.length ? dl(facts) : got === undefined ? '' : '<p class="sec-lede">No rating, sample or gauge is recorded for this place.</p>'}
    ${guide.length ? `<details class="guide"><summary>Getting there and getting in: ${guide.length} checked notes</summary>${dl(guide)}${g.checked ? `<p class="meta">Checked on ${esc(P.shortDate(g.checked))}${g.how === 'desk' ? ', from published sources, not on a visit' : ''}.</p>` : ''}</details>` : ''}
    ${photos.length ? `<div class="photos">${photos.map(p => `<figure><img src="../guides/photos/${encodeURIComponent(p.file)}" width="${Number(p.w) || 640}" height="${Number(p.h) || 480}" alt="${esc(p.caption || s.name)}" loading="lazy" decoding="async"><figcaption>${esc(p.caption || '')} ${credit({ ...p, licence_name: p.licence && /by-sa\/2\.0/.test(p.licence) ? 'CC BY-SA 2.0' : '' })}</figcaption></figure>`).join('')}</div>` : ''}
    <p class="meta">${esc(s.source === 'openstreetmap' ? 'This place is from OpenStreetMap, © OpenStreetMap contributors.' : String(s.notes || '').replace(/([^.])$/, '$1.'))} A listing is not a right to swim or a check that it is allowed. <a href="../spot/${encodeURIComponent(s.id)}/">This place on the current site</a></p></section>`;
}
function placeHtml() {
  const s = spotOf(route.id);
  if (!s) return `${bar(true)}<main id="main" class="home"><section class="opening"><h1 id="title" tabindex="-1">That place is not listed</h1><p class="lede">The link names a place this forecast does not cover, or one that has been removed.</p><p><a class="btn primary" href="./">Find a place</a></p></section>${foot()}</main>`;
  const day = placeDay(s), hero = photoOf(s.id), isKept = kept().includes(s.id), o = P.official(s);
  const missed = route.day && route.day !== day ? `<p class="notice" role="note"><b>This link was for ${esc(P.longDate(route.day))}.</b> That day is no longer in the forecast, so this shows today.</p>` : '';
  const tools = `<div class="tools"><a class="tool" href="${link({ day })}">${IC.back}<span>All places</span></a><span class="tools-r"><button type="button" class="tool" data-do="keep" aria-pressed="${isKept}">${IC.save}<span>${isKept ? 'Saved' : 'Save'}</span></button><button type="button" class="tool" data-do="share" aria-label="Share this forecast">${IC.share}</button></span></div>`;
  return `${bar(true)}<main id="main" class="place${hero ? ' has-photo' : ''}">
    <div class="top">
      ${hero ? `<figure class="hero"><img src="../guides/photos/${encodeURIComponent(hero.file)}" width="${hero.w}" height="${hero.h}" alt="${esc(String(hero.caption || s.name).replace(/[.\s]+$/, ''))}." decoding="async" fetchpriority="high">${tools}<figcaption>${credit(hero)}</figcaption></figure>` : tools}
      <div class="head"><h1 id="title" tabindex="-1">${esc(s.name)}</h1><p class="kind">${esc(kindLine(s))}</p><p class="meta" id="tool-said" role="status"></p></div>
      <div class="first">${stale()}${missed}${officialHtml(o)}
        <i class="tabs-top" aria-hidden="true"></i>${dayTabsHtml(P.dayTabs(s, DATA), day, 'Day', d => link({ id: s.id, day: d }))}
        ${answerHtml(s, day)}</div>
      ${condsHtml(s, day)}
    </div>
    <div class="more">${behindHtml(s, day)}${upstreamHtml(s, day)}${nearbyHtml(s, day)}</div>
    ${placeFactsHtml(s)}
    ${foot()}
  </main>`;
}

// ------------------------------------------------------------------------------------------------ drawing and events
let lastKey = '';
// Draw the screen for the address. Focus is kept on the control that was used (a day's tab, a distance), found
// again by what it does, so a keyboard stays where it was; a new screen puts focus on its heading.
function draw(opts = {}) {
  route = P.parseQuery(location.search);
  if (route.screen === 'place' && spotOf(route.id) && !details.has(route.id)) loadDetail(route.id);
  const y = window.scrollY, key = route.screen === 'place' ? `place/${route.id}` : `find/${route.area || ''}`;
  const active = document.activeElement, sel = active && active !== document.body && app.contains(active)
    ? (active.dataset.day ? `.daytabs [data-day="${active.dataset.day}"]` : active.dataset.miles ? `[data-miles="${active.dataset.miles}"]` : active.dataset.do ? `[data-do="${active.dataset.do}"]` : active.id ? `#${active.id}` : '') : '';
  const caret = active && active.id === 'q' ? active.selectionStart : null;
  app.innerHTML = route.screen === 'find' ? homeHtml() : placeHtml();
  const s = route.screen === 'place' ? spotOf(route.id) : null;
  document.title = s ? `${s.name} · SwimSignal preview` : 'Where do you swim? · SwimSignal preview';
  if (key !== lastKey) {
    window.scrollTo({ top: opts.y || 0, behavior: 'instant' });
    if (location.hash === '#find') { const q = document.getElementById('q'); if (q) q.focus(); }
    else if (opts.focus) { const h = app.querySelector(route.area ? '.area-h' : 'h1'); if (h) h.focus({ preventScroll: true }); }
  } else {
    window.scrollTo({ top: y, behavior: 'instant' });
    const again = sel && app.querySelector(sel);
    if (again) { again.focus({ preventScroll: true }); if (caret !== null && again.setSelectionRange) again.setSelectionRange(caret, caret); }
  }
  lastKey = key;
  watchTabs();
}
// On a phone the day tabs stay at the top of the screen for the whole page, so the date shown is always in view.
// Once they have left their own place they drop the level word and keep the day and its mark.
let tabsSeen = null;
function watchTabs() {
  if (tabsSeen) tabsSeen.disconnect();
  const mark = app.querySelector('.tabs-top'), tabs = app.querySelector('.place .daytabs');
  if (!mark || !tabs || !('IntersectionObserver' in window)) return;
  tabsSeen = new IntersectionObserver(([e]) => tabs.classList.toggle('stuck', !e.isIntersecting && e.boundingClientRect.top < 0));
  tabsSeen.observe(mark);
}
async function loadDetail(id) {
  const s = spotOf(id); if (!s) return;
  details.set(id, undefined);
  const get = p => loadJson(p).catch(() => null);
  const [detail, up] = await Promise.all([s.detail_file ? get(`../data/${s.detail_file}`) : null, daily(s) ? get(`../data/upstream/${encodeURIComponent(id)}.json`) : null]);
  details.set(id, { detail, up: up && Array.isArray(up.overflows) ? up.overflows : null });
  if (route && route.id === id) draw();
}
function setDay(d) {
  const r = { ...route, day: d }; history.replaceState(null, '', link(r) + (location.hash && location.hash !== '#find' ? location.hash : '')); draw();
  const s = route.id && spotOf(route.id);
  say(s ? `${P.dayTabs(s, DATA).find(t => t.date === d).said}. The page now shows ${P.headDay(d) === 'today' ? 'today' : P.longDate(d)}.` : `Levels shown for ${P.headDay(d) === 'today' ? 'today' : P.longDate(d)}.`);
}
function jump(id) { const el = document.getElementById(id); if (!el) return;
  const h = el.querySelector('h2') || el; el.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); h.focus({ preventScroll: true }); }

app.addEventListener('input', e => { if (e.target.id === 'q') typed(e.target.value); });
app.addEventListener('keydown', e => {
  if (e.target.id === 'q' && e.key === 'Enter') { const first = app.querySelector('#results a.row'); if (first) { e.preventDefault(); first.click(); } }
  // Left and right move along the days, as tabs do.
  const tab = e.target.closest && e.target.closest('.daytab');
  if (tab && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) { const all = [...app.querySelectorAll('.daytab')], i = all.indexOf(tab), to = all[i + (e.key === 'ArrowRight' ? 1 : -1)];
    if (to) { e.preventDefault(); to.focus(); } }
});
app.addEventListener('click', e => {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
  const a = e.target.closest('a[href]'), b = e.target.closest('[data-do]');
  if (b) { const act = b.dataset.do;
    if (act === 'jump') { e.preventDefault(); jump(b.dataset.to); return; }
    if (act === 'locate') { locate(() => draw()); return; }
    if (act === 'unlocate') { here = null; hereNote = ''; draw(); return; }
    if (act === 'miles') { miles = Number(b.dataset.miles) || 20; draw(); return; }
    if (act === 'all' && route.id) { expanded.add(route.id); draw(); return; }
    if (act === 'more') { const box = b.nextElementSibling, open = b.getAttribute('aria-expanded') === 'true'; b.setAttribute('aria-expanded', String(!open)); b.textContent = open ? 'Details' : 'Hide details'; const box2 = b.closest('.st-row') ? b.closest('.st-row').nextElementSibling : box; if (box2) box2.hidden = open; return; }
    if (act === 'keep' && route.id) { const ids = kept(), on = ids.includes(route.id); keep(on ? ids.filter(x => x !== route.id) : [...ids, route.id]); draw();
      const t = document.getElementById('tool-said'); if (t) t.textContent = on ? 'Removed from your places.' : 'Saved on this device. It now opens the first page.'; return; }
    if (act === 'share') { const s = spotOf(route.id), day = placeDay(s), url = location.origin + location.pathname + link({ id: s.id, day }).replace(/^\.\//, ''), t = document.getElementById('tool-said');
      const done = msg => { if (t) t.textContent = msg; };
      const title = `${s.name}: ${P.levelWords(dayLevel(s, day)).toLowerCase()} ${dayWord(day)} (SwimSignal forecast)`;
      if (navigator.share) navigator.share({ title, url }).catch(() => {});
      else if (navigator.clipboard) navigator.clipboard.writeText(url).then(() => done(`Link copied. It opens this place on ${P.headDay(day) === 'today' ? 'today' : P.longDate(day)}.`), () => done('Copy the address from the bar above.'));
      else done('Copy the address from the bar above.');
      return; }
  }
  // Only this page's own addresses are drawn here; a link to the live site, or out, is left to the browser.
  const dir = location.pathname.replace(/[^/]*$/, '');
  if (!a || a.target || a.origin !== location.origin || (a.pathname !== location.pathname && a.pathname !== dir)) return;
  if (a.getAttribute('href').startsWith('#')) return;
  if (a.dataset.day) { e.preventDefault(); setDay(a.dataset.day); return; }
  e.preventDefault(); leftAt.set(location.search, { y: window.scrollY, href: a.getAttribute('href') }); history.pushState(null, '', a.getAttribute('href')); draw({ focus: true });
});
// Back returns to where the page was left: the list of places elsewhere, not the top of the page.
const leftAt = new Map();
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
window.addEventListener('popstate', () => { const at = leftAt.get(location.search) || { y: 0 };
  draw({ focus: true, y: at.y });
  // A keyboard comes back to the link it followed, so the next Tab goes on from there.
  const from = at.href && [...app.querySelectorAll('a[href]')].find(x => x.getAttribute('href') === at.href);
  if (from) from.focus({ preventScroll: true }); });

(async function start() {
  try { const [data, hero] = await Promise.all([loadJson('../data/spots-lite.json'), loadJson('../data/hero-photos.json').catch(() => ({}))]);
    DATA = P.prepare(data, now()); HERO = hero || {}; }
  catch (e) { app.innerHTML = '<header class="bar"><a class="brand" href="./">SwimSignal</a></header><main id="main" class="home"><section class="opening"><h1>The forecast could not be read</h1><p class="lede">Check the connection and load the page again. <a href="../">The current site</a> keeps a copy for offline use.</p></section></main>'; return; }
  draw();
})();
})();
