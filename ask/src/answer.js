// Checks the model's give_answer against what it was shown, and builds the reply the page draws.
// The model writes only a summary, its assumptions, a short "why it fits" for each spot and what it
// could not answer. Every fact the reader sees comes from facts.js. The checks below refuse an answer
// that says "safe" or "clean", names a spot it did not look up, puts a condition or a number in its words
// that the data did not give it, or names a level for a day the forecast does not cover.
// Only what the tools gave back approves a condition or a number: never the question (the person's words
// say what they want, not what the water is) and never the model's own tool inputs. A line saying a
// condition is not known does not approve it, and words about one spot may use only that spot's lines.
// A condition the lines do not affirm may appear only in the unknown list, asked as "Whether ...".

import { KIDS_NOTE, TRAVEL_NOTE, dayWords, milesBetween, spotFacts, spotURL } from './facts.js';
import levels from '../../src/dipcast/site/levels.js';

const { OTHER_RISKS } = levels;

export const MAX_SPOTS = 5;
const LIMITS = { summary: 600, fit: 200, line: 200 };

// Never in the model's words: the water is never called safe or clean, by any form of the words.
export const NEVER = /\b(safe|safer|safest|safely|unsafe|safety|clean|cleaner|cleanest|cleanliness|unpolluted|uncontaminated|pollution[- ]free|sewage[- ]free|risk[- ]free|harmless|guaranteed?|healthy)\b/i;
// Never in the model's words either: a judgement for children SwimSignal does not make (KIDS_NOTE says so).
export const KIDS = /\b(kid|child|family|toddler|beginner)[- ]?friendly\b|\bsuitable for (?:young )?(?:children|kids|families|toddlers|beginners)\b|\bgood for (?:children|kids|families)\b/i;
// Conditions at the water: allowed in the model's words only where a line it was shown says so.
export const CONDITIONS = /\b(calm|calmer|flat|still water|glassy|smooth|placid|tranquil|rough|wavy|choppy|windy|breezy|gusty|sheltered|shallow|deep|warm|warmer|warmest|mild|balmy|cold|colder|coldest|chilly|icy|freezing|clear|murky|gentle|slow[- ]flowing|fast[- ]flowing|sunny|dry|rainy|quiet|busy)\b/gi;
const LEVEL_WORDS = /\b(low|moderate|high|very high) risk\b/i;
const NUMBER = /\d+(?:\.\d+)?/g;
// A unit after a number, and the units that are the same: 2 steps is not 2 miles.
const UNIT = /^\s*-?\s*(°\s*c|degrees?|%|per ?cent|miles?|mi|kilomet(?:re|er)s?|km|metres?|meters?|m|cm|mm|feet|foot|ft|yards?|steps?|minutes?|mins?|hours?|hrs?|h|days?|weeks?|years?)(?![a-z])/i;
const SAME = { degree: '°c', c: '°c', 'per cent': '%', percent: '%', mi: 'mile', kilometre: 'km', kilometer: 'km',
  metre: 'm', meter: 'm', feet: 'ft', foot: 'ft', min: 'minute', h: 'hour', hr: 'hour' };
