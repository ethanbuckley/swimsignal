// The tools the model may call. Each reads only SwimSignal's published files (SITE_URL: data/spots-lite.json,
// data/spot/<id>.json, data/places.json), never anything else, and gives back what the page would show.
// give_answer is not run here: index.js checks it (answer.js).

import { GUIDE_TOPICS, guideTopics, milesBetween, spotFacts, spotSummary } from './facts.js';

export const MAX_RESULTS = 12;
export const MAX_MILES = 60;
const ID = /^[A-Za-z0-9_-]{1,80}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;

// The files, kept for ten minutes in this isolate: the site is rebuilt at most every half hour, and one
// question reads the same files several times.
const KEEP_MS = 10 * 60 * 1000;
const cache = new Map();
export function clearCache() { cache.clear(); }

export async function readSite(env, path, { fetcher = fetch, now = Date.now() } = {}) {
  const hit = cache.get(path);
  if (hit && now - hit.at < KEEP_MS) return hit.value;
  const res = await fetcher(new URL(path, env.SITE_URL).href, { cf: { cacheTtl: 600 } });
  if (res.status === 404) { cache.set(path, { at: now, value: null }); return null; }
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  const value = await res.json();
  cache.set(path, { at: now, value });
  return value;
}

export const TOOLS = [
  {
    name: 'find_place',
    description: "Looks up a town or village in Great Britain in SwimSignal's list of places (Ordnance Survey Open Names) and gives its position. Use it for any place the question starts from. It gives up to five matches; if there is more than one, use the one the question means, or say which you used.",
    strict: true,
    input_schema: { type: 'object', additionalProperties: false, required: ['name'],
      properties: { name: { type: 'string', description: 'The place name as the person wrote it, e.g. "Leeds".' } } },
  },
  {
    name: 'search_spots',
    description: `Lists SwimSignal's spots within a straight-line distance of a position, nearest first, at most ${MAX_RESULTS}, with each spot's forecast headline for the day and the state of its official advice. Distances are straight lines, not travel times.`,
    strict: true,
    input_schema: { type: 'object', additionalProperties: false, required: ['lat', 'lon', 'within_miles', 'day', 'kind'],
      properties: {
        lat: { type: 'number' }, lon: { type: 'number' },
        within_miles: { type: 'number', description: `1 to ${MAX_MILES}.` },
        day: { type: 'string', description: 'YYYY-MM-DD, the day asked about.' },
        kind: { type: 'string', enum: ['all', 'river', 'lake'] },
      } },
  },
  {
    name: 'get_spot',
    description: "Everything SwimSignal's data says about one spot on one day, as lines with their source and date: official advice, the forecast, water temperature, air, wind, river level, access and the practical guide. The person sees exactly these lines. Call it for every spot you will recommend.",
    strict: true,
    input_schema: { type: 'object', additionalProperties: false, required: ['id', 'day'],
      properties: { id: { type: 'string' }, day: { type: 'string', description: 'YYYY-MM-DD' } } },
  },
  {
    name: 'give_answer',
    description: "Gives the answer to the person. Call it once, last. The facts for each spot are added from SwimSignal's data by the service, so do not repeat them: say only why each spot fits, in a short phrase built from those facts.",
    strict: true,
    input_schema: { type: 'object', additionalProperties: false, required: ['day', 'place', 'within_miles', 'summary', 'assumptions', 'spots', 'unknown'],
      properties: {
        day: { type: ['string', 'null'], description: 'YYYY-MM-DD, or null if the question names no day and no day was assumed.' },
        place: { type: ['string', 'null'], description: 'The place name used with find_place, or null.' },
        within_miles: { type: ['number', 'null'] },
        summary: { type: 'string', description: 'Two or three plain sentences, under 500 characters.' },
        assumptions: { type: 'array', items: { type: 'string' }, description: 'How you read the question, e.g. "40 minutes read as 25 miles in a straight line". At most three.' },
        spots: { type: 'array', description: 'Best first, at most five. Empty if none fits or the question is outside what SwimSignal covers.',
          items: { type: 'object', additionalProperties: false, required: ['id', 'fit', 'guide_topics'],
            properties: {
              id: { type: 'string' },
              fit: { type: 'string', description: 'Why it fits, under 160 characters, from the get_spot lines only.' },
              guide_topics: { type: 'array', items: { type: 'string', enum: GUIDE_TOPICS }, description: 'The guide topics the question cares about, or empty for all.' },
            } } },
        unknown: { type: 'array', items: { type: 'string' }, description: 'What the question asked that the data does not know. At most five.' },
      } },
  },
];

