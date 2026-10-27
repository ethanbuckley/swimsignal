// Today's EA advice on a designated bathing water's page: a fold at the foot of the Environment Agency
// rating tile that loads the EA's own panel for the site, as the coverage page does for the coast.
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

// Official advice at a spot (spots.json `official`, newest first): lines a reviewer checked against the
// publisher's own record, written in by the build from data/advisories/ with no request
// (src/dipcast/official_advice.py). The block sits above the forecast's level, never changes it, and says
// so. Each line keeps its publisher, its start and a link, and says when the finder last checked it: a
// check that is old or could not read the source says "Not re-checked since", never nothing. No item, no
// block: the page then says what it said before ("Today's EA advice", above). The prerender runs this.
const EA_TODAY_STATES = new Set(['checked', 'stale', 'unverified', 'gone', 'changed']);
const eaTodayDay = iso => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
  return m && +m[2] >= 1 && +m[2] <= 12 ? `${+m[3]} ${EA_TODAY_MONTHS[m[2] - 1]} ${m[1]}` : null; };
// The items a page can show: a line, a publisher and a known state with a real day. Anything else is dropped.
const eaTodayAdvice = d => (d && Array.isArray(d.official) ? d.official : [])
  .filter(o => o && typeof o.line === 'string' && o.line && typeof o.publisher === 'string' && o.publisher
    && EA_TODAY_STATES.has(o.state) && eaTodayDay(o.checked));
