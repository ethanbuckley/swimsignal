// The page and the latest forecast kept on the device, so the site opens without signal at the
// water's edge; the page then says how old the forecast is (index.html, freshness()).
//
// Pages, data and the site's own scripts: the network first, the stored copy if the network fails
// or takes over 4 s (a slow answer still refreshes the stored copy when it arrives). Icons, the
// picture behind the pages, the fonts and the map library (vendor/): the stored copy first,
// refreshed in the background. Everything is this site's own: map tiles are their provider's
// (OpenStreetMap's, or DIPCAST_TILES') and the page-view counter Cloudflare's, so neither is stored,
// nor is the 6 MB overflow layer (whole, or in the tiles the map loads, data/overflows/), nor
// swimmers' photos (reviews/photos/), which would pile up on the device a spot at a time, nor the Atom
// feeds (feed.xml, feed/, spot/<id>/feed.xml), which are for feed readers, not the app.
//
// BUILD is a hash of the files this worker stores, which scripts/build_site.py (shell_stamp) writes
// in on every build. A changed font, icon or script therefore changes this file, the browser
// installs the new worker, and it fills a new cache, so nothing is served stale for a visit; the
// old cache is deleted when it takes over. The page asks for its own script (app.js, taken out of
// index.html at build), levels.js, experience.js, anypoint.js and the rest with ?v=BUILD too, so a
// page and its scripts come from one build: a page from the network never runs with a stored older
// levels.js, and a stored page never with a newer one.
//
// An outing kept for offline use (outingpack.js) is in a cache of its own, PACK, not named dipcast-, so a new
// build's worker leaves it alone. It answers only when the network and this build's cache both fail, and only
// until the end of the outing's day (fromPack).
//
// To retire this worker, publish a sw.js that unregisters itself: a deleted file leaves the
// installed worker running on visitors' devices.
const BUILD = 'dev';
const CACHE = `dipcast-${BUILD}`;
const TIMEOUT_MS = 4000;
const SHELL = ['./', `app.js?v=${BUILD}`, `levels.js?v=${BUILD}`, `experience.js?v=${BUILD}`, `anypoint.js?v=${BUILD}`, `plan.js?v=${BUILD}`, `lists.js?v=${BUILD}`, 'feedback.html', 'page.css', 'data/spots-lite.json', 'manifest.webmanifest',
  'icons/icon.svg', 'icons/icon-192.png', 'icons/fells.webp', 'icons/fells-wide.webp',
  `since.js?v=${BUILD}`,   // what changed at a saved spot since you last looked
  `outing.js?v=${BUILD}`,   // a plan's outing: when, the spot and a backup
  `dayplan.js?v=${BUILD}`,   // the day plan: options, and the plan as a picture
  `outingwatch.js?v=${BUILD}`,   // what would change the outing, and what has since it was planned
  `findwindow.js?v=${BUILD}`,   // Find a window on Saved
  `spotdate.js?v=${BUILD}`,   // the outing's calendar file and the alerts for its date
  'fonts/SourceSans3-latin.woff2', 'fonts/SourceSans3-italic-latin.woff2', 'fonts/SourceSerif4-latin.woff2',
  'vendor/leaflet/leaflet.css', 'vendor/leaflet/leaflet.js', `reviews.js?v=${BUILD}`, `visits.js?v=${BUILD}`, `illness.js?v=${BUILD}`, `guide.js?v=${BUILD}`, `evidence.js?v=${BUILD}`,
  `spotscores.js?v=${BUILD}`,   // how the forecast has done here; its data file is stored when a spot first asks for it
  `seasonal.js?v=${BUILD}`,   // past spills upstream by month; its numbers come in the spot's own file
  `outingpack.js?v=${BUILD}`,   // keeping a plan's outing for offline use (PACK, below)
  `measured.js?v=${BUILD}`,   // lab results an organisation sent (samples/)
  `timeline.js?v=${BUILD}`,   // the evidence timeline; its files are fetched when its fold is opened
  `journal.js?v=${BUILD}`,
  `passport.js?v=${BUILD}`,   // the swim passport on Saved
  `arrive.js?v=${BUILD}`,   // the arrival guide (prototype, ?arrive=1 only); the guide is in the spot's own file
  `replay.js?v=${BUILD}`,   // the catchment replay (prototype, ?replay=1 only); its data file is stored when first opened
  `plume.js?v=${BUILD}`,   // the spill map on a spot's page; its route file is stored when first opened
  `evmap.js?v=${BUILD}`,   // the evidence map (prototype, ?evidence=1 only); offline it draws from the spot's stored trace, or says it could not load
  `eatoday.js?v=${BUILD}`];   // today's EA advice: the script only; the EA's panel is the EA's, never stored

