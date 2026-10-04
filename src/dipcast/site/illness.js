// "I got ill after swimming here", on a spot's page: a short form for a swimmer to say they were ill
// after a swim here, and the counts of such reports. A report is information about health, so the form
// asks for the least that can test a forecast (the day of the swim, the kinds of symptom as ticks, the
// days until the first, and whether they saw a doctor or called 111), nothing that names anyone, and a
// tick that consents in so many words; and no report is ever shown, only a spot's counts, from five.
// The service is the reviews Worker (reviews/, the end of src/index.js), where reports are off until
// switched on; the build puts the counts in reviews/index.json, under "illness", only while they are on.
//
// This script uses reviews.js's loader (reviewsLoad) and its rule for which spots take reviews, so it
// loads after it. Its names begin il, illness or ILLNESS. In Node the last lines export the parts that
// need no page (tests/site_illness.test.cjs).

// The kinds of symptom: the service's ids (reviews/src/rules.js, ILLNESS_SYMPTOMS; a test keeps the two
// the same) and the form's words. The UK Health Security Agency and the Environment Agency name stomach
// upsets and ear, eye, skin and respiratory infections as illnesses open water can bring ("Swim healthy",
// updated 24 June 2019); a fever goes under something else.
const ILLNESS_SYMPTOMS = [['gut', 'Sickness, diarrhoea or stomach pain'], ['ear', 'Ear pain or infection'], ['eye', 'Sore or red eyes'],
  ['skin', 'Rash or itchy skin'], ['other', 'Something else, such as a fever']];
const ILLNESS_ONSET = [[0, 'The same day'], [1, 'The next day'], [2, 'Two days after'], [3, 'Three or more days after']];
const ILLNESS_KEY = 'dipcast.illness';   // this browser's own reports: id, key, spot and the day sent; nothing about the illness
const ILLNESS_DAYS_BACK = 14, ILLNESS_KEEP_DAYS = 400;   // as the service's (rules.js)
const ILLNESS_ICON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13.5V5a2 2 0 0 1 4 0v8.5a4 4 0 1 1-4 0Z"/><path d="M12 9v7.5"/></svg>';

const ilEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const ilAdd = (iso, n) => new Date(Date.parse(iso + 'T12:00:00Z') + n * 86400000).toISOString().slice(0, 10);
const ilLocal = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const ilDay = (iso, opts) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', opts);

// ------------------------------------------------------------------------------ no page needed

// The tile's figure and sentence from a spot's counts ({ d30, d365 }, d30 null when under the threshold),
// or for a spot without counts. A count is always at least `min`, so always plural.
function illnessWords(c, min) {
  if (!c || !c.d365) return { fig: null, say: `No count to show: fewer than ${min} swimmers have reported being ill after swimming here in the last 12 months.` };
  return c.d30
    ? { fig: [c.d30, 'reports in the last 30 days'], say: `${c.d30} swimmers reported being ill after swimming here in the last 30 days, and ${c.d365} in the last 12 months.` }
    : { fig: [c.d365, 'reports in the last 12 months'], say: `${c.d365} swimmers reported being ill after swimming here in the last 12 months, fewer than ${min} of them in the last 30 days.` };
}

// The days a swim can be on, today and the 14 before, newest first, with the words the form shows.
function illnessDays(today) {
  return Array.from({ length: ILLNESS_DAYS_BACK + 1 }, (_, i) => {
    const iso = ilAdd(today, -i), words = ilDay(iso, { weekday: 'long', day: 'numeric', month: 'long' });
    return [iso, i === 0 ? `Today, ${words}` : i === 1 ? `Yesterday, ${words}` : words];
  });
}
// The onsets possible after a swim on `swam`: none that would start after today.
const illnessOnsets = (swam, today) => ILLNESS_ONSET.map(([n]) => n).filter(n => ilAdd(swam, n) <= today);

