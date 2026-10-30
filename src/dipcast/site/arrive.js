// The arrival guide (prototype, docs/ARRIVAL-GUIDE-2026-10.md): a spot's practical guide in the order a first-time
// visitor needs it, for the task "I have never been here. Get me from the car park or bus stop to the water, in and
// out, and tell me what nobody has checked." Shown only with ?arrive=1 in the address (index.html, mountArrival), in
// the guide tile's place, so the page is unchanged without it.
//
// The facts are the guide's (guides/<spot id>.toml, guide.js), word for word, each with its line of who says so
// (guideRuns): nothing is added to a fact, and no fact is moved between the parts. Three parts are kept apart and
// never joined into one answer, since each can be true without the others:
//   the way there and back   bus and train, parking, the path, getting in, getting out, toilets, then the seasons
//                            and opening times: the guide's topics as a journey, numbered, a step with no fact
//                            saying so, and a step a photo would make findable saying when there is none;
//   who can swim here        the guide's rules and the desk check of access (access.py), never inferred from a
//                            path, a car park or a beach;
//   the water                a link to the forecast above, which is not restated here.
// Then "What nobody has checked": every step with nothing, every missing photo, the questions the guide's format has
// no place for yet, and how the verified facts were checked. A reader can then say, from the tile alone, which facts
// are verified (by whom, when), which are a swimmer's word, and which are not known.
//
// A plain script, like replay.js: in the page its names are globals (each begins arrival or ARRIVAL, clear of the
// page's own arriveSentence), it uses guide.js's helpers, which the page has already loaded, and in Node the last
// lines export them (tests/site_arrive.test.cjs).

const arrivalGuide = () => (typeof guideRuns === 'function'
  ? { guideRuns, guideChecked, guidePhoto, GUIDE_TOPICS } : require('./guide.js'));
const arrivalEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// The journey, in order. Each step names the guide's topics it shows, under the guide's own headings where a step
// holds two; `photo` is what a photograph at that step would show, for the line that says there is none yet.
// Who can swim (rules) is not a step: it is its own part, after the journey.
const ARRIVAL_STEPS = [
  { key: 'there', title: 'Getting there', topics: ['transport', 'parking'] },
  { key: 'path', title: 'From the road to the water', topics: ['path'], photo: 'the path to the water' },
  { key: 'entry', title: 'Getting in', topics: ['entry'], photo: 'the place to get in' },
  { key: 'exit', title: 'Getting out', topics: ['exit'], photo: 'the place to get out' },
  { key: 'facilities', title: 'Toilets and changing', topics: ['toilets', 'changing'] },
  { key: 'seasons', title: 'Seasons, opening times and fees', topics: ['hours', 'fees'] },
];
// The guide's headings, as a step's sub-headings where it holds more than one topic; "Bus and train" and "Parking"
// read as the two ways of getting there.
const ARRIVAL_SUB = { transport: 'By bus or train', parking: 'By car' };
const arrivalSub = k => ARRIVAL_SUB[k] || (new Map(arrivalGuide().GUIDE_TOPICS)).get(k) || k;
// What a first-time visitor asks that no topic in the guide's format holds yet (guides/README.md): said on every
// guide, so a reader does not take silence for an answer. In the page's own words, not facts.
const ARRIVAL_ASKED = [
  'How deep the water is where you get in, at its usual level.',
  'Whether there is a step-free route from the road to the water\'s edge.',
  'How far the stop, the station and each car park are from the water, on foot.',
  'Whether a phone has signal at the water.',
];

// A camera, in the stroke set (index.html, ICON): beside the line that says a step has no photo yet.
const ARRIVAL_CAMERA = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3.5L9 5.5h6L16.5 8H20v11H4Z"/><circle cx="12" cy="13.5" r="3.2"/></svg>';

// The guide's facts by topic, in the order guides.py sorted them (verified first).
function arrivalBy(g) {
  const by = new Map();
  for (const f of (g && Array.isArray(g.facts) ? g.facts : [])) {
    if (!f || typeof f.topic !== 'string') continue;
    if (!by.has(f.topic)) by.set(f.topic, []);
    by.get(f.topic).push(f);
  }
  return by;
}

