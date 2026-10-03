// Quick notes on a visit, on a spot's page: what it was like today or yesterday. Ticks from a short
// list ("entry steps damaged", "car park closed", "very busy", "new warning sign"), a few words and one
// photo. Reviews describe the place; these describe a day, so every tick ends: how busy it was after a
// day, algae after a week, damage, closures and signs after a month unless another swimmer says they are
// still so. Suspected pollution and algae are labelled as what one swimmer saw until the operator has
// confirmed them from a named source. Notes are ordered worst first, and a good one never sits above,
// or reads as cancelling, a warning: theirs or the forecast's.
//
// The service is the reviews Worker (reviews/, its notes at the end of src/index.js), and the build
// writes the notes still showing into reviews/index.json, under "visits". This script uses reviews.js's
// loader, photo shrinking and photo viewer, so it loads after it. Its names begin vn, visit or VISIT.
// In Node the last lines export the parts that need no page (tests/site_visits.test.cjs).

// The ticks. days, tone and confirm must match reviews/src/rules.js (VISIT_KINDS); a test checks.
// ask: the form's words; say: the list's; sure: the list's once the operator has verified it.
const VISIT_KINDS = {
  pollution: { days: 3, tone: 'observation', ask: 'Water looked or smelled polluted', say: 'Suspected pollution', sure: 'Pollution' },
  algae: { days: 7, tone: 'observation', ask: 'Scum or algae on the water', say: 'Suspected algae', sure: 'Algae' },
  steps: { days: 30, tone: 'warning', confirm: true, ask: 'Entry steps or path damaged', say: 'Entry steps or path damaged' },
  access: { days: 14, tone: 'warning', confirm: true, ask: 'Way in closed or blocked', say: 'Way in closed or blocked' },
  rough: { days: 2, tone: 'warning', ask: 'Rough or fast water', say: 'Rough or fast water' },
  sign: { days: 30, tone: 'warning', confirm: true, ask: 'New warning sign', say: 'New warning sign' },
  'parking-closed': { days: 14, tone: 'info', confirm: true, ask: 'Car park closed', say: 'Car park closed' },
  'parking-full': { days: 1, tone: 'info', ask: 'Car park full', say: 'Car park full' },
  busy: { days: 1, tone: 'info', ask: 'Very busy', say: 'Very busy' },
  quiet: { days: 1, tone: 'info', ask: 'Quiet', say: 'Quiet' },
  clear: { days: 1, tone: 'good', ask: 'Water looked clear', say: 'Water looked clear' },
  good: { days: 1, tone: 'good', ask: 'Good swim, no problems', say: 'Good swim, no problems' },
};
const VISIT_TONES = { observation: 4, warning: 3, info: 2, good: 1 };
const VISIT_KEY = 'dipcast.visits', VISIT_CONFIRMED = 'dipcast.visits.confirmed';
const VISIT_LIMITS = { kinds: 6, text: 280 };
const VISIT_SHOW = 4;
const VISIT_REASONS = [['not-now', 'It is not like this any more'], ['not-about-spot', 'It is not about this spot'], ['rude', 'It is rude or hateful'],
  ['person', 'It shows or names someone'], ['spam', 'It is spam or advertising'], ['other', 'Something else']];
const VISIT_WEB = /https?:\/\/|www\.|\b[a-z0-9-]+\.(com|co\.uk|org|net|uk|io|ly)\b/i;
const VISIT_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 21V4"/><path d="M5 4.5h12l-2.5 4 2.5 4H5"/></svg>';

const vnEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const vnAdd = (iso, n) => new Date(Date.parse(iso + 'T12:00:00Z') + n * 86400000).toISOString().slice(0, 10);
const vnLocal = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const vnDay = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
const vnWhen = (iso, today) => (iso === today ? 'today' : iso === vnAdd(today, -1) ? 'yesterday' : `on ${vnDay(iso)}`);

// ------------------------------------------------------------------------------ no page needed

