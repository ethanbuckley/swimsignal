// Today's EA advice on a designated bathing water's page: a fold at the foot of the Environment Agency
// rating tile that loads the EA's own panel for the site, as the coverage page does for the coast (#116).
//
// The EA's short-term advice against bathing, after a pollution incident or an algal bloom, never
// reaches spots.json: the EA's bathing-water service refuses the build's machines (since 28 Sep 2026),
// and its API sends no access-control-allow-origin, so this page cannot read it either (checked 4 Oct
// 2026). On 4 Oct 2026 two of the spots had an incident open: Frensham Great Pond (harmful algae, since
// 19 Jun) and Ham and Kingston (harmful algae, since 17 Aug). The EA offers a widget for other sites to
// embed (environment.data.gov.uk/bwq/widget): its own panel of today's advice, incidents included, in
// its own words. That is what opens here.
//
// The fold is closed when the page draws. Opening it loads the panel once per page view, from the
// reader's browser, in a sandboxed frame with scripts off (its links open a new tab) that sends no
// referrer. Nothing is kept. A page cannot read or style a frame from another site, so the panel keeps
// the EA's design and it cannot change the level. Nor can the page read the panel's height, so the frame's
// is fixed (index.html, details.ea-today): taller for a site with no rating yet, whose panel says so in
// two more lines, and on a narrow phone. It shows no issue time, and its cache-control lets a browser keep
// it for an hour: the line under it says so.
//
// A plain script, like evidence.js: in the page its names are globals (each begins eaToday or EA_TODAY,
// clear of the page's own and the other scripts'), and in Node the last lines export them
// (tests/site_eatoday.test.cjs).

const EA_TODAY_WIDGET = 'https://environment.data.gov.uk/bwq/widget/widget/widget1';
const EA_TODAY_SITE = /^uk[a-z0-9]+-\d{5}$/;   // an EA bathing-water id, as "ukj2310-11945"
const EA_TODAY_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const eaTodayEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// The EA's id for a spot: its own id without "bw-", or else the site= of its EA page's address. Null for
// a spot that is not a designated bathing water and for a point clicked on the map.
function eaTodayId(d) {
  if (!d || d.unlisted || !d.classification) return null;
  const own = typeof d.id === 'string' && d.id.startsWith('bw-') ? d.id.slice(3) : '';
  if (EA_TODAY_SITE.test(own)) return own;
  const m = /[?&]site=([^&#]*)/.exec(String(d.classification.url || ''));
  return m && EA_TODAY_SITE.test(m[1]) ? m[1] : null;
}
// The panel's address, without photo, map or rating history (the tile has the rating); null unless id is one.
function eaTodayUrl(id) {
  return typeof id === 'string' && EA_TODAY_SITE.test(id) ? `${EA_TODAY_WIDGET}?eu=${id}&history=false&m=false&p=false` : null;
}
// "4 Oct 2026, 16:45", in UK time whatever the reader's clock, as the coverage page writes it.
function eaTodayWhen(t) {
  const f = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  const p = Object.fromEntries(f.formatToParts(new Date(t)).filter(x => x.type !== 'literal').map(x => [x.type, x.value]));
  return `${+p.day} ${EA_TODAY_MONTHS[p.month - 1]} ${p.year}, ${p.hour}:${p.minute}`;
}

// The EA's page for a site: its own address where the spot has one, or else the profile for the id.
const eaTodayPage = (url, id) => /^https:\/\//.test(url || '') ? url : `https://environment.data.gov.uk/bwq/profiles/profile.html?site=${id}`;
// The fold, closed, for the rating tile (facts in index.html); '' without an EA id. Until it is opened it
// holds a link to the EA's page; once opened, the line under the panel keeps that link, for a panel that
// does not load (offline, or a frame the browser blocks).
function eaTodayFold(d) {
  const id = eaTodayId(d);
  if (!id) return '';
  const page = eaTodayPage(d.classification.url, id);
  return `<details class="ea-today" id="ea-today" data-site="${id}" data-name="${eaTodayEsc(d.name)}" data-rated="${d.classification.class ? 'yes' : 'no'}"><summary>Today's EA advice</summary>`
    + `<p>Open <a href="${eaTodayEsc(page)}">the EA's page</a> for today's advice.</p></details>`;
}

// Fills an opened fold with the EA's panel and the line under it; false if its site id is not one.
function eaTodayOpen(fold, nowMs) {
  const url = eaTodayUrl(fold.dataset.site);
  if (!url) return false;
  const frame = document.createElement('iframe');
  frame.src = url;
  frame.title = `Environment Agency: today's advice at ${fold.dataset.name}`;
  frame.setAttribute('sandbox', 'allow-popups allow-popups-to-escape-sandbox');   // its links open a new tab; no scripts
  frame.referrerPolicy = 'no-referrer';
  if (fold.dataset.rated === 'no') frame.className = 'unrated';   // "This newly-designated site does not have ...": a taller panel
  const note = document.createElement('p'), link = fold.querySelector('p a');
  const page = eaTodayPage(link && link.getAttribute('href'), fold.dataset.site);
  note.innerHTML = `The Environment Agency's own panel, loaded ${eaTodayWhen(nowMs)}. It shows no issue time, and browsers may keep it for up to an hour. No warning is not a water test. `
    + `If the panel does not show, open <a href="${eaTodayEsc(page)}">the EA's page</a>.`;
  fold.replaceChildren(fold.querySelector('summary'), frame, note);
  // Opened near the foot of a phone's screen, the panel would land below it: bring it into view.
  if (fold.scrollIntoView) fold.scrollIntoView({ block: 'nearest' });
  return true;
}

// One listener for the page, on the way down ('toggle' does not bubble), so it holds for every spot the
// page draws. A fold loads once: closed and opened again, it shows the same panel without a new request.
function eaTodayListen(root, now = () => Date.now()) {
  root.addEventListener('toggle', e => {
    const fold = e.target;
    if (fold && fold.classList && fold.classList.contains('ea-today') && fold.open && !fold.dataset.loaded) {
      fold.dataset.loaded = 'yes';
      eaTodayOpen(fold, now());
    }
  }, true);
}
if (typeof document === 'object' && document && typeof document.addEventListener === 'function') eaTodayListen(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { EA_TODAY_WIDGET, EA_TODAY_SITE, eaTodayId, eaTodayUrl, eaTodayWhen, eaTodayFold, eaTodayOpen, eaTodayListen };
}
