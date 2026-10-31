// Checks the model's give_answer against what it was shown, and builds the reply the page draws.
// The model writes only a summary, its assumptions, a short "why it fits" for each spot and what it
// could not answer. Every fact the reader sees comes from facts.js. The checks below refuse an answer
// that says "safe" or "clean", names a spot it did not look up, puts a condition or a number in its words
// that the data did not give it, or names a level for a day the forecast does not cover.

import { KIDS_NOTE, TRAVEL_NOTE, dayWords, milesBetween, spotFacts, spotURL } from './facts.js';
import levels from '../../src/dipcast/site/levels.js';

const { OTHER_RISKS } = levels;

export const MAX_SPOTS = 5;
const LIMITS = { summary: 600, fit: 200, line: 200 };

// Never in the model's words: the water is never called safe or clean, by any form of the words.
export const NEVER = /\b(safe|safer|safest|safely|unsafe|safety|clean|cleaner|cleanest|cleanliness|unpolluted|uncontaminated|pollution[- ]free|sewage[- ]free|risk[- ]free|harmless|guaranteed?|healthy)\b/i;
// Never in the model's words either: a judgement for children SwimSignal does not make (KIDS_NOTE says so).
export const KIDS = /\b(kid|child|family|toddler|beginner)[- ]?friendly\b|\bsuitable for (?:young )?(?:children|kids|families|toddlers|beginners)\b|\bgood for (?:children|kids|families)\b/i;
// Conditions at the water: allowed in the model's words only where the lines it was shown use the word.
export const CONDITIONS = /\b(calm|calmer|flat|choppy|windy|breezy|gusty|sheltered|shallow|deep|warm|warmer|warmest|cold|colder|coldest|chilly|clear|murky|gentle|slow[- ]flowing|fast[- ]flowing|sunny|dry|rainy|quiet|busy)\b/gi;
const LEVEL_WORDS = /\b(low|moderate|high|very high) risk\b/i;
const NUMBER = /\d+(?:\.\d+)?/g;

// The text the model may draw its words from: the question, what each tool gave it and the notes here.
function corpusOf(question, toolTexts) {
  return [question, ...toolTexts, KIDS_NOTE, TRAVEL_NOTE, OTHER_RISKS].join('\n').toLowerCase();
}

// Problems with one piece of the model's text. corpus: what it may draw on.
export function textProblems(text, corpus, where) {
  const out = [];
  const m = text.match(NEVER);
  if (m) out.push(`${where} says "${m[0]}": never call the water or a spot safe, clean or the like.`);
  const k = text.match(KIDS);
  if (k) out.push(`${where} says "${k[0]}": SwimSignal does not judge suitability for children.`);
  for (const c of new Set((text.match(CONDITIONS) || []).map((w) => w.toLowerCase()))) {
    if (!new RegExp(`\\b${c.replace('-', '[- ]')}\\b`).test(corpus)) out.push(`${where} says "${c}", which no line from the data says.`);
  }
  for (const n of new Set(text.match(NUMBER) || [])) {
    if (!corpus.includes(n)) out.push(`${where} gives the number ${n}, which is not in the data or the question.`);
  }
  return out;
}

const trim = (t, max) => String(t ?? '').replace(/\s+/g, ' ').trim().slice(0, max);

// Checks give_answer. Returns { problems, answer } where answer is null when there are problems.
export function checkAnswer(input, ctx) {
  const { question, seen, today, now, env, toolTexts } = ctx;
  const problems = [];
  const corpus = corpusOf(question, toolTexts);
  const doc = seen.doc;
  const day = input?.day && /^\d{4}-\d{2}-\d{2}$/.test(input.day) ? input.day : today;
  const summary = trim(input?.summary, LIMITS.summary);
  if (!summary) problems.push('summary is empty.');
  problems.push(...textProblems(summary, corpus, 'The summary'));
  const assumptions = (Array.isArray(input?.assumptions) ? input.assumptions : []).slice(0, 3).map((a) => trim(a, LIMITS.line)).filter(Boolean);
  assumptions.forEach((a, i) => problems.push(...textProblems(a, corpus, `Assumption ${i + 1}`)));
  const unknownLines = (Array.isArray(input?.unknown) ? input.unknown : []).slice(0, 5).map((a) => trim(a, LIMITS.line)).filter(Boolean);
  unknownLines.forEach((a, i) => problems.push(...textProblems(a, corpus, `Unknown ${i + 1}`)));

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
    // A spot's own words may use only its own lines, the question and the notes.
    const own = corpusOf(question, [built.facts.map((f) => f.text).join('\n'), got.s.name, got.s.area || ''].concat(toolTexts.filter((t) => t.includes(id))));
    problems.push(...textProblems(fit, own, `The fit for ${got.s.name}`));
    spots.push({ got, built, fit });
  }
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