self.addEventListener('install', e => {
  // One missing file must not stop the rest being stored. no-cache: a new build's cache is filled
  // from the server, not from the browser's copies of the last build's files.
  e.waitUntil(caches.open(CACHE)
    .then(c => Promise.all(SHELL.map(u => c.add(new Request(u, { mode: 'cors', credentials: 'omit', cache: 'no-cache' })).catch(() => null))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('dipcast-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url), here = url.origin === self.location.origin;
  if (!here) return;                                            // tiles, the page-view counter: not ours to keep
  if (url.pathname.endsWith('/data/overflows.geojson') || url.pathname.includes('/data/overflows/') || url.pathname.includes('/reviews/photos/')) return;
  if (url.pathname.endsWith('.xml')) return;                    // the Atom feeds and the sitemap: for readers and crawlers, not the app
  // The stylesheet changes with the pages; a library in vendor/ changes only with its version.
  const fresh = req.mode === 'navigate' || (/\.(html|json|js|css)$/.test(url.pathname) && !url.pathname.includes('/vendor/'));
  e.respondWith(fresh ? networkFirst(req) : storedFirst(req));
});

// A page is stored under its address without the query, so ?spot= or ?fbclid= links cannot leave an
// older copy that an offline or slow visit would find first.
const key = req => { const u = new URL(req.url); if (req.mode === 'navigate') u.search = ''; u.hash = ''; return u.href; };

async function networkFirst(req) {
  const cache = await caches.open(CACHE), k = key(req);
  // no-cache: ask the server every time. GitHub Pages sends max-age=600, so without it a reload
  // within 10 minutes of the last one could get the browser's older copy of the forecast.
  const net = fetch(req, { cache: 'no-cache' }).then(res => { if (res.ok) { cache.put(k, res.clone()); withTrace(cache, k); } return res; });
  net.catch(() => {});   // when the stored copy answers, a later network failure is expected
  try {
    return await Promise.race([net, new Promise((_, no) => setTimeout(() => no(new Error('slow')), TIMEOUT_MS))]);
  } catch (err) {
    const hit = await cache.match(k) || await fromPack(k);
    if (hit) return stored(hit);
    // A page never opened before (a spot's, say): the home page stands in and reads the spot from
    // the address. Its first <base>, at this worker's scope, keeps its links working at any depth.
    const home = req.mode === 'navigate' ? await cache.match(self.registration.scope) || await fromPack(self.registration.scope) : undefined;
    if (!home) return net;
    const html = (await home.text()).replace('<head>', `<head>\n<base href="${self.registration.scope}">`);
    return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8', [STORED]: '1' } });
  }
}

// A spot's own file, data/spot/<id>.json, brings its traced river, data/spot/<id>-trace.json, which its map
// draws only when zoomed in (index.html, drawTrace): stored now, so the map has it at the water. Not every
// spot has one (an isolated lake has nothing traced), so a missing one is no error.
const SPOT_FILE = /\/data\/spot\/([A-Za-z0-9_-]+)\.json$/;
function withTrace(cache, k) {
  const u = new URL(k), m = u.pathname.match(SPOT_FILE);
  if (!m || /-(trace|replay|plume)$/.test(m[1])) return;   // a trace, a replay (replay.js) or a spill map's routes (plume.js): none has a trace of its own
  u.pathname = u.pathname.replace(SPOT_FILE, '/data/spot/$1-trace.json'); u.search = '';
  fetch(u.href, { cache: 'no-cache', credentials: 'omit' }).then(res => { if (res.ok) cache.put(u.href, res); }).catch(() => {});
}

async function storedFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req.url);
  const net = fetch(req.url, { mode: 'cors', credentials: 'omit' })
    .then(res => { if (res.ok) cache.put(req.url, res.clone()); return res; })
    .catch(() => null);
  return hit || (await net) || (await fromPack(req.url)) || Response.error();
}

// A stored answer says so, so the page can tell a kept copy from a fresh one even when the phone says it is
// online (one bar of signal, and the 4 s ran out): outingpack.js, seen.
const STORED = 'X-SwimSignal-Stored';
const stored = res => new Response(res.body, { status: res.status, statusText: res.statusText, headers: [...res.headers, [STORED, '1']] });

// The outing kept for offline use (outingpack.js): its copy of k, while its day lasts on this device's clock.
// Its note (PACK_META, which the page writes beside the files) gives the day; past it, or without one, the
// pack is deleted rather than shown.
const PACK = 'swimsignal-outing', PACK_META = 'outing-pack.json';
const localDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
async function fromPack(k) {
  try {
    const hit = await caches.match(k, { cacheName: PACK });
    if (!hit) return undefined;
    const note = await caches.match(new URL(PACK_META, self.registration.scope).href, { cacheName: PACK });
    const day = note ? await note.json().then(m => m && m.day, () => null) : null;
    if (typeof day === 'string' && day >= localDay(new Date())) return hit;
    await caches.delete(PACK);
  } catch (err) { /* no pack */ }
  return undefined;
}

// Keeping an outing (outingpack.js) asks for the files every page needs at this build, to keep them with it.
self.addEventListener('message', e => {
  if (e.data && e.data.outingPack === 'shell' && e.ports && e.ports[0]) e.ports[0].postMessage({ build: BUILD, shell: SHELL });
});

// Alerts (push/ sends them; index.html, "alerts"): show what arrived, and open its page when
// tapped. Only this site's own pages open, whatever a message says.
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = {}; }
  if (!d || typeof d !== 'object') d = {};
  // Push services honour TTL, but also check on the device in case delivery was delayed.
  // userVisibleOnly subscriptions still need a visible notification: never show an expired
  // pollution claim as current, and instead invite the swimmer to check the latest forecast.
  const expiry = Date.parse(d.expires_at);
  if (d.expires_at !== undefined && (!Number.isFinite(expiry) || expiry <= Date.now())) {
    d = { title: 'SwimSignal forecast update', body: 'This alert has expired. Open SwimSignal to check the latest forecast.', tag: d.tag, url: d.url };
  } else if (d.issued_at && Number.isFinite(Date.parse(d.issued_at))) {
    const when = new Date(d.issued_at).toLocaleString('en-GB', { timeZone: 'Europe/London', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    d.body = `${d.body || ''} Forecast issued ${when} (UK time).`;
  }
  e.waitUntil(self.registration.showNotification(d.title || 'SwimSignal', {
    body: d.body || '', tag: d.tag, data: { url: d.url }, icon: 'icons/icon-192.png', badge: 'icons/icon-192.png' }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const scope = self.registration.scope, u = (e.notification.data || {}).url;
  let url = scope;
  try { const v = new URL(u, scope).href; if (v.startsWith(scope)) url = v; } catch (err) { /* the home page */ }
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(wins => {
    const w = wins.find(c => c.url.startsWith(scope));
    return w ? w.focus().then(c => c.navigate(url)).catch(() => self.clients.openWindow(url)) : self.clients.openWindow(url);
  }));
});