// How many facts are of each kind, and from how many pages: the tile's second line. A fact from a dated record
// (source_date) is counted apart from a current page, as guide.js labels it "Source", not "Verified".
function arrivalCounts(g) {
  const facts = g && Array.isArray(g.facts) ? g.facts : [];
  const n = { verified: 0, dated: 0, suggested: 0, pages: 0 };
  const pages = new Set();
  for (const f of facts) {
    if (f.status === 'suggested') { n.suggested++; continue; }
    if (f.status !== 'confirmed') continue;
    if (f.source_date) n.dated++; else n.verified++;
    if (f.source) pages.add(f.source);
  }
  n.pages = pages.size;
  return n;
}
const arrivalPlural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
function arrivalCountsSaid(g) {
  const n = arrivalCounts(g);
  const parts = [`${arrivalPlural(n.verified, 'fact')} verified`];
  if (n.dated) parts.push(`${n.dated} from dated records`);
  parts.push(n.suggested ? `${n.suggested} a swimmer's word, not checked` : 'none a swimmer\'s word');
  return `In this guide: ${parts.join(', ')}; ${arrivalPlural(n.pages, 'published page')} in all.`;
}

// The steps, each with its topics' facts or the fact that it has none, and its photo line. Pure: the tests read it.
// A photo in the guide is not yet tied to a step (the format has no field for it), so with any photo at all the
// steps do not claim theirs is missing; the photos show after the journey.
function arrivalSteps(g) {
  const by = arrivalBy(g), photos = !!(g && Array.isArray(g.photos) && g.photos.length);
  return ARRIVAL_STEPS.map(s => {
    const parts = s.topics.map(k => ({ topic: k, facts: by.get(k) || [] }));
    return { ...s, parts, empty: parts.every(p => !p.facts.length), noPhoto: !!s.photo && !photos };
  });
}

// "What nobody has checked": the steps with nothing, the photos not taken, the questions with no place in the
// format, the suggestions not checked, and how the verified facts were checked. Plain text, escaped when written.
function arrivalUnknowns(g, d = {}) {
  const out = [];
  const steps = arrivalSteps(g);
  for (const s of steps) {
    if (s.empty) out.push(`${s.title}: nothing in this guide.`);
    else for (const p of s.parts) if (!p.facts.length) out.push(`${s.key === 'there' ? `${s.title} ${arrivalSub(p.topic).toLowerCase()}` : arrivalSub(p.topic)}: nothing in this guide.`);
  }
  const by = arrivalBy(g);
  if (!(by.get('rules') || []).length && !(d && d.access)) out.push('Who can swim here: nothing in this guide.');
  const shots = steps.filter(s => s.noPhoto).map(s => s.photo);
  if (shots.length) out.push(`No photo yet of ${shots.length > 1 ? `${shots.slice(0, -1).join(', ')} or ${shots[shots.length - 1]}` : shots[0]}.`);
  out.push(...ARRIVAL_ASKED);
  const n = arrivalCounts(g);
  if (n.suggested) out.push(`${arrivalPlural(n.suggested, 'fact')} above ${n.suggested === 1 ? 'is' : 'are'} a swimmer's word that SwimSignal has not checked.`);
  if (g && g.how === 'desk') out.push('Nobody from SwimSignal has been here: every verified fact comes from a published page, not a visit.');
  return out;
}

// One run of facts under its line of who says so, as the tile writes them (guide.js, guideFacts).
const arrivalRuns = facts => arrivalGuide().guideRuns(facts)
  .map(r => `<dd>${r.texts.map(t => `<p class="g-text">${arrivalEsc(t)}</p>`).join('')}<p class="g-src">${r.src}</p></dd>`).join('');
const arrivalNone = what => `<p class="arr-none">${what}</p>`;

function arrivalStep(s, i) {
  // A step of two topics names each under the guide's heading, unless both are empty, when one line says so.
  const many = s.parts.length > 1 && !s.empty;
  const body = many
    ? '<dl class="g-facts arr-facts">' + s.parts.map(p => `<div class="arr-part"><dt>${arrivalEsc(arrivalSub(p.topic))}</dt>`
      + (p.facts.length ? arrivalRuns(p.facts) : `<dd>${arrivalNone('Nothing in this guide yet.')}</dd>`) + '</div>').join('') + '</dl>'
    : s.empty ? arrivalNone('Nothing in this guide yet.') : `<dl class="g-facts arr-facts"><div class="arr-part">${arrivalRuns(s.parts[0].facts)}</div></dl>`;
  const shot = s.noPhoto ? `<p class="arr-shot">${ARRIVAL_CAMERA}<span>No photo yet of ${s.photo}.</span></p>` : '';
  const plan = s.key === 'there' ? '<p class="arr-plan">Times and routes: <a href="https://www.traveline.info/">Traveline journey planner</a>.</p>' : '';
  return `<li class="arr-step" id="arr-${s.key}"><h4 class="arr-t"><span class="arr-n">${i + 1}</span>${s.title}</h4>${body}${plan}${shot}</li>`;
}

