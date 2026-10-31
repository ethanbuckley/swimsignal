// Ask SwimSignal (ask/, the Worker): one question in plain words on Plan a swim, and the answer under it.
// Off until the build has the Worker's address (DIPCAST_ASK_URL, build_site.ask_config), which puts
// "ask": {"url": ...} in spots.json: then askBox() gives the tile, and nothing else on the page changes.
// The question goes to the Worker only when the reader presses Ask (DESIGN.md, rule 8; the privacy
// notice's "Ask SwimSignal" section). Nothing is kept in the browser.
//
// The answer's facts are the Worker's lines from SwimSignal's data, each with its source and date; the
// model writes only the summary, how it read the question and a phrase on why each spot fits. So the view
// shows those apart: the model's words first, each spot's lines under it, as quoted data.
//
// A plain script, as plan.js: globals in the page, exports in Node.

const ASK_MAX = 300;   // characters, as the Worker's MAX_QUESTION
const ASK_TIMEOUT_MS = 45000;
const askEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const askOn = data => !!(data && data.ask && /^https:\/\/[A-Za-z0-9.-]+(:\d+)?\/$/.test(data.ask.url || ''));

// A line's date as the reader wants it: a year, a day, or a day and a time in London.
function askWhen(d) {
  if (!d) return '';
  if (/^\d{4}$/.test(d)) return d;
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  const t = Date.parse(d);
  return Number.isNaN(t) ? '' : new Date(t).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });
}
const askLink = u => /^https:\/\//.test(u || '');   // a source's own page; never another scheme
const askMiles = m => typeof m === 'number' ? `${m.toFixed(1)} miles` : '';   // as the Worker gives it, so the model's phrase agrees

// The tile: the question, and where its answer goes. '' while Ask is off.
function askBox(data) {
  if (!askOn(data)) return '';
  return '<section class="group tile ask" aria-labelledby="ask-h"><h2 class="group-head" id="ask-h">Ask SwimSignal</h2>'
    + '<form id="ask-form" class="ask-form"><label class="sr" for="ask-q">Your question</label>'
    + `<input type="text" id="ask-q" name="question" maxlength="${ASK_MAX}" autocomplete="off" enterkeyhint="send" placeholder="Within 40 minutes of Leeds, calm for paddleboarding, Saturday morning">`
    + '<button type="submit" class="btn">Ask</button></form>'
    + '<p class="planner-note">An AI model answers from SwimSignal\'s own data only, with the source and date of each fact. Your question is sent to SwimSignal and to Anthropic, which runs the model, and is not kept by SwimSignal. Leave out your name and other personal details. <a href="privacy.html#ask">Privacy</a></p>'
    + '<div id="ask-answer" aria-live="polite"></div></section>';
}

// One spot: its name, a link to its page, the model's phrase, then SwimSignal's lines.
function askSpotHtml(s, esc = askEsc) {
  const meta = [askMiles(s.miles), s.kind, s.area].filter(Boolean).join(' · ');
  const facts = s.facts.map(f => `<li${f.topic === 'official' ? ' class="ask-official"' : ''}>${esc(f.text)}`
    + `<span class="ask-src">${askLink(f.link) ? `<a href="${esc(f.link)}">${esc(f.source)}</a>` : esc(f.source)}${f.date ? `, ${esc(askWhen(f.date))}` : ''}</span></li>`).join('');
  return `<li class="ask-spot"><h3 class="ask-name"><a href="${esc(s.url)}">${esc(s.name)}</a></h3>`
    + (meta ? `<p class="ask-meta">${esc(meta)}</p>` : '')
    + (s.fit ? `<p class="ask-fit">${esc(s.fit)}</p>` : '')
    + `<ul class="ask-facts">${facts}</ul></li>`;
}

// The whole answer. Model's words in the first paragraphs; every fact after them is SwimSignal's.
function askAnswerHtml(a, esc = askEsc) {
  const unknown = [...new Set([...a.unknown, ...a.spots.flatMap(s => s.unknown)])];
  return `<h3 class="ask-h" tabindex="-1">${esc(a.day_words)}</h3>`
    + `<p class="ask-summary">${esc(a.summary)}</p>`
    + (a.assumptions.length ? `<p class="planner-note">Read as: ${a.assumptions.map(esc).join('; ')}.</p>` : '')
    + (a.spots.length ? `<ol class="ask-spots">${a.spots.map(s => askSpotHtml(s, esc)).join('')}</ol>` : '')
    + (unknown.length ? `<h3 class="ask-sub">Not known</h3><ul class="ask-unknown">${unknown.map(u => `<li>${esc(u)}</li>`).join('')}</ul>` : '')
    + a.notes.map(n => `<p class="planner-note">${esc(n)}</p>`).join('')
    + `<p class="planner-note">${a.issued_at ? `From SwimSignal's update of ${esc(askWhen(a.issued_at))}. ` : ''}Written by an AI model from that data: check a spot's page before you go. <a href="${esc(a.plan_url)}">Open in Plan a swim</a></p>`;
}

async function askSend(url, question) {
  const res = await fetch(url + 'ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
    signal: AbortSignal.timeout(ASK_TIMEOUT_MS) });
  let body = null;
  try { body = await res.json(); } catch { /* the message below */ }
  if (!res.ok || !body || !body.answer) throw new Error(body && body.error || 'Ask SwimSignal could not answer just now. Plan a swim works as always.');
  return body.answer;
}

// The page: one listener for the form, wherever the planner draws it.
if (typeof document === 'object') {
  document.addEventListener('submit', async e => {
    if (!e.target || e.target.id !== 'ask-form') return;
    e.preventDefault();
    const form = e.target, input = form.querySelector('#ask-q'), out = document.getElementById('ask-answer'), button = form.querySelector('button');
    const q = (input.value || '').trim();
    if (q.length < 3 || !out || typeof DATA === 'undefined' || !askOn(DATA)) return;
    button.disabled = true;
    out.innerHTML = '<p class="planner-note" role="status">Looking through SwimSignal\'s data…</p>';
    try {
      const a = await askSend(DATA.ask.url, q);
      out.innerHTML = askAnswerHtml(a);
      const h = out.querySelector('.ask-h');
      if (h) h.focus();
    } catch (err) {
      out.innerHTML = `<p class="planner-note" role="alert">${askEsc(err && err.name === 'TimeoutError' ? 'Ask SwimSignal took too long. Plan a swim works as always.' : err.message)}</p>`;
    } finally {
      button.disabled = false;
    }
  });
}

if (typeof module === 'object' && module.exports) {
  module.exports = { ASK_MAX, askOn, askWhen, askBox, askSpotHtml, askAnswerHtml };
}
