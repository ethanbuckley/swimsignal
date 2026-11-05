// Keeping a plan's outing for offline use (the outing tile on plan/, outing.js): "Keep this outing for offline
// use" stores on this device what reading the outing needs without signal. That is the plan's page, the pages and
// own files of its spot and backup (spot/<id>/, data/spot/<id>.json, its traced river), the forecast
// (data/spots-lite.json) and the files every page needs, as the offline copy holds them for its build (sw.js, SHELL).
// They go in a cache of their own, CACHE, which sw.js answers from when the network and the build's own cache
// both fail. A new build's worker deletes only its dipcast- caches, so it leaves this one alone. The outing's day,
// spot and backup, when it was kept and when its forecast was issued are noted in this browser (KEY) and in the
// cache itself (META), so the worker can drop it after the day as the page does. Nothing is sent: every file is
// the site's own, asked for as any visit asks.
//
// What it cannot promise: on iPhone and iPad, Safari can delete a site's storage when the phone is short of space,
// and the Home Screen app keeps its own storage, apart from Safari's; Facebook's and Instagram's own browsers keep
// theirs apart from both. A browser that keeps no site data keeps no pack. The tile says so where it matters.
//
// A plain script, as spotdate.js: one global, OutingPack, in the page (so no name here can clash with the app's
// own), and the same object as the export in Node.
const OutingPack = (() => {
  const CACHE = 'swimsignal-outing', KEY = 'dipcast.outingpack', META = 'outing-pack.json';
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  const R = () => typeof dayWord === 'function' ? { dayWord } : require('./levels.js');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const localDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  // ------------------------------------------------------------------ what a pack holds
  // As addresses relative to the site's root: need, without which it is not kept, and may, kept when there.
  // o = { shell (sw.js's SHELL, at its build), spots: [{ id, page (has spot/<id>/), file (detail_file) }] }.
  // The extras are what the plan's and the spots' pages ask for besides: the evidence's warnings, how the
  // forecast has done at each spot, and the reviews' list. A spot without a trace (an isolated lake) has none.
  const EXTRAS = ['data/verification.json', 'data/spot_scores.json', 'reviews/index.json'];
  function files(o) {
    const need = ['plan/', 'data/spots-lite.json'], may = [];
    for (const s of o.spots || []) {
      if (s.page) need.push(`spot/${s.id}/`);
      if (s.upstream) may.push(`data/upstream/${s.id}.json`);   // a paddle's finish: what drains into the water between (outing.js, outingStretch)
      if (s.file) { need.push(`data/${s.file}`); may.push(`data/${s.file.replace(/\.json$/, '-trace.json')}`); }
    }
    may.push(...EXTRAS, ...(o.shell || []));
    const seen = new Set(), once = l => l.filter(p => !seen.has(p) && seen.add(p));
    return { need: once(need), may: once(may) };
  }

  // ------------------------------------------------------------------ the note
  // The note as kept in this browser, or null for none or one that is not whole.
  function read(raw) {
    let m = null;
    try { m = JSON.parse(raw); } catch (e) { return null; }
    return m && typeof m === 'object' && ISO.test(m.day) && typeof m.spot === 'string' && Number.isFinite(m.keptAt) ? m : null;
  }
  // After the outing's day on this device's clock, a pack is dropped (sw.js, fromPack, by the same rule).
  const expired = (m, nowMs) => !m || localDay(new Date(nowMs)) > m.day;
  // The pack is this outing's: the same day, spot, backup and a paddle's finish. want = { day, spot, backup, finish }.
  const same = (m, want) => !!m && m.day === want.day && m.spot === want.spot && (m.backup || null) === (want.backup || null)
    && (m.finish || null) === (want.finish || null);
  // The page (rel: its address under the site's root) is one the pack holds: the plan's, or its spot's or backup's.
  const covers = (m, rel) => !!m && [`plan/`, `spot/${m.spot}/`, ...(m.backup ? [`spot/${m.backup}/`] : []), ...(m.finish ? [`spot/${m.finish}/`] : [])].includes(rel.replace(/\/?$/, '/'));

  // ------------------------------------------------------------------ the words
  const hm = ms => new Date(ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });   // 07:12, 21:40
  // "today", "yesterday", "on Saturday", on this device's clock. A pack lasts five days at most, so a weekday is enough.
  function onDay(ms, nowMs) {
    const d = localDay(new Date(ms)), t = new Date(nowMs);
    if (d === localDay(t)) return 'today';
    t.setDate(t.getDate() - 1);
    if (d === localDay(t)) return 'yesterday';
    return 'on ' + new Date(ms).toLocaleDateString('en-GB', { weekday: 'long' });
  }
  const ago = m => { const t = Math.max(0, Math.round(m)); return t < 60 ? `${t} min` : t % 60 ? `${Math.floor(t / 60)} h ${t % 60} min` : `${t / 60} h`; };   // index.html's
  // "Kept for offline use at 07:12 on Saturday." and "The forecast in it was issued at 06:00." (with its day when
  // that is not the day it was kept).
  const keptAt = (m, nowMs) => `Kept for offline use at ${hm(m.keptAt)} ${onDay(m.keptAt, nowMs)}.`;
  function issuedAt(m, nowMs) {
    const t = Date.parse(m.issuedAt);
    if (!Number.isFinite(t)) return '';
    return `The forecast in it was issued at ${hm(t)}${localDay(new Date(t)) === localDay(new Date(m.keptAt)) ? '' : ' ' + onDay(t, nowMs)}.`;
  }
  const CHECK = 'Check again before you leave if you have signal.';
  const dayOf = day => R().dayWord(day).replace(/^on /, '');   // "today", "tomorrow", "Saturday"
  const named = m => `${esc((m.names || [])[0] || m.spot)}${m.finish ? `, finish ${esc((m.names || [])[2] || m.finish)}` : ''}${m.backup ? `, backup ${esc((m.names || [])[1] || m.backup)}` : ''}`;

  // The pack's part of the outing tile, as HTML. t = { state, meta, want, names: [spot, backup], newer (a later
  // forecast's issue time, ISO), nowMs, ios, app (an in-app browser's name) }. state: 'none' (this browser cannot
  // keep pages), 'off' (the offline copy is turned off here), 'ready', 'other' (another outing is kept), 'kept'.
  function tile(t) {
    const keepBtn = word => `<button type="button" class="btn" data-outing-pack="keep">${word}</button>`;
    const stopBtn = '<button type="button" class="btn" data-outing-pack="stop">Stop keeping it</button>';
    const until = `until the end of ${esc(dayOf(t.want.day))}`;
    const what = `the plan and the pages of ${(t.names || []).filter(Boolean).map(esc).join(' and ')}`;
    switch (t.state) {
      case 'none': return '<p class="small muted">This browser cannot keep the outing for offline use.</p>';
      case 'off': return '<p class="small">Keeping this outing for offline use needs the offline copy, which is turned off in this browser. '
        + 'You can turn it back on at the bottom of the home page, under "Saved spots, offline use and your data".</p>';
      case 'ready': case 'other': return (t.state === 'other' && t.meta
        ? `<p class="small">A different outing is kept for offline use: ${named(t.meta)}, for ${esc(dayOf(t.meta.day))}. Keeping this one replaces it. `
          + '<button type="button" class="linkbtn small" data-outing-pack="stop">Stop keeping that one</button></p>' : '')
        + `<p class="outing-acts">${keepBtn('Keep this outing for offline use')}</p>`
        + `<p class="small muted">This keeps ${what} on this device, so you can open them without signal, ${until}. Nothing is sent.</p>`;
      case 'kept': break;
      default: return '';
    }
    const m = t.meta, newer = t.newer && Date.parse(t.newer) > Date.parse(m.issuedAt) ? Date.parse(t.newer) : null;
    const caveats = [`It stays on this device ${until}, then it is deleted.`,
      t.ios ? 'On iPhone and iPad, Safari can delete it sooner if the phone is short of space. Safari and the Home Screen app each keep their own copy, so keep it in the one you will open at the water.' : '',
      t.app ? `In the ${esc(t.app)} app's browser, it stays in that app: your phone's own browser does not have it.` : ''].filter(Boolean);
    return `<p class="outing-pack-on"><b>${keptAt(m, t.nowMs)}</b> ${[issuedAt(m, t.nowMs), CHECK].filter(Boolean).join(' ')}</p>`
      + (newer ? `<p class="small">A newer forecast was issued at ${hm(newer)} ${onDay(newer, t.nowMs)}. Keep the outing again to store it.</p>` : '')
      + `<p class="small muted">${caveats.join(' ')}</p>`
      + `<p class="outing-acts">${newer ? keepBtn('Keep it again') : ''}${stopBtn}</p>`;
  }

  // The line a kept page shows where the forecast's age is given (index.html, freshness), when it is read from a
  // stored copy: o = { meta, rel, offline (no connection, or the forecast came from a stored copy), nowMs, issued
  // (the shown forecast's issue time, when the page says it nowhere else) }. '' otherwise.
  function line(o) {
    const m = o.meta;
    if (!o.offline || expired(m, o.nowMs) || !covers(m, o.rel)) return '';
    return `<p class="issued">Showing the copy kept on this device. Your outing was kept for offline use at ${hm(m.keptAt)} ${onDay(m.keptAt, o.nowMs)}, `
      + `${ago((o.nowMs - m.keptAt) / 60000)} ago.${o.issued ? ` The forecast shown was issued ${esc(o.issued)}.` : ''}</p>`;
  }

  // ------------------------------------------------------------------ on the device
  // st: this browser's local storage; cs: its caches. Both are passed in Node.
  const kept = (st = globalThis.localStorage) => { try { return read(st.getItem(KEY)); } catch (e) { return null; } };
  async function drop(cs = globalThis.caches, st = globalThis.localStorage) {
    try { st.removeItem(KEY); } catch (e) { /* nothing kept */ }
    if (cs) await cs.delete(CACHE);
  }
  // Once a page opens: a pack past its day, or one whose note this browser has lost, is deleted.
  async function tidy(nowMs = Date.now(), cs = globalThis.caches, st = globalThis.localStorage) {
    const m = kept(st);
    if (m && !expired(m, nowMs)) return false;
    if (m || (cs && await cs.has(CACHE))) { await drop(cs, st); return true; }
    return false;
  }
  // Fetches the files and stores them, replacing any pack. get(path) answers as fetch does; base: the site's root,
  // which the worker's scope is; meta: the note, to which the forecast's issue time is added from the file itself.
  // Every file is read before anything is replaced, so a file that cannot be had leaves the pack that was there.
  async function store(list, get, base, meta, cs = globalThis.caches, st = globalThis.localStorage) {
    const copy = async (p, r) => [new URL(p, base).href, new Response(await r.blob(), { status: 200, headers: r.headers })];
    const need = await Promise.all(list.need.map(async p => {
      const r = await get(p);
      if (!r || !r.ok) throw new Error(`${p} answered ${r ? r.status : 'nothing'}`);
      return copy(p, r);
    }));
    const may = (await Promise.all(list.may.map(p => Promise.resolve().then(() => get(p)).then(r => r && r.ok ? copy(p, r) : null).catch(() => null)))).filter(Boolean);
    const forecast = need.find(([u]) => u === new URL('data/spots-lite.json', base).href);
    const issued = forecast ? await forecast[1].clone().json().then(j => j.generated_at).catch(() => null) : null;
    const note = { ...meta, issuedAt: issued || meta.issuedAt || null };
    await cs.delete(CACHE);
    const c = await cs.open(CACHE);
    try {
      for (const [u, r] of [...need, ...may]) await c.put(u, r);
      await c.put(new URL(META, base).href, new Response(JSON.stringify(note), { headers: { 'Content-Type': 'application/json' } }));
      st.setItem(KEY, JSON.stringify(note));
    } catch (e) {
      await drop(cs, st);
      throw new Error(/quota/i.test(e.name + e.message) ? 'this device has no room for it' : 'this browser is not keeping site data');
    }
    return note;
  }

  // ------------------------------------------------------------------ in the page
  let STORED = false;   // the forecast came from a stored copy (sw.js marks it), though the phone says it is online
  const seen = res => { STORED = !!(res && res.headers && res.headers.get('X-SwimSignal-Stored')); };
  const rel = () => location.pathname.startsWith(ROOT.pathname) ? location.pathname.slice(ROOT.pathname.length) : '';
  const notice = () => line({ meta: kept(), rel: rel(), offline: !navigator.onLine || STORED, nowMs: Date.now(),
    issued: navigator.onLine && STORED && typeof issued === 'function' ? issued() : '' });

  // The worker's own list of what every page needs, at its build (sw.js, the message 'shell').
  async function shell() {
    const reg = await Promise.race([navigator.serviceWorker.ready, new Promise(r => setTimeout(() => r(null), 5000))]);
    const w = reg && reg.active;
    if (!w) throw new Error('the offline copy is not running yet in this browser; reload the page and try again');
    return new Promise((ok, no) => {
      const ch = new MessageChannel(), t = setTimeout(() => no(new Error('the offline copy did not answer; reload the page and try again')), 5000);
      ch.port1.onmessage = e => { clearTimeout(t); e.data && Array.isArray(e.data.shell) ? ok(e.data) : no(new Error('the offline copy did not answer')); };
      w.postMessage({ outingPack: 'shell' }, [ch.port2]);
    });
  }
  const can = () => typeof navigator === 'object' && 'serviceWorker' in navigator && typeof caches === 'object';
  function state(want) {
    if (!can()) return { state: 'none' };
    if (typeof offlineOff === 'function' && offlineOff()) return { state: 'off' };
    const m = kept();
    if (!m || expired(m, Date.now())) return { state: 'ready' };
    return { state: same(m, want) ? 'kept' : 'other', meta: m };
  }

  // Draws the pack's part at the foot of the outing tile's keeping part (outing.js, outingKeep), for the outing's
  // spot and backup (outing.js, outingPair: spots from spots.json).
  function draw(pair) {
    const box = document.querySelector('#outing .outing-keep');
    if (!box || !pair || !pair.main) return;
    box.insertAdjacentHTML('beforeend', '<div class="outing-pack" id="outing-pack"></div><p class="small muted msg" id="outing-pack-msg" aria-live="polite"></p>');
    const el = document.getElementById('outing-pack'), msg = document.getElementById('outing-pack-msg');
    const spots = [pair.main, pair.backup, pair.finish].filter(Boolean);
    // names: [spot, backup, finish], each in its place, null where there is none (an older pack has two).
    const names = [pair.main.name, pair.backup ? pair.backup.name : null, pair.finish ? pair.finish.name : null];
    const want = { day: PLAN.day, spot: pair.main.id, backup: pair.backup ? pair.backup.id : null, ...(pair.finish ? { finish: pair.finish.id } : {}) };
    const paint = () => {
      const s = state(want);
      el.innerHTML = tile({ ...s, want, names: names.filter(Boolean), newer: DATA.generated_at, nowMs: Date.now(), ios: IOS, app: IN_APP });
      el.querySelectorAll('[data-outing-pack]').forEach(b => b.addEventListener('click', async () => {
        el.querySelectorAll('button').forEach(x => { x.disabled = true; });
        if (b.dataset.outingPack === 'stop') {
          await drop().catch(() => {});
          paint(); msg.textContent = 'It is no longer kept on this device.';
          return;
        }
        msg.textContent = 'Keeping this outing on this device…';
        try {
          const sh = await shell();
          const list = files({ shell: sh.shell, spots: spots.map(x => ({ id: x.id, page: PAGE_ID.test(x.id), file: x.detail_file || null, upstream: !!pair.finish && x.id === pair.finish.id })) });
          await store(list, p => fetch(new URL(p, ROOT).href, { cache: 'no-cache', credentials: 'omit' }), ROOT.href,
            { v: 1, ...want, names, keptAt: Date.now(), issuedAt: DATA.generated_at, build: sh.build });
          paint(); msg.textContent = 'Kept for offline use.';
        } catch (e) { paint(); msg.textContent = `Could not keep this outing: ${e.message}.`; }
      }));
    };
    paint();
  }

  // A pack past its day goes as soon as any page opens.
  if (typeof window === 'object' && typeof document === 'object' && can()) tidy().catch(() => {});

  return { CACHE, KEY, META, EXTRAS, files, read, expired, same, covers, keptAt, issuedAt, CHECK, tile, line, kept, drop, tidy, store, seen, notice, draw };
})();

if (typeof module === 'object' && module.exports) module.exports = OutingPack;