// The day a tick's days count from: the visit, or for one others can confirm, the last confirmation.
const visitFrom = (v, k) => (VISIT_KINDS[k].confirm && v.confirmed_on && v.confirmed_on > v.seen_on ? v.confirmed_on : v.seen_on);
// A note's ticks still showing on `today`, worst first; unknown ones (a newer list) left out.
function visitLive(v, today) {
  const kinds = Array.isArray(v.kinds) ? v.kinds.filter(k => Object.hasOwn(VISIT_KINDS, k)) : [];
  return kinds.filter(k => vnAdd(visitFrom(v, k), VISIT_KINDS[k].days) >= today)
    .sort((a, b) => VISIT_TONES[VISIT_KINDS[b].tone] - VISIT_TONES[VISIT_KINDS[a].tone]);
}
const visitTone = kinds => kinds.reduce((t, k) => (VISIT_TONES[VISIT_KINDS[k].tone] > VISIT_TONES[t] ? VISIT_KINDS[k].tone : t), 'good');
// The last day a tick another swimmer can confirm is shown, or null when the note has none.
function visitLasts(v, live) {
  const ends = live.filter(k => VISIT_KINDS[k].confirm).map(k => vnAdd(visitFrom(v, k), VISIT_KINDS[k].days));
  return ends.length ? ends.reduce((a, b) => (b > a ? b : a)) : null;
}

// This browser's own notes, read back safely, as reviewsMine does for reviews.
function visitsMine(text) {
  let v; try { v = JSON.parse(text || '[]'); } catch (e) { return []; }
  return Array.isArray(v) ? v.filter(r => r && typeof r === 'object' && typeof r.id === 'string' && /^[0-9a-f]{20}$/.test(r.id)
    && typeof r.spot === 'string' && (r.gone === true || (typeof r.token === 'string' && typeof r.seen_on === 'string' && Array.isArray(r.kinds)))) : [];
}

// A spot's notes as the tile lists them: every one with a tick still showing, this browser's own that
// the site does not have yet among them, its deleted ones left out. Worst first: suspected pollution
// or algae, then hazards, then the rest, then good news; the same tone, the newest first. `confirmed`
// is what this browser has confirmed (id: the service's answer), shown before the site catches up.
function visitRows(entry, mine, spot, today, confirmed = {}) {
  const published = Array.isArray(entry) ? entry : [], ids = new Set(published.map(v => v.id));
  const own = mine.filter(v => v.spot === spot), gone = new Set(own.filter(v => v.gone).map(v => v.id));
  const keys = new Set(own.filter(v => !v.gone).map(v => v.id));
  const waiting = own.filter(v => !v.gone && !ids.has(v.id)).map(v => ({ ...v, waiting: true, mine: true }));
  return [...waiting, ...published.filter(v => !gone.has(v.id)).map(v => ({ ...v, ...(confirmed[v.id] || {}), mine: keys.has(v.id) }))]
    .map(v => ({ ...v, live: visitLive(v, today) })).filter(v => v.live.length)
    .sort((a, b) => VISIT_TONES[visitTone(b.live)] - VISIT_TONES[visitTone(a.live)]
      || String(b.confirmed_on || b.seen_on).localeCompare(String(a.confirmed_on || a.seen_on)) || String(b.id).localeCompare(String(a.id)));
}

// Where a good note needs a line above it, and the line: when the forecast or a note warns. A good
// visit is one swimmer's luck on one day; it never cancels a warning. [index into rows, words], or [-1, ''].
// The rows are worst first, so every note that warns is above the first good one, or is that one.
function visitCaveat(rows, spotWarns) {
  const at = rows.findIndex(v => v.live.some(k => VISIT_KINDS[k].tone === 'good'));
  const notesWarn = rows.some(v => v.live.some(k => VISIT_TONES[VISIT_KINDS[k].tone] >= VISIT_TONES.warning));
  if (at < 0 || !(notesWarn || spotWarns)) return [-1, ''];
  return [at, notesWarn && spotWarns ? 'A good visit does not cancel a warning: the forecast and the notes above still apply.'
    : notesWarn ? 'A good visit does not cancel the warnings above.' : 'A good visit does not change the forecast above.'];
}