// The first thing wrong with a draft, in the form's words, or ''.
function illnessProblem(d, today) {
  if (!illnessDays(today).some(([iso]) => iso === d.swam_on)) return `Choose the day you swam, in the last ${ILLNESS_DAYS_BACK} days.`;
  if (!Array.isArray(d.symptoms) || !d.symptoms.length) return 'Tick at least one kind of symptom.';
  if (!illnessOnsets(d.swam_on, today).includes(d.onset)) return 'Say when it started.';
  if (!d.consent) return 'Tick the box to agree that SwimSignal keeps this information about your health.';
  return '';
}
// The report as the service takes it: the doctor answer only when given.
const illnessBody = (d, spot) => ({ spot, swam_on: d.swam_on, symptoms: d.symptoms, onset: d.onset,
  ...(typeof d.doctor === 'boolean' ? { doctor: d.doctor } : {}), consent: true, website: d.website || '' });

// This browser's own reports, read back safely; one older than the service keeps reports is dropped.
function illnessMine(text, today) {
  let v; try { v = JSON.parse(text || '[]'); } catch (e) { return []; }
  return Array.isArray(v) ? v.filter(r => r && typeof r === 'object' && typeof r.id === 'string' && /^[0-9a-f]{20}$/.test(r.id)
    && typeof r.token === 'string' && typeof r.spot === 'string' && typeof r.sent_on === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(r.sent_on)
    && (!today || r.sent_on > ilAdd(today, -ILLNESS_KEEP_DAYS))) : [];
}

// ------------------------------------------------------------------------------ the page

let illnessTurn = 0;
const illnessNow = () => { try { return illnessMine(localStorage.getItem(ILLNESS_KEY), ilLocal()); } catch (e) { return []; } };
const illnessKeep = list => { try { localStorage.setItem(ILLNESS_KEY, JSON.stringify(list.slice(-20))); return true; } catch (e) { return false; } };

// Called with mountReviews each time the page draws a spot (index.html, reviewsFor): a tile after the
// reviews. Nothing while the file loads, nothing unless reports are on, nothing if another spot opened.
async function mountIllness(d) {
  const turn = ++illnessTurn;
  if (typeof reviewable !== 'function' || !reviewable(d)) return;
  const data = await reviewsLoad();
  if (turn !== illnessTurn || !data || !data.on || !data.submit || !data.illness || data.illness.on !== true) return;
  const after = document.getElementById('reviews') || document.getElementById('visits')
    || document.querySelector('#result .stack > #guide') || document.querySelector('#result .stack > .tiles');
  if (!after || document.getElementById('illness')) return;
  const sec = document.createElement('section');
  sec.className = 'tile rv-tile'; sec.id = 'illness'; sec.tabIndex = -1; sec.setAttribute('aria-labelledby', 'il-h');
  after.after(sec);
  drawIllness(sec, d, data);
}

// The tile: the label, the count as its figure, one sentence that says the reports are unverified, this
// browser's own reports with Delete, the button, and the line on getting help.
function drawIllness(sec, d, data, say = '') {
  if (!sec.isConnected) return;
  const min = Number(data.illness.min) || 5, w = illnessWords((data.illness.spots || {})[d.id], min);
  // This browser's own reports of this spot. One sent in the last 14 days covers any swim it could be
  // about, so the button stays away until then: one illness, one report.
  const mine = illnessNow().filter(r => r.spot === d.id), sent = mine.some(r => r.sent_on > ilAdd(ilLocal(), -ILLNESS_DAYS_BACK));
  let h = `<h2 class="t-lab" id="il-h">${ILLNESS_ICON}<span>Illness after swimming</span></h2>`;
  if (w.fig) h += `<p class="t-fig">${w.fig[0]}<small>${w.fig[1]}</small></p>`;
  h += `<p class="t-say">${w.say}${w.fig ? ' Unverified: what swimmers told the site, not a test of the water or a diagnosis.' : ''}`
    + `${data.complete === false ? ' The counts could not be updated this time.' : ''}</p>`;
  h += `<div class="rv-write" id="il-write">${say ? `<p class="rv-said" id="il-said" tabindex="-1">${say}</p>` : ''}`
    + mine.map(r => `<p class="rv-acts il-mine">You sent a report from this browser on ${ilDay(r.sent_on, { day: 'numeric', month: 'short' })}. `
      + `<button type="button" class="linkbtn small" data-ildelete="${ilEsc(r.id)}">Delete it</button></p>`).join('')
    + (sent ? '' : '<button type="button" class="btn" id="il-open">I got ill after swimming here</button>') + '</div>'
    // Outside the part the form replaces, so it stays in view while the form is open. The UKHSA's and the
    // Environment Agency's advice: seek medical help and say you have been open water swimming ("Swim healthy").
    + '<p class="t-key">Unwell now? Call 111 or go to <a href="https://111.nhs.uk/">111.nhs.uk</a>, and say you swam in open water. '
    + 'Reports here do not reach the NHS or any health authority.</p>'
    + '<details class="t-more"><summary><span class="sr">Illness after swimming: what this means</span></summary><p>A swimmer can say they were ill '
    + 'after swimming here: the day they swam, the kind of symptoms and when they started. Nobody checks a report, and illness has many causes, '
    + 'food and other people among them, so a count does not show that the water made anyone ill. The site shows only counts, from five reports, '
    + 'so that no one can be picked out, and a report counts from the day after it is sent. Counts do not change the forecast, and no count does not '
    + 'mean the water is clean. SwimSignal keeps the reports to test its forecasts against them.</p></details>';
  sec.innerHTML = h;
  sec.onclick = e => illnessClick(e, sec, d, data);
}

