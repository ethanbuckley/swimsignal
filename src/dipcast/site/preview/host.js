// SwimSignal, the redesign: what the live site's own feature scripts expect of the page they run in. Swimmers'
// reviews, notes on a visit and reports of illness (reviews.js, visits.js, illness.js) are loaded here as they are,
// so what a swimmer is asked and told is the same on both sites, and each draws itself into the place's page
// (app.js, mountSwimmers). On the live page these few names are the page's own (index.html and guide.js); a plain
// script, so they are globals here too, as those scripts expect.

// "Show all": the rest show, the button goes, and focus moves to the first one shown (guide.js, showRest).
function showRest(rows, button) {
  const first = rows[0];
  rows.forEach(x => { x.hidden = false; });
  button.remove();
  if (first && first.focus) { first.tabIndex = -1; first.focus(); }
}

// What has been typed into a form, kept in this page's memory only, by place and form, so a form closed and opened
// again has its words back; a reload or closing the tab clears it. Photos are not kept. Nothing is sent.
// (index.html, draftTrack, word for word.)
const DRAFTS = new Map();
const draftKey = (form, spot) => `${spot}:${form.id}`;
const draftFields = form => [...form.querySelectorAll('textarea, input:not([type=file]), select')].filter(el => el.name !== 'website' && el.name !== 'consent');
function draftTrack(form, spot) {
  const key = draftKey(form, spot), fields = draftFields(form), saved = DRAFTS.get(key);
  const restored = saved && saved.fields.length === fields.length;
  if (restored) {
    fields.forEach((el, i) => { const v = saved.fields[i]; if (el.type === 'checkbox' || el.type === 'radio') el.checked = v.checked; else el.value = v.value; });
    fields.forEach(el => el.dispatchEvent(new Event('change', { bubbles: true })));
  }
  const noteAt = typeof form.querySelector === 'function' && form.querySelector('[data-draft-note]');
  (noteAt || form).insertAdjacentHTML(noteAt ? 'beforeend' : 'afterbegin', `<p class="small muted" role="status">${restored ? `Draft restored.${saved.photos ? ' Please add photos again.' : ''} ` : ''}Unsent answers stay in this tab's memory until it is closed or reloaded. Photos must be added again after leaving the page.</p>`);
  let photos = !!(saved && saved.photos);
  const save = () => DRAFTS.set(key, { photos, fields: fields.map(el => ({ value: el.value, checked: !!el.checked })) });
  form.addEventListener('input', save);
  form.addEventListener('change', e => { if (e.target.type === 'file' && e.target.files && e.target.files.length) photos = true; save(); }, true);
  form.addEventListener('click', e => { if (e.target.closest('button[id$="-cancel"]')) DRAFTS.delete(key); }, true);
}
const draftForget = (form, spot) => DRAFTS.delete(draftKey(form, spot));

// Words typed into one of those forms (data-keep-page) are lost by leaving, so the page asks first: the browser's
// own question for closing, reloading or another site, and this one for a link to another of these pages. The
// browser's Back button is not asked about: it cannot be held. (index.html, unsent.)
const unsent = () => [...document.querySelectorAll('form[data-keep-page]')].some(f =>
  [...f.querySelectorAll('textarea, input, select')].some(e => e.type === 'checkbox' || e.type === 'radio'
    ? e.checked !== e.defaultChecked : e.tagName === 'SELECT'
      ? e.value !== ((e.querySelector('option[selected]') || e.options[0]) || {}).value
      : e.type !== 'file' && e.value !== e.defaultValue) || !!f.querySelector('.rv-previews img'));
let leaving = false;   // asked once already: a link to another page is not asked about again on unload
document.addEventListener('input', () => { leaving = false; });
window.addEventListener('beforeunload', e => { if (!leaving && unsent()) { e.preventDefault(); e.returnValue = ''; } });
document.addEventListener('click', e => {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
  // A link away from this place. A day's tab and a link to a part of this page keep the place, and the form with it.
  const c = e.target.closest && e.target.closest('#app a[href]');
  if (!c || c.dataset.day || c.getAttribute('href').startsWith('#') || c.closest('form[data-keep-page]') || c.closest('#result') || !unsent()) return;
  if (confirm('Leave this page? What you have written here will be lost.')) { leaving = true; return; }
  e.preventDefault(); e.stopImmediatePropagation();
}, true);