function eaTodayChecked(o) {
  const day = eaTodayDay(o.checked);
  return o.state === 'checked' ? `Last checked ${day}.`
    : o.state === 'unverified' ? `Not re-checked since ${day}: the ${o.publisher} source could not be read.`
    : o.state === 'gone' ? `Not re-checked since ${day}: no longer in the ${o.publisher}'s open list; its end was not published.`
    : o.state === 'changed' ? `Not re-checked since ${day}: the ${o.publisher}'s record has changed since it was reviewed.`
    : `Not re-checked since ${day}.`;
}
function eaTodayOfficial(d) {
  const items = eaTodayAdvice(d);
  if (!items.length) return '';
  const r = eaTodayRestricts(d);   // "advice" and "follow" only for a notice its reviewer marked as restricting swimming
  return `<section class="notice official" id="official" aria-labelledby="official-h"><h2 id="official-h">${r ? 'Official advice' : 'Official notice'}</h2><ul>`
    + items.map(o => `<li><p class="o-line">${eaTodayEsc(o.line)}</p><p class="o-src">`
      + (/^https:\/\/[^\s"<>]+$/.test(o.link || '') ? `<a href="${eaTodayEsc(o.link)}">Open the ${eaTodayEsc(o.publisher)} page</a>. ` : '')
      + `${eaTodayEsc(eaTodayChecked(o))}</p></li>`).join('')
    + `</ul><p class="o-sep">${r ? 'Follow this advice first' : 'Read this notice first'}. It is not SwimSignal's, and the forecast below does not include it.</p></section>`;
}
// In the answer's coverage line, in place of "Today's EA advice not checked: open it before you swim"
// when a reviewed notice shows above: what was checked and when, then where the latest is. '' without one.
const eaTodayShort = iso => (eaTodayDay(iso) || '').replace(/ \d{4}$/, '');
function eaTodayCover(d) {
  const items = eaTodayAdvice(d);
  if (!items.length) return '';
  const o = items[0], what = items.length > 1 ? 'The notices above' : `The ${eaTodayEsc(o.publisher)}'s notice above`;
  const when = o.state === 'checked' ? `${items.length > 1 ? 'were' : 'was'} last checked ${eaTodayShort(o.checked)}`
    : `${items.length > 1 ? 'have' : 'has'} not been re-checked since ${eaTodayShort(o.checked)}`;
  const open = eaTodayLatest(d);
  return `${what} ${when}${open ? `. ${open}` : ''}`;
}
// Where the latest is, for a spot with a reviewed notice: the fold in its rating tile (eaTodayFold) at a
// bathing water, else the publisher's page. The Not known here tile says only this, as the answer has the rest.
function eaTodayLatest(d) {
  const o = eaTodayAdvice(d)[0]; if (!o) return '';
  return eaTodayId(d) ? `Open <a href="#ea-today">today's EA advice</a> for the latest`
    : /^https:\/\/[^\s"<>]+$/.test(o.link || '') ? `Open <a href="${eaTodayEsc(o.link)}">the ${eaTodayEsc(o.publisher)} page</a> for the latest` : '';
}
// What to do, in place of the level's line ("Usual care: …", which read as leave to swim), while a reviewed
// notice shows: the notice comes first. "Follow" only for a notice its reviewer marked as restricting swimming
// (eaTodayRestricts); any other is to be read, in its own words above, not obeyed as a restriction it may not be.
// '' without one, and the level's own line stands.
const eaTodayAct = d => !eaTodayAdvice(d).length ? ''
  : eaTodayRestricts(d) ? 'Follow the official advice above first.' : 'Read the official notice above first.';
// Whether a spot's notices include one its reviewer marked as restricting swimming (`restricts: true`,
// src/dipcast/official_advice.py). What the pages leave out of counts, shared plans and suggestions, and put first,
// goes by this; what they show (the notice, its tag, the map's ring) goes by eaTodayAdvice, every notice. Only an
// explicit true counts: a notice without the field (a spots.json from before 28 Oct 2026) changes no selection.
const eaTodayRestricts = d => eaTodayAdvice(d).some(o => o.restricts === true);
// What the pages ask beside a notice's compact form, "Official: … . Follow it first": follow it only where it
// restricts swimming, else read it (the sites view, the organisers' page, the record, the comparison).
const eaTodayFirst = d => eaTodayRestricts(d) ? 'Follow it first' : 'Read the official notice first';
// The label a page puts before a notice's compact form: "Official advice" only where it restricts swimming.
const eaTodayLabel = d => eaTodayRestricts(d) ? 'Official advice' : 'Official notice';
// The compact form for the places a spot is one row among many: the list, Saved, Plan a swim's rows and
// the decision record. "EA advice against bathing (harmful algae) · since 19 Jun · checked 26 Oct", in a line of its own
// beside the level, never in it. One shared helper, so every surface says the same. '' without advice.
const eaTodayWho = p => p === 'Environment Agency' ? 'EA' : p;
function eaTodayBrief(d) {
  const items = eaTodayAdvice(d);
  if (!items.length) return '';
  const o = items[0], said = o.line.replace(/^[^:]*:\s*/, '').replace(/\s+since\s.*$/, '');   // the cause, "(harmful algae)", stays
  const since = eaTodayShort(o.since);
  return [`${eaTodayWho(o.publisher)} ${said}`, since ? `since ${since}` : '',
    o.state === 'checked' ? `checked ${eaTodayShort(o.checked)}` : `not re-checked since ${eaTodayShort(o.checked)}`,
    items.length > 1 ? `${items.length - 1} more` : ''].filter(Boolean).join(' · ');
}
const eaTodayTag = (d, el = 'span') => { const t = eaTodayBrief(d); return t ? `<${el} class="o-tag">${eaTodayEsc(t)}</${el}>` : ''; };
// The line under the level when there is official advice, so the two are not read as one.
const eaTodayApart = d => eaTodayAdvice(d).length ? `<p class="gaps o-apart">This level is SwimSignal's forecast. The official ${eaTodayRestricts(d) ? 'advice' : 'notice'} above is separate.</p>` : '';

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
  module.exports = { EA_TODAY_WIDGET, EA_TODAY_SITE, eaTodayId, eaTodayUrl, eaTodayWhen, eaTodayPage, eaTodayFold, eaTodayOpen, eaTodayListen,
    eaTodayAdvice, eaTodayRestricts, eaTodayFirst, eaTodayLabel, eaTodayChecked, eaTodayOfficial, eaTodayApart, eaTodayCover, eaTodayLatest, eaTodayAct, eaTodayBrief, eaTodayTag };
}