function unitOf(word) {
  const u = word.toLowerCase().replace(/\s+/g, ' ').replace('° c', '°c');
  const one = u.length > 3 && u.endsWith('s') ? u.slice(0, -1) : u;
  return SAME[u] ?? SAME[one] ?? one;
}
// Each unit a number is given with in a text, null for none: the word after it, or the key before it ("miles":11.7).
function unitsOf(n, text) {
  const out = new Set();
  for (const m of text.matchAll(new RegExp(`(?<![\\d.])${n.replace('.', '\\.')}(?!\\d|\\.\\d)`, 'g'))) {
    const after = text.slice(m.index + n.length).match(UNIT);
    const key = text.slice(Math.max(0, m.index - 40), m.index).match(/(?:^|[^a-z])([a-z]+)"?\s*:\s*$/);
    out.add(after ? unitOf(after[1]) : key && UNIT.test(key[1]) ? unitOf(key[1]) : null);
  }
  return out;
}

// A line from the data in clauses, each holding one claim at most.
const clauses = (t) => String(t).toLowerCase().split(/(?<!\d)[.,:](?!\d)|[!?;"\n()]|\s(?:and|but|so|while|though|although)\s/).map((c) => c.trim()).filter(Boolean);
// The model's text in claims: a list ("calm, warm and shallow") stays one claim, and a new subject
// ("and it is calm") or "but" or "so" starts another.
const claims = (t) => String(t).toLowerCase().split(/(?<!\d)[.:](?!\d)|[!?;\n]|,?\s(?:but|so|yet|while|though|although|whereas)\s|,?\s(?:and|which|where)\s(?=(?:it|its|it's|the|this|that|there|they|these|those|here|[a-z]+ (?:is|are|was|were|will|has|have))\b)/).map((c) => c.trim()).filter(Boolean);
// A line that says a condition is not known, or not so, does not approve it ("cannot say whether the water will be calm").
const NEGATED = /\b(not|no|never|none|nothing|unknown|cannot|can't|isn't|aren't|won't|whether|without)\b/;
const has = (c, text) => new RegExp(`\\b${c.replace('-', '[- ]')}\\b`).test(text);
const linesSay = (c, lines) => clauses(lines).some((l) => has(c, l) && !NEGATED.test(l));
// In the unknown list, a claim that asks ("Whether the water will be calm", "How deep it is") may name a
// condition or the question's number. Nowhere else does a hedge, a "not known" or the person's own words
// let one through: "No wind forecast means the water is calm" says the water is calm.
const ASKS = /^(?:whether|how|if)\b/;

// Problems with one piece of the model's text. from: the lines that may approve a condition or a number,
// as one text, or { every, numbers, question }: a condition must be in each text of every (each spot a
// sentence speaks of) and a number in numbers. unknown: the text is a line of the unknown list.
// assumption: the text is an assumption, which may restate the question's numbers before "read as"
// ("40 minutes read as 25 miles"); what it was read as must still be the data's.
export function textProblems(text, from, where, { unknown = false, assumption = false } = {}) {
  const src = typeof from === 'string' ? { every: [from], numbers: from } : from;
  const question = String(src.question || '').toLowerCase();
  const out = [];
  const m = text.match(NEVER);
  if (m) out.push(`${where} says "${m[0]}": never call the water or a spot safe, clean or the like.`);
  const k = text.match(KIDS);
  if (k) out.push(`${where} says "${k[0]}": SwimSignal does not judge suitability for children.`);
  const said = new Set();
  for (const claim of claims(text)) {
    const asks = unknown && ASKS.test(claim);
    const readAs = assumption ? claim.indexOf(' read as ') : -1;
    for (const c of claim.matchAll(CONDITIONS)) {
      const w = c[0].toLowerCase();
      if (said.has(w) || asks || src.every.every((lines) => linesSay(w, lines))) continue;
      said.add(w);
      out.push(`${where} says "${w}", which no line from the data says${src.every.length > 1 ? ' for every spot it speaks of' : ''}. `
        + 'A missing forecast or the question\'s words never say what the water is: put it in unknown, as "Whether the water will be …".');
    }
    for (const n of claim.matchAll(NUMBER)) {
      const u = claim.slice(n.index + n[0].length).match(UNIT);
      const unit = u ? unitOf(u[1]) : null;
      const given = (t) => { const seen = unitsOf(n[0], String(t).toLowerCase()); return unit ? seen.has(unit) : seen.size > 0; };
      if (said.has(`${n[0]} ${unit}`) || given(src.numbers) || ((asks || n.index < readAs) && given(question))) continue;
      said.add(`${n[0]} ${unit}`);
      out.push(u ? `${where} gives ${n[0]} ${u[1].trim()}, which the data does not give with that unit.` : `${where} gives the number ${n[0]}, which is not in the data.`);
    }
  }
  return out;
}

const NOTES = [KIDS_NOTE, TRAVEL_NOTE, OTHER_RISKS].join('\n');
// What the tools gave back (index.js, ctx.shown), never what the model sent them: all of it, the part
// about no one spot (places, the search's distance), and one spot's own (its get_spot and search lines).
function shownOf(shown) {
  const text = (x) => JSON.stringify(x);
  const all = [...shown.map((x) => text(x.out)), NOTES].join('\n');
  const general = [...shown.map((x) => (x.name === 'find_place' ? text(x.out) : x.name === 'search_spots' ? text({ ...x.out, spots: [] }) : '')), NOTES].join('\n');
  const own = (id, extra = []) => [...extra, ...shown.flatMap((x) => (x.name === 'get_spot' && x.out?.id === id ? [text(x.out)]
    : x.name === 'search_spots' ? (x.out?.spots || []).filter((s) => s.id === id).map(text) : [])), NOTES].join('\n');
  return { all, general, own };
}

// The words a spot goes by: "Wharfe at Cromwheel, Ilkley" is also Cromwheel and Ilkley.
const nameParts = (s) => [s.name, ...s.name.split(/,|\(|\)|\s+at\s+/)].map((p) => p.trim().toLowerCase()).filter((p) => p.length >= 4);
const sentences = (t) => String(t).split(/(?<=[.!?])\s+|\n/).filter((x) => x.trim());

const trim = (t, max) => String(t ?? '').replace(/\s+/g, ' ').trim().slice(0, max);

// Checks give_answer. Returns { problems, answer } where answer is null when there are problems.
export function checkAnswer(input, ctx) {
  const { question, seen, today, now, env, shown: results = [] } = ctx;
  const problems = [];
  const shown = shownOf(results);
  const doc = seen.doc;
  const day = input?.day && /^\d{4}-\d{2}-\d{2}$/.test(input.day) ? input.day : today;
  const summary = trim(input?.summary, LIMITS.summary);
  if (!summary) problems.push('summary is empty.');
  const assumptions = (Array.isArray(input?.assumptions) ? input.assumptions : []).slice(0, 3).map((a) => trim(a, LIMITS.line)).filter(Boolean);
  const unknownLines = (Array.isArray(input?.unknown) ? input.unknown : []).slice(0, 5).map((a) => trim(a, LIMITS.line)).filter(Boolean);
  unknownLines.forEach((a, i) => problems.push(...textProblems(a, { every: [shown.all], numbers: shown.all, question }, `Unknown ${i + 1}`, { unknown: true })));

  const picked = Array.isArray(input?.spots) ? input.spots.slice(0, MAX_SPOTS) : [];
  const ids = new Set();
  const spots = [];
  for (const p of picked) {
    const id = String(p?.id || '');
    if (ids.has(id)) continue;
    ids.add(id);
    const got = seen.spots.get(id);
    if (!got) { problems.push(`Spot ${id} was not looked up with get_spot, so it cannot be recommended.`); continue; }
    const topics = Array.isArray(p.guide_topics) ? p.guide_topics : [];
    const built = spotFacts(got.s, got.detail, { day, today, now, doc, topics });
    const fit = trim(p.fit, LIMITS.fit);
    // A spot's own words may use only its own lines and the notes; a distance may also be the search's.
    const own = shown.own(id, [...built.facts.map((f) => f.text), got.s.name, got.s.area || '']);
    problems.push(...textProblems(fit, { every: [own], numbers: own + '\n' + shown.general, question }, `The fit for ${got.s.name}`));
    spots.push({ got, built, fit });
  }
  // A sentence that names spots may use only their lines. One that names none speaks of every spot
  // given (or looked up, if none is given), so a condition in it must be in the lines of each.
  const ownOf = (id) => shown.own(id, [seen.spots.get(id).s.name, seen.spots.get(id).s.area || '']);
  const scoped = (text, where, opts) => sentences(text).flatMap((t) => {
    const lower = t.toLowerCase();
    const named = [...seen.spots.keys()].filter((id) => nameParts(seen.spots.get(id).s).some((p) => lower.includes(p)));
    const looked = spots.length ? spots.map((x) => x.got.s.id) : [...seen.spots.keys()];
    const every = (named.length ? named : looked).map(ownOf);
    return textProblems(t, { every, numbers: named.length ? [...named.map(ownOf), shown.general].join('\n') : shown.all, question }, where, opts);
  });
  problems.unshift(...scoped(summary, 'The summary'), ...assumptions.flatMap((a, i) => scoped(a, `Assumption ${i + 1}`, { assumption: true })));
  if (spots.length && !spots.some((x) => x.built.level_known) && LEVEL_WORDS.test(summary)) {
    problems.push(`The summary names a level, but the forecast does not cover ${dayWords(day)} at these spots: say it is not known.`);
  }
  if (problems.length) return { problems, answer: null };

  // Official advice first: a spot whose official advice restricts swimming goes after the others,
  // whatever the model's order, and a raised level after the rest of those.
  const rankOf = (x) => (x.built.restricts ? 2 : x.built.raised ? 1 : 0);
  const order = spots.map((x, i) => ({ x, i })).sort((a, b) => rankOf(a.x) - rankOf(b.x) || a.i - b.i).map((a) => a.x);
  const from = input.place ? seen.places.get(String(input.place).toLowerCase()) : null;
  const site = env.SITE_URL;
  const answer = {
    question, day, day_words: dayWords(day), issued_at: doc?.generated_at || null,
    summary, assumptions,
    spots: order.map(({ got, built, fit }) => ({
      id: got.s.id, name: got.s.name, kind: got.s.kind, area: got.s.area || null,
      miles: from ? Math.round(milesBetween(from.lat, from.lon, got.s.lat, got.s.lon) * 10) / 10 : null,
      fit, url: spotURL(site, got.s, day), restricts: built.restricts,
      facts: built.facts.map(({ topic, text, source, date, link }) => ({ topic, text, source, date, link: link || null })),
      unknown: built.unknown,
    })),
    unknown: unknownLines,
    notes: [OTHER_RISKS, ...(from ? [TRAVEL_NOTE] : []), ...(KIDS_ASKED.test(question) ? [KIDS_NOTE] : [])],
    plan_url: planURL(site, day, from, input.within_miles, order.map((x) => x.got.s)),
  };
  return { problems: [], answer };
}

const KIDS_ASKED = /\b(kids?|child|children|family|families|toddlers?|little ones|beginners?)\b/i;

// Plan a swim with the same day, place and distance (plan.js, readPlan): after the #, so it never
// reaches a server. The planner's distances are 5, 10, 20, 30 or 50 miles; the next one up is used.
export function planURL(site, day, from, within, spots) {
  const q = new URLSearchParams();
  if (day) q.set('day', day);
  if (from) { q.set('from', from.name); q.set('at', `${from.lat},${from.lon}`); }
  const radius = [5, 10, 20, 30, 50].find((r) => r >= (Number(within) || 0));
  if (from && within) q.set('within', String(radius ?? 0));
  const kinds = new Set(spots.map((s) => s.kind));
  if (kinds.size === 1) q.set('kind', [...kinds][0]);
  return `${site}plan/${[...q].length ? '#' + q.toString() : ''}`;
}

// When the model gives no usable answer: the facts for the spots it looked up, in its order of looking,
// with a plain summary, so the reader still gets what the data says, or a pointer to Plan a swim.
export function fallbackAnswer(ctx, why) {
  const { question, seen, today, now, env } = ctx;
  const doc = seen.doc;
  const spots = [...seen.spots.values()].slice(0, 3).map(({ s, detail }) => {
    const built = spotFacts(s, detail, { day: today, today, now, doc });
    return { id: s.id, name: s.name, kind: s.kind, area: s.area || null, miles: null, fit: '', url: spotURL(env.SITE_URL, s, today),
      restricts: built.restricts, facts: built.facts.map(({ topic, text, source, date, link }) => ({ topic, text, source, date, link: link || null })), unknown: built.unknown };
  });
  return {
    question, day: today, day_words: dayWords(today), issued_at: doc?.generated_at || null,
    summary: spots.length ? "SwimSignal could not write a full answer to that. Here is what its data says about the spots it looked at, for today."
      : "SwimSignal could not answer that from its data. Plan a swim lists the spots near a town on a day.",
    assumptions: [], spots, unknown: [], notes: [OTHER_RISKS], plan_url: `${env.SITE_URL}plan/`, partial: why,
  };
}