// Runs one tool call. Returns { content, seen } where content is what the model reads and seen notes
// what it has been shown, for the checks on its answer.
export async function runTool(name, input, ctx) {
  const { env, today, now, seen } = ctx;
  const read = (p) => readSite(env, p, ctx);
  if (name === 'find_place') {
    const want = String(input?.name || '').trim().toLowerCase();
    if (!want) return { error: 'name is empty' };
    const doc = await read('data/places.json');
    const all = doc?.places || [];
    let hits = all.filter((p) => p[0].toLowerCase() === want);
    if (!hits.length) hits = all.filter((p) => p[0].toLowerCase().startsWith(want));
    const places = hits.slice(0, 5).map(([n, lat, lon]) => ({ name: n, lat, lon }));
    for (const p of places) seen.places.set(p.name.toLowerCase(), p);
    return places.length ? { places, source: 'Ordnance Survey Open Names' } : { places: [], note: `No place called "${input.name}" in SwimSignal's list of places in Great Britain.` };
  }
  const doc = await read('data/spots-lite.json');
  if (!doc) throw new Error('data/spots-lite.json is missing');
  seen.doc = doc;
  if (name === 'search_spots') {
    const { lat, lon, within_miles: within, day, kind } = input || {};
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { error: 'lat and lon must be numbers' };
    if (!DAY.test(String(day))) return { error: 'day must be YYYY-MM-DD' };
    const miles = Math.min(Math.max(Number(within) || 10, 1), MAX_MILES);
    const from = { lat, lon };
    seen.searches.push({ lat, lon, within_miles: miles });
    const near = doc.spots
      .filter((s) => kind === 'all' || !kind || s.kind === kind)
      .map((s) => ({ s, d: milesBetween(lat, lon, s.lat, s.lon) }))
      .filter((x) => x.d <= miles)
      .sort((a, b) => a.d - b.d)
      .slice(0, MAX_RESULTS)
      .map((x) => spotSummary(x.s, day, doc, from));
    for (const x of near) seen.listed.add(x.id);
    return { day, within_miles: miles, distances: 'straight line', spots: near,
      ...(near.length ? {} : { note: `No SwimSignal spot within ${miles} miles.` }) };
  }
  if (name === 'get_spot') {
    const { id, day } = input || {};
    if (!ID.test(String(id))) return { error: 'unknown spot id' };
    if (!DAY.test(String(day))) return { error: 'day must be YYYY-MM-DD' };
    const s = doc.spots.find((x) => x.id === id);
    if (!s) return { error: `No spot with id ${id} in SwimSignal's data.` };
    const detail = s.detail_file ? await read(`data/${s.detail_file}`) : s;
    seen.spots.set(id, { s, detail });
    const { facts, unknown } = spotFacts(s, detail, { day, today, now, doc });
    return { id, name: s.name, kind: s.kind, area: s.area, day, guide_topics: guideTopics(detail),
      facts: facts.map((f) => ({ text: f.text, source: f.source, date: f.date })), unknown };
  }
  return { error: `No tool called ${name}.` };
}

export const newSeen = () => ({ places: new Map(), searches: [], listed: new Set(), spots: new Map(), doc: null });