// Who can swim here: the guide's rules, word for word, and the desk check of access where the build has one.
// Nothing is concluded from the way in: a path, a car park or a beach is not permission.
function arrivalPermission(g, d = {}) {
  const rules = arrivalBy(g).get('rules') || [];
  const a = d && d.access && typeof d.access.text === 'string' && d.access.text ? d.access : null;
  const desk = a ? `<dd><p class="g-text">${arrivalEsc(a.text)}</p><p class="g-src">${/^https:\/\//.test(a.url || '') ? `<a href="${arrivalEsc(a.url)}">Authority guidance</a>. ` : ''}`
    + `Desk check ${arrivalEsc(a.checked_at || '')}; current signs have not been inspected.</p></dd>` : '';
  const body = rules.length || desk ? `<dl class="g-facts arr-facts"><div class="arr-part">${desk}${rules.length ? arrivalRuns(rules) : ''}</div></dl>`
    : arrivalNone('Nothing in this guide says who may swim here.');
  return '<section class="arr-sec" aria-labelledby="arr-who-h"><h3 class="arr-h" id="arr-who-h">Who can swim here</h3>'
    + '<p class="arr-say">A path, a car park or a beach is not permission to swim. This part says only what its sources say.</p>' + body + '</section>';
}

// The water: the forecast above answers it. Nothing here restates a level, a reading or advice.
const arrivalWater = () => '<section class="arr-sec" aria-labelledby="arr-water-h"><h3 class="arr-h" id="arr-water-h">The water</h3>'
  + '<p class="arr-say">Pollution risk for the next five days, and the Environment Agency\'s advice where there is any, are in '
  + '<a href="#risk-hero">the forecast at the top of this page</a>. Nothing in this guide is about the water.</p></section>';

// The tile, in the guide's place (id guide, so the notes on a visit and the reviews still mount after it).
function arrivalTile(d, today) {
  if (!d || d.unlisted || d.detail_missing) return '';
  const G = arrivalGuide();
  const g = d.guide && Array.isArray(d.guide.facts) && d.guide.facts.length ? d.guide : null;
  const icon = (typeof ICON === 'object' && ICON.route) || '';
  const head = `<h2 class="t-lab" id="guide-h">${icon}<span>Arriving for the first time</span></h2>`;
  const checked = g ? `<p class="t-say">${G.guideChecked(g, today)}</p><p class="arr-count">${arrivalCountsSaid(g)}</p>`
    : '<p class="t-say">There is no practical guide for this spot yet: every step below is unknown.</p>';
  const steps = arrivalSteps(g || { facts: [] });
  const photos = g && Array.isArray(g.photos) && g.photos.length
    ? `<div class="arr-photos">${g.photos.map((p, i) => G.guidePhoto(p, i, g)).join('')}</div>` : '';
  const ask = '<p class="g-ask">Been here? <a href="feedback.html?type=guide&amp;spot=' + encodeURIComponent(d.name || '')
    + '">Tell us what you found</a>: the way down, where you got in and out, and photos.</p>';
  return `<section class="tile g-tile arr" id="guide" aria-labelledby="guide-h">${head}${checked}`
    + '<section class="arr-sec" aria-labelledby="arr-way-h"><h3 class="arr-h" id="arr-way-h">The way there and back</h3>'
    + `<ol class="arr-steps">${steps.map(arrivalStep).join('')}</ol>${photos}</section>`
    + arrivalPermission(g || {}, d) + arrivalWater()
    + '<section class="arr-sec" aria-labelledby="arr-unk-h"><h3 class="arr-h" id="arr-unk-h">What nobody has checked</h3>'
    + `<ul class="arr-unk">${arrivalUnknowns(g || { facts: [] }, d).map(t => `<li>${arrivalEsc(t)}</li>`).join('')}</ul></section>`
    + ask + '</section>';
}

if (typeof module === 'object' && module.exports) {
  module.exports = { ARRIVAL_STEPS, ARRIVAL_ASKED, arrivalCounts, arrivalCountsSaid, arrivalSteps, arrivalUnknowns, arrivalPermission, arrivalTile };
}