// The first thing wrong with a draft, in the form's words, or ''.
function visitProblem(d) {
  if (!Array.isArray(d.kinds) || !d.kinds.length) return 'Tick at least one thing you found.';
  if (d.kinds.length > VISIT_LIMITS.kinds) return `Tick at most ${VISIT_LIMITS.kinds}.`;
  if (d.when !== 'today' && d.when !== 'yesterday') return 'Say whether you were here today or yesterday.';
  if ((d.text || '').length > VISIT_LIMITS.text) return `Keep it to ${VISIT_LIMITS.text} characters.`;
  if (VISIT_WEB.test(d.text || '')) return 'Leave out web addresses.';
  if (d.photo && !d.consent) return 'Tick the box to say the photo is yours to share.';
  return '';
}

// The ticks as the list words them: the operator's verification turns "Suspected algae" into "Algae".
const visitWords = v => v.live.map(k => (v.verified && VISIT_KINDS[k].sure) || VISIT_KINDS[k].say).join(' · ');

// One note in the list. `today` for the dates; `iConfirmed` when this browser has confirmed it today.
function visitItem(v, today, { hidden = false, iConfirmed = false } = {}) {
  const lasts = visitLasts(v, v.live), seen = vnWhen(v.seen_on, today);
  const flag = !v.live.some(k => VISIT_KINDS[k].tone === 'observation') ? ''
    : v.verified ? `<p class="vn-flag">Verified: ${vnEsc(v.verified.replace(/\.+$/, ''))}.</p>`
    : '<p class="vn-flag">Not verified: what one swimmer saw, not a water test.</p>';
  // Own notes the site does not have yet: published at once, or by the operator since (state from the
  // service), reach the page at the next update; the rest wait to be checked.
  const state = !v.waiting ? '' : v.state === 'published' || (v.published && v.state !== 'pending') ? 'on this page at its next update' : 'waiting to be checked';
  const conf = v.confirmations ? `confirmed by ${v.confirmations} more swimmer${v.confirmations === 1 ? '' : 's'}, the last ${vnWhen(v.confirmed_on, today)}` : '';
  const meta = [v.mine ? 'Your note' : '', `Seen ${seen}`, conf, lasts && !v.waiting ? `shown until ${vnDay(lasts)} unless confirmed again` : '', state]
    .filter(Boolean).join(' · ');
  const p = !v.waiting && Array.isArray(v.photos) && v.photos[0];
  const pic = p ? `<ul class="rv-pics"><li><button type="button" class="rv-pic" data-photo="${vnEsc(v.id)}-0" data-w="${Number(p.w)}" data-h="${Number(p.h)}"`
    + ` aria-label="Photo with the note seen ${seen}"><img src="reviews/photos/${vnEsc(v.id)}-0-t.jpg" width="${Number(p.tw)}" height="${Number(p.th)}"`
    + ' alt="" loading="lazy" decoding="async"></button></li></ul>' : '';
  const canConfirm = !v.mine && !v.waiting && !iConfirmed && lasts && v.seen_on < today && v.confirmed_on !== today;
  const acts = v.mine ? `<button type="button" class="linkbtn small" data-vdelete="${vnEsc(v.id)}">Delete</button>`
    : v.waiting ? '' : (canConfirm ? `<button type="button" class="linkbtn small" data-confirm="${vnEsc(v.id)}">Still like this</button> · ` : '')
      + (iConfirmed ? '<span>You said it is still like this.</span> · ' : '')
      + `<button type="button" class="linkbtn small" data-vreport="${vnEsc(v.id)}">Report</button>`;
  return `<li class="rv vn vn-${visitTone(v.live)}"${hidden ? ' hidden' : ''} data-id="${vnEsc(v.id)}"><p class="rv-v">${visitWords(v)}</p>${flag}`
    + `<p class="rv-meta">${meta}</p>${v.text ? `<p class="rv-text">${vnEsc(v.text)}</p>` : ''}${pic}`
    + (acts ? `<div class="rv-acts">${acts}</div>` : '') + '</li>';
}

// Forget own notes that have ended, and deleted ones once the site has dropped them too.
function visitsTidy(mine, index, today) {
  const live = new Set(Object.values((index && index.visits) || {}).flat().map(v => v.id));
  return mine.filter(v => (v.gone ? live.has(v.id) : visitLive(v, today).length > 0));
}

// ------------------------------------------------------------------------------ the page