function illnessClick(e, sec, d, data) {
  const t = e.target.closest('button'); if (!t || !sec.contains(t)) return;
  if (t.id === 'il-open') return illnessOpenForm(sec, d, data);
  if (t.dataset.ildelete) {
    const p = t.parentElement;
    p.innerHTML = `<span class="rv-sure">Delete your report for good?</span> <button type="button" class="linkbtn small" data-ilsure="${ilEsc(t.dataset.ildelete)}">Delete it</button>`
      + ' <button type="button" class="linkbtn small" data-ilkeep="1">Keep it</button>';
    p.querySelector('[data-ilsure]').focus();
    return;
  }
  if (t.dataset.ilkeep) return drawIllness(sec, d, data);
  if (t.dataset.ilsure) return illnessDelete(t, sec, d, data);
}

// Deleting withdraws the sender's consent: the service deletes the report at once, whatever else it holds.
async function illnessDelete(t, sec, d, data) {
  const mine = illnessNow(), r = mine.find(x => x.id === t.dataset.ilsure); if (!r) return;
  t.disabled = true;
  const say = msg => { const p = t.closest('.il-mine'); if (p) p.textContent = msg; };
  try {
    const res = await fetch(data.submit + 'illness/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: r.id, token: r.token }) });
    if (!res.ok) return say(res.status === 403 ? 'The service did not accept this browser\'s key. Email hello@swimsignal.co.uk with the spot and the day you swam to have it deleted.'
      : 'It could not be deleted just now. Try again later.');
  } catch (err) { return say('It could not be deleted: check your connection and try again.'); }
  illnessKeep(mine.filter(x => x.id !== r.id));
  drawIllness(sec, d, data, 'Your report is deleted. The counts change at the site\'s next update, within a few hours.');
  document.getElementById('il-said')?.focus();
}

// ------------------------------------------------------------------------------ sending one

// The form: a question to each field, in the order a swimmer answers them, with the chips of the notes on
// a visit (visits.js, vn-kinds). The consent is its own tick and names the information as health.
function illnessFormHtml(today) {
  const days = illnessDays(today).map(([iso, words]) => `<option value="${iso}">${words}</option>`).join('');
  const ticks = ILLNESS_SYMPTOMS.map(([id, words]) => `<label><input type="checkbox" name="symptom" value="${id}"><span>${words}</span></label>`).join('');
  const onsets = ILLNESS_ONSET.map(([n, words]) => `<label><input type="radio" name="onset" value="${n}"><span>${words}</span></label>`).join('');
  // data-keep-page: the page does not reload itself to fetch a newer forecast while this is open (index.html).
  return '<form class="rv-form" id="il-form" novalidate data-keep-page>'
    + `<label class="rv-q" for="il-swam">When did you swim here?</label><select id="il-swam" name="swam_on">${days}</select>`
    + `<fieldset><legend class="rv-q">What did you have? <span class="rv-opt">Tick any that apply</span></legend><div class="rv-choice vn-kinds">${ticks}</div></fieldset>`
    + `<fieldset><legend class="rv-q">When did it start?</legend><div class="rv-choice vn-kinds">${onsets}</div></fieldset>`
    + '<fieldset><legend class="rv-q">Did you see a doctor or call 111 about it? <span class="rv-opt">Optional</span></legend><div class="rv-choice">'
    + '<label><input type="radio" name="doctor" value="yes"><span>Yes</span></label><label><input type="radio" name="doctor" value="no"><span>No</span></label></div></fieldset>'
    + '<label class="rv-consent"><input type="checkbox" name="consent" value="yes"><span>I agree that SwimSignal keeps this information about my health. '
    + 'It is deleted after about 13 months, and only ever published as part of a count of five or more reports.</span></label>'
    + '<div class="rv-hp" aria-hidden="true"><label>Leave this empty <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>'
    + '<p class="rv-hint">Report only your own illness, and only once. The report has no name and no words. '
    + '<a href="privacy.html#illness">What happens to it</a> · <a href="terms.html#illness">the rules</a>.</p>'
    + '<div class="rv-send"><button type="submit" class="btn primary">Send report</button><button type="button" class="btn" id="il-cancel">Cancel</button></div>'
    + '<p class="rv-msg" id="il-msg" role="status"></p></form>';
}

function illnessOpenForm(sec, d, data) {
  const today = ilLocal(), box = sec.querySelector('#il-write');
  box.innerHTML = illnessFormHtml(today);
  const f = box.querySelector('form'), msg = f.querySelector('#il-msg'), send = f.querySelector('[type=submit]'), swam = f.querySelector('#il-swam');
  const say = (text, bad = false) => { msg.textContent = text; msg.classList.toggle('bad', bad); };
  // An onset that would fall after today cannot be chosen: after a swim today, only "the same day".
  const fit = () => {
    const ok = illnessOnsets(swam.value, today);
    f.querySelectorAll('input[name=onset]').forEach(x => { x.disabled = !ok.includes(Number(x.value)); if (x.disabled) x.checked = false; });
  };
  swam.addEventListener('change', fit); fit();
  f.querySelector('#il-cancel').addEventListener('click', () => { drawIllness(sec, d, data); sec.querySelector('#il-open')?.focus(); });
  f.addEventListener('submit', async e => {
    e.preventDefault();
    const pick = name => (f.querySelector(`input[name=${name}]:checked`) || {}).value;
    const draft = { swam_on: swam.value, symptoms: [...f.querySelectorAll('input[name=symptom]:checked')].map(x => x.value),
      onset: pick('onset') === undefined ? null : Number(pick('onset')), doctor: pick('doctor') === undefined ? null : pick('doctor') === 'yes',
      consent: f.querySelector('input[name=consent]').checked, website: f.querySelector('input[name=website]').value };
    const problem = illnessProblem(draft, today);
    if (problem) { say(problem, true); return; }
    send.disabled = true; say('Sending…');
    let res;
    try {
      res = await fetch(data.submit + 'illness', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(illnessBody(draft, d.id)) });
    } catch (err) { res = null; }
    if (!res || !res.ok) {
      const why = !res ? 'Your report could not be sent. Check your connection and try again.'
        : res.status === 429 ? 'Too many reports from this connection today. Try again tomorrow.'
        : res.status === 400 || res.status === 503 ? (t => `${t.charAt(0).toUpperCase()}${t.slice(1)}.`)((await res.text()).trim())
        : 'The service did not answer. Try again later.';
      send.disabled = false; say(why, true); return;
    }
    const { id, token } = await res.json();
    const kept = illnessKeep([...illnessNow(), { id, token, spot: d.id, sent_on: today }]);
    drawIllness(sec, d, data, 'Thanks. Your report is added to this spot\'s counts tomorrow.'
      + (kept ? ' You can delete it from this browser at any time.'
        : ' This browser is not keeping site data, so it cannot delete the report later: email hello@swimsignal.co.uk with the spot and the day you swam.'));
    document.getElementById('il-said')?.focus();
  });
  swam.focus();
}

if (typeof module === 'object' && module.exports) {
  module.exports = { ILLNESS_SYMPTOMS, ILLNESS_ONSET, ILLNESS_DAYS_BACK, ILLNESS_KEEP_DAYS, illnessWords, illnessDays, illnessOnsets, illnessProblem, illnessBody, illnessMine, ilAdd };
}