let visitTurn = 0;
const visitAsked = new Map();
const visitsNow = () => { try { return visitsMine(localStorage.getItem(VISIT_KEY)); } catch (e) { return []; } };
const visitsKeep = list => { try { localStorage.setItem(VISIT_KEY, JSON.stringify(list.slice(-100))); return true; } catch (e) { return false; } };
function visitsConfirmed() {
  try { const v = JSON.parse(localStorage.getItem(VISIT_CONFIRMED) || '{}'); return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; } catch (e) { return {}; }
}
const vnPost = (data, path, body) => fetch(data.submit + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

// Does the spot's own forecast warn? Then a good note says it changes nothing (levels.js).
const visitSpotWarns = d => typeof level === 'function' && typeof rank === 'function'
  && (rank(level(d)) >= 1 || (typeof advisedAgainst === 'function' && advisedAgainst(d)));

// Called with mountReviews each time the page draws a spot (index.html, render): a tile before the
// reviews. Nothing while the file loads, nothing if reviews are off, nothing if another spot opened.
async function mountVisits(d) {
  const turn = ++visitTurn;
  if (typeof reviewable !== 'function' || !reviewable(d)) return;
  const data = await reviewsLoad();
  if (turn !== visitTurn || !data || !data.on || !data.submit) return;
  const after = document.querySelector('#result .stack > .tiles');
  if (!after || document.getElementById('visits')) return;
  const today = vnLocal(), mine = visitsNow(), tidy = visitsTidy(mine, data, today);
  if (tidy.length < mine.length) visitsKeep(tidy);
  const sec = document.createElement('section');
  sec.className = 'tile rv-tile'; sec.id = 'visits'; sec.tabIndex = -1; sec.setAttribute('aria-labelledby', 'vn-h');
  const reviews = document.getElementById('reviews');
  if (reviews) reviews.before(sec); else after.after(sec);
  drawVisits(sec, d, data);
  // Own notes the site does not have yet: still waiting, published since, or turned down.
  const want = visitRows((data.visits || {})[d.id], visitsNow(), d.id, today).filter(v => v.waiting && !visitAsked.has(v.id)).map(v => v.id).slice(0, 20);
  if (!want.length) return;
  let out = {};
  try { const res = await vnPost(data, 'visits/status', { ids: want }); if (res.ok) out = await res.json(); } catch (e) { /* asked again next visit */ }
  for (const id of want) if (['pending', 'published', 'gone'].includes(out[id])) visitAsked.set(id, out[id]);
  if (turn !== visitTurn || !sec.isConnected) return;
  const gone = new Set(want.filter(id => visitAsked.get(id) === 'gone'));
  if (gone.size) visitsKeep(visitsNow().map(v => (gone.has(v.id) ? { id: v.id, spot: v.spot, gone: true } : v)));
  drawVisits(sec, d, data, gone.size ? 'A note you sent was not published, or has since been removed.' : '');
}

function drawVisits(sec, d, data, say = '') {
  if (!sec.isConnected) return;
  const today = vnLocal(), confirmed = visitsConfirmed();
  const mineConfirmed = Object.fromEntries(Object.entries(confirmed).filter(([, c]) => c && c.on === today)
    .map(([id, c]) => [id, { confirmed_on: c.on, confirmations: Number(c.confirmations) || 0 }]));
  const rows = visitRows((data.visits || {})[d.id], visitsNow(), d.id, today, mineConfirmed)
    .map(v => (v.waiting ? { ...v, state: visitAsked.get(v.id) } : v));
  const [caveatAt, caveat] = visitCaveat(rows, visitSpotWarns(d));
  let h = `<h2 class="t-lab" id="vn-h">${VISIT_ICON}<span>Recent visits</span></h2>`;
  h += `<p class="t-say">${rows.length ? 'What swimmers found here in the last few days, the warnings first.' : 'No notes from the last few days.'}`
    + `${data.complete === false ? ' The notes could not be updated this time, so the newest may be missing.' : ''}</p>`;
  if (rows.length) {
    h += '<ol class="rv-list">' + rows.map((v, i) => (i === caveatAt ? `<li class="vn-caveat"${i >= VISIT_SHOW ? ' hidden' : ''}>${caveat}</li>` : '')
      + visitItem(v, today, { hidden: i >= VISIT_SHOW, iConfirmed: Boolean(mineConfirmed[v.id]) })).join('') + '</ol>'
      + (rows.length > VISIT_SHOW ? `<button type="button" class="btn quiet" id="vn-all" aria-expanded="false">Show all ${rows.length}</button>` : '');
  }
  h += `<div class="rv-write" id="vn-write">${say ? `<p class="rv-said" id="vn-said" tabindex="-1">${say}</p>` : ''}`
    + '<button type="button" class="btn primary" id="vn-open">Say what it\'s like today</button>'
    + '<p class="t-key">Each note ends after a few days, or a month for damage and closures.</p></div>'
    + '<details class="t-more"><summary><span class="sr">Recent visits: what this means</span></summary><p>Swimmers say what they found on the day: '
    + 'getting in, parking, how busy it was, what the water looked like. Each thing ends by itself: how busy it was after a day, algae after a week, '
    + 'damage, closures and signs after a month unless another swimmer confirms it is still so. A note of pollution or algae is what one swimmer '
    + 'saw, not a test, until the site verifies it from an official source, which it names. Notes do not change the forecast, and a good one does not cancel a warning. '
    + 'Notes of ticks alone appear without being read first; words and photos are checked.</p></details>';
  sec.innerHTML = h;
  sec.onclick = e => visitClick(e, sec, d, data);
}

function visitClick(e, sec, d, data) {
  const t = e.target.closest('button'); if (!t || !sec.contains(t)) return;
  if (t.id === 'vn-all') { sec.querySelectorAll('.rv-list > [hidden]').forEach(x => { x.hidden = false; }); t.remove(); return; }
  if (t.id === 'vn-open') return visitOpenForm(sec, d, data);
  if (t.classList.contains('rv-pic') && typeof reviewShow === 'function') return reviewShow(t);
  if (t.dataset.confirm) return visitConfirm(t, sec, d, data);
  if (t.dataset.vreport) return visitReportForm(t, data);
  if (t.dataset.vdelete) {
    const p = t.parentElement;
    p.innerHTML = `<span class="rv-sure">Delete your note?</span> <button type="button" class="linkbtn small" data-vsure="${vnEsc(t.dataset.vdelete)}">Delete it</button> <button type="button" class="linkbtn small" data-vkeep="1">Keep it</button>`;
    p.querySelector('[data-vsure]').focus();
    return;
  }
  if (t.dataset.vkeep) return drawVisits(sec, d, data);
  if (t.dataset.vsure) return visitDelete(t, sec, d, data);
}

async function visitConfirm(t, sec, d, data) {
  t.disabled = true;
  const id = t.dataset.confirm, say = msg => { const p = t.closest('.rv-acts'); if (p) p.textContent = msg; };
  let res;
  try { res = await vnPost(data, 'visits/confirm', { id }); } catch (e) { return say('It could not be sent: check your connection and try again.'); }
  if (!res.ok) return say(res.status === 404 ? 'That note has ended.' : 'It could not be sent just now. Try again later.');
  const out = await res.json(), all = visitsConfirmed();
  all[id] = { on: vnLocal(), confirmations: out.confirmations };
  // Kept for today only: the site has the confirmation itself at its next update.
  try { localStorage.setItem(VISIT_CONFIRMED, JSON.stringify(Object.fromEntries(Object.entries(all).filter(([, c]) => c && c.on === vnLocal())))); } catch (e) { /* shown for this visit */ }
  drawVisits(sec, d, data, 'Thanks. That note now shows for longer.');
}

async function visitDelete(t, sec, d, data) {
  const mine = visitsNow(), v = mine.find(x => x.id === t.dataset.vsure); if (!v) return;
  t.disabled = true;
  const say = msg => { const p = t.closest('.rv-acts'); if (p) p.textContent = msg; };
  try {
    const res = await vnPost(data, 'visits/delete', { id: v.id, token: v.token });
    if (!res.ok) return say(res.status === 403 ? 'The service did not accept this browser\'s key. Email hello@swimsignal.co.uk to have it deleted.' : 'It could not be deleted just now. Try again later.');
  } catch (e) { return say('It could not be deleted: check your connection and try again.'); }
  visitsKeep(mine.map(x => (x.id === v.id ? { id: v.id, spot: v.spot, gone: true } : x)));
  drawVisits(sec, d, data, 'Your note is deleted. It leaves the site at its next update, within a few hours.');
  document.getElementById('vn-said')?.focus();
}

function visitReportForm(t, data) {
  const p = t.parentElement, id = t.dataset.vreport, sel = `vn-why-${id}`;
  p.innerHTML = `<form class="rv-report"><label class="rv-q" for="${sel}">What is wrong with it?</label><select id="${sel}">`
    + VISIT_REASONS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('') + '</select>'
    + '<span class="rv-send"><button type="submit" class="btn">Send report</button><button type="button" class="btn" data-vkeep="1">Cancel</button></span></form>';
  const f = p.querySelector('form'); f.querySelector('select').focus();
  f.onsubmit = async e => {
    e.preventDefault(); f.querySelector('[type=submit]').disabled = true;
    let ok = false;
    try { ok = (await vnPost(data, 'visits/report', { id, reason: f.querySelector('select').value })).ok; } catch (err) { ok = false; }
    p.textContent = ok ? 'Thanks. The note will be checked. It stays up until then.' : 'The report could not be sent. Email hello@swimsignal.co.uk instead.';
  };
}

// ------------------------------------------------------------------------------ writing one

function visitFormHtml() {
  const boxes = Object.entries(VISIT_KINDS).map(([id, k]) => `<label><input type="checkbox" name="kind" value="${id}"><span>${k.ask}</span></label>`).join('');
  return '<form class="rv-form" id="vn-form" novalidate data-keep-page>'
    + '<fieldset><legend class="rv-q">When were you here?</legend><div class="rv-choice">'
    + '<label><input type="radio" name="when" value="today" checked><span>Today</span></label><label><input type="radio" name="when" value="yesterday"><span>Yesterday</span></label></div></fieldset>'
    + `<fieldset><legend class="rv-q">What did you find? <span class="rv-opt">Tick any that apply</span></legend><div class="rv-choice vn-kinds">${boxes}</div></fieldset>`
    + '<p class="rv-hint vn-pol" id="vn-pol" hidden>If you think the water is polluted, tell the Environment Agency on <a href="tel:0800807060">0800 80 70 60</a>, '
    + 'or in Wales Natural Resources Wales on <a href="tel:03000653000">0300 065 3000</a>. Both answer at any hour. Here your note shows as what you saw, not as a test.</p>'
    + `<label class="rv-q" for="vn-text">Anything to add? <span class="rv-opt">Optional</span></label>`
    + `<textarea id="vn-text" name="text" rows="3" maxlength="${VISIT_LIMITS.text}" placeholder="Which steps, what the sign says"></textarea>`
    + '<p class="rv-q" id="vn-ph">Photo <span class="rv-opt">One, optional</span></p><ul class="rv-previews" id="vn-preview" aria-labelledby="vn-ph"></ul>'
    + '<label class="btn rv-add" id="vn-add"><input type="file" class="rv-file" id="vn-file" accept="image/*">Add a photo</label>'
    + '<label class="rv-consent" id="vn-consent" hidden><input type="checkbox" name="consent" value="yes"><span>I took this photo, and anyone who can be recognised in it is happy for it to be online.</span></label>'
    + '<div class="rv-hp" aria-hidden="true"><label>Leave this empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
    + '<p class="rv-hint">Ticks alone appear at the site\'s next update, within a few hours. Words or a photo are read first. Leave out other people\'s names: '
    + '<a href="terms.html#visit-notes">the rules</a> · <a href="privacy.html#visit-notes">what happens to it</a>.</p>'
    + '<div class="rv-send"><button type="submit" class="btn primary">Send note</button><button type="button" class="btn" id="vn-cancel">Cancel</button></div>'
    + '<p class="rv-msg" id="vn-msg" role="status"></p></form>';
}

function visitOpenForm(sec, d, data) {
  const box = sec.querySelector('#vn-write'); box.innerHTML = visitFormHtml();
  const f = box.querySelector('form'), msg = f.querySelector('#vn-msg'), file = f.querySelector('#vn-file'), list = f.querySelector('#vn-preview');
  const send = f.querySelector('[type=submit]');
  let photo = null, busy = false;
  const say = (text, bad = false) => { msg.textContent = text; msg.classList.toggle('bad', bad); };
  const ticked = () => [...f.querySelectorAll('input[name=kind]:checked')].map(x => x.value);
  const drawPreview = () => {
    list.innerHTML = photo ? `<li><img src="${photo.url}" alt="Your photo"><button type="button" class="linkbtn small" data-drop="1">Remove</button></li>` : '';
    f.querySelector('#vn-consent').hidden = !photo;
    f.querySelector('#vn-add').hidden = Boolean(photo);
  };
  f.addEventListener('change', e => {
    if (e.target.name === 'kind') f.querySelector('#vn-pol').hidden = !ticked().some(k => VISIT_KINDS[k].tone === 'observation');
  });
  list.addEventListener('click', e => { if (!e.target.closest('[data-drop]')) return;
    URL.revokeObjectURL(photo.url); photo = null; drawPreview(); f.querySelector('#vn-file').focus(); });
  file.addEventListener('change', async () => {
    const x = file.files[0]; file.value = ''; if (!x) return;
    if (x.size > REVIEW_LIMITS.file) { say('That photo is too large to use.', true); return; }
    busy = true; send.disabled = true; say('Getting the photo ready…');
    try { photo = await reviewShrink(x); drawPreview(); say(''); } catch (err) { say('The photo could not be read here. A JPEG or a PNG works anywhere.', true); }
    busy = false; send.disabled = false;
  });
  f.querySelector('#vn-cancel').addEventListener('click', () => { if (photo) URL.revokeObjectURL(photo.url); drawVisits(sec, d, data); sec.querySelector('#vn-open')?.focus(); });
  f.addEventListener('submit', async e => {
    e.preventDefault(); if (busy) return;
    const draft = { kinds: ticked(), when: (f.querySelector('input[name=when]:checked') || {}).value, text: f.querySelector('#vn-text').value.trim(),
      photo: Boolean(photo), consent: f.querySelector('input[name=consent]').checked };
    const problem = visitProblem(draft);
    if (problem) { say(problem, true); return; }
    const today = vnLocal(), seenOn = draft.when === 'today' ? today : vnAdd(today, -1);
    send.disabled = true; say('Sending…');
    const body = new FormData();
    body.append('spot', d.id); body.append('seen_on', seenOn); body.append('text', draft.text);
    draft.kinds.forEach(k => body.append('kind', k));
    body.append('website', f.querySelector('input[name=website]').value);
    if (photo) { body.append('consent', 'yes'); body.append('photo0', photo.full, 'photo0.jpg'); body.append('thumb0', photo.thumb, 'thumb0.jpg'); }
    let res;
    try { res = await fetch(data.submit + 'visits', { method: 'POST', body }); } catch (err) { res = null; }
    if (!res || !res.ok) {
      const why = !res ? 'Your note could not be sent. Check your connection and try again.'
        : res.status === 429 ? 'Too many notes from this connection today. Try again tomorrow.'
        : res.status === 413 ? 'The photo is too large. Try another.'
        : res.status === 400 || res.status === 503 ? (t => `${t.charAt(0).toUpperCase()}${t.slice(1)}.`)((await res.text()).trim())
        : 'The service did not answer. Try again later.';
      send.disabled = false; say(why, true); return;
    }
    const { id, token, published } = await res.json();
    const kept = visitsKeep([...visitsNow(), { id, token, spot: d.id, kinds: draft.kinds, seen_on: seenOn, text: draft.text,
      photos: photo ? 1 : 0, published: Boolean(published), sent_at: new Date().toISOString() }]);
    if (photo) URL.revokeObjectURL(photo.url);
    drawVisits(sec, d, data, (published ? 'Thanks. Your note is on this page for everyone at the site\'s next update, within a few hours.'
      : 'Thanks. Your note appears here once it has been checked, usually within a day.')
      + (kept ? '' : ' This browser is not keeping site data, so it cannot show you the note before then.'));
    document.getElementById('vn-said')?.focus();
  });
  f.querySelector('input[name=kind]').focus();
}

if (typeof module === 'object' && module.exports) {
  module.exports = { VISIT_KINDS, VISIT_TONES, VISIT_LIMITS, visitLive, visitTone, visitLasts, visitsMine, visitRows, visitCaveat, visitProblem,
    visitWords, visitItem, visitsTidy, vnAdd };
}
