// What SwimSignal's published data says about one spot on one day, as lines a reader can check: each
// with its source and its date. The model reads these lines (get_spot) and the reader sees the same
// lines, written here and not by the model, so the answer cannot carry a condition the data does not.
// The level words and the advice are the page's own (src/dipcast/site/levels.js), so Ask never says
// something different from the spot's page.

import levels from '../../src/dipcast/site/levels.js';

const { dayHeadline, dayAction, daily, eaUnchecked, EA_UNCHECKED, ORDER, OTHER_RISKS, NO_FORECAST, plainLevel, dayLevel, isolated } = levels;

export const SOURCE = {
  forecast: "SwimSignal's forecast",
  ea: 'Environment Agency',
  weather: "Open-Meteo's weather forecast, in SwimSignal's update",
  access: "SwimSignal's desk check of access",
  swimsignal: "SwimSignal's data",
};
export const WIND_UNKNOWN = "Wind: not known. SwimSignal's data has no wind forecast, so it cannot say whether the water will be calm.";
export const LAKE_WIND = 'In a lake, the wind decides where river water goes. The forecast does not use wind.';
export const NO_GUIDE = 'No practical guide for this spot yet.';
export const KIDS_NOTE = 'SwimSignal does not rate spots as suitable for children or for paddleboarding. What the guides say about getting in, paths and toilets is given instead.';
export const TRAVEL_NOTE = 'Distances are in a straight line. Travel time is not known: SwimSignal has no road or public transport times.';
// The topics a practical guide can have (guides/*.toml), for give_answer's choice of what to show.
export const GUIDE_TOPICS = ['parking', 'transport', 'path', 'entry', 'exit', 'toilets', 'changing', 'fees', 'hours', 'rules', 'paddle', 'launch'];
const GUIDE_WORDS = { parking: 'Parking', transport: 'Getting there', path: 'Path', entry: 'Getting in', exit: 'Getting out',
  toilets: 'Toilets', changing: 'Changing', fees: 'Fees', hours: 'Opening hours', rules: 'Rules', paddle: 'Paddling', launch: 'Launching' };

const MILE_KM = 1.609344;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
export const dayWords = (iso) => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
const timeWords = (iso) => new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });

export function milesBetween(lat1, lon1, lat2, lon2) {
  const r = (d) => (d * Math.PI) / 180;
  const a = Math.sin(r(lat2 - lat1) / 2) ** 2 + Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lon2 - lon1) / 2) ** 2;
  return (2 * 6371.0088 * Math.asin(Math.sqrt(a))) / MILE_KM;
}

// The days the update forecasts: the first five of a spot that has them, as the page shows.
export const forecastDays = (doc) => {
  const s = (doc.spots || []).find((x) => daily(x));
  return s ? s.days.slice(0, 5).map((d) => d.date) : [];
};

// The level line for a day, in the page's words, and whether it is known.
export function levelFact(s, day, doc) {
  const issued = s.query?.issued_at || doc.generated_at;
  const inWindow = !daily(s) || s.days.slice(0, 5).some((d) => d.date === day);
  const level = inWindow ? dayLevel(s, day) : NO_FORECAST;
  if (level === NO_FORECAST) {
    const days = forecastDays(doc);
    const range = days.length ? ` It covers ${dayWords(days[0])} to ${dayWords(days[days.length - 1])}.` : '';
    return { topic: 'forecast', known: false, level, source: SOURCE.forecast, date: issued,
      text: `Forecast for ${dayWords(day)}: not known. SwimSignal's update has no forecast for that day here.${range}` };
  }
  const head = dayHeadline(s, day);
  const action = dayAction(s, day);
  const plain = plainLevel(level) ? ` ${OTHER_RISKS}` : '';
  return { topic: 'forecast', known: true, level, source: SOURCE.forecast, date: issued,
    text: `${dayWords(day)}: ${head}.${plain}${action ? ' ' + action : ''}` };
}

// Official advice first, always: a notice in the data, or, at a designated bathing water, that today's
// could not be checked, or that the data has none.
export function officialFacts(s, doc) {
  const out = [];
  for (const o of Array.isArray(s.official) ? s.official : []) {
    out.push({ topic: 'official', restricts: !!o.restricts, source: o.publisher || SOURCE.ea, date: o.checked || o.since || null,
      link: o.link || null, text: `Official advice: ${o.line}.` });
  }
  if (out.length) return out;
  if (eaUnchecked(s)) {
    out.push({ topic: 'official', restricts: false, source: SOURCE.ea, date: null, link: s.classification?.url || null,
      text: `Official advice: ${EA_UNCHECKED} Check the Environment Agency's page for this bathing water before you go.` });
  } else {
    out.push({ topic: 'official', restricts: false, source: SOURCE.swimsignal, date: doc.generated_at, link: null,
      text: 'Official advice: none in SwimSignal\'s data for this spot. Check the signs at the water.' });
  }
  return out;
}

function waterFact(s, day, today, now) {
  const w = s.water_temp, e = s.water_temp_est;
  const t = w ? Date.parse(w.observed_at) : NaN;
  const forDay = day === today ? '' : ` This is today's; nothing is known for ${dayWords(day)}.`;
  if (w && typeof w.temp_c === 'number' && !Number.isNaN(t) && now - t < 24 * 3600 * 1000) {
    const where = [w.where, w.river ? `on the ${w.river}` : '', typeof w.river_km === 'number' && w.direction ? `${w.river_km} km ${w.direction} of the spot` : '']
      .filter(Boolean).join(', ');
    return { topic: 'water', known: true, source: `${SOURCE.ea} water sensor`, date: w.observed_at, link: w.url || null,
      text: `Water temperature: ${Math.round(w.temp_c * 10) / 10} °C measured ${where}.${w.quality === 'Unchecked' ? ' The EA has not yet checked the reading.' : ''}${forDay}` };
  }
  if (e && typeof e.temp_c === 'number' && e.date === today && (s.kind === 'river' || s.kind === 'lake')) {
    const how = !e.route || e.route === 'river_model' ? 'an estimate, not a measurement' : 'a provisional estimate from air temperatures, not a measurement';
    return { topic: 'water', known: true, source: SOURCE.forecast, date: e.date, link: null,
      text: `Water temperature: about ${e.temp_c} °C near the surface today, ${how}.${forDay}` };
  }
  return { topic: 'water', known: false, source: SOURCE.swimsignal, date: null, link: null, text: 'Water temperature: not known in this update.' };
}

function airFact(s, day, doc) {
  const x = (s.weather?.days || []).find((d) => d.date === day);
  if (!x) return { topic: 'air', known: false, source: SOURCE.weather, date: null, link: null, text: `Air temperature for ${dayWords(day)}: not known.` };
  const parts = [typeof x.tmax === 'number' ? `air up to ${x.tmax} °C` : '', x.sunrise ? `sunrise ${x.sunrise}` : '', x.sunset ? `sunset ${x.sunset}` : ''].filter(Boolean);
  return { topic: 'air', known: true, source: SOURCE.weather, date: doc.generated_at, link: null, text: `${dayWords(day)}: ${parts.join(', ')}.` };
}

function riverFact(s, now) {
  const r = s.river_state;
  if (!r || !r.label) return null;
  const rise = typeof r.rise_6h_m === 'number' && Math.abs(r.rise_6h_m) >= 0.05 ? `, ${r.rise_6h_m > 0 ? 'rising' : 'falling'} ${Math.abs(r.rise_6h_m)} m over 6 hours` : '';
  const old = r.stale || (Date.parse(r.observed_at) && now - Date.parse(r.observed_at) > 12 * 3600 * 1000) ? ' The reading is old.' : '';
  return { topic: 'river', known: true, source: `${SOURCE.ea} river level gauge`, date: r.observed_at, link: null,
    text: `River level: ${r.label} for the time of year at the ${r.station} gauge${r.same_river === false ? ' (on another river)' : ''}${rise}, at ${timeWords(r.observed_at)}. This is the level now, not on the day.${old}` };
}

function floodFacts(s) {
  const n = Array.isArray(s.flood_alerts) ? s.flood_alerts.length : 0;
  return n ? [{ topic: 'flood', known: true, source: `${SOURCE.ea} flood warnings`, date: null, link: null,
    text: `Flood alerts: ${n} in force here when SwimSignal last updated. The spot's page lists them.` }] : [];
}

export function guideFacts(detail, topics) {
  const g = detail?.guide;
  if (!g || !Array.isArray(g.facts) || !g.facts.length) return [];
  const want = topics && topics.length ? new Set(topics) : null;
  const seen = new Map();
  const out = [];
  for (const f of g.facts) {
    if (want && !want.has(f.topic)) continue;
    const n = seen.get(f.topic) || 0;
    if (n >= 2) continue;   // two lines a topic: the rest are on the spot's page
    seen.set(f.topic, n + 1);
    out.push({ topic: 'guide', guide_topic: f.topic, known: true, source: f.source_name || 'the guide\'s source', date: g.checked || null,
      link: /^https:\/\//.test(f.source || '') ? f.source : null, text: `${GUIDE_WORDS[f.topic] || cap(f.topic)}: ${f.text}` });
  }
  return out;
}

export const guideTopics = (detail) => [...new Set((detail?.guide?.facts || []).map((f) => f.topic))];

export function spotURL(site, s, day) {
  return `${site}spot/${encodeURIComponent(s.id)}/${daily(s) && day ? '#day=' + day : ''}`;
}

// Every line for a spot on a day, official advice first. topics: the guide's topics to show (all if empty).
export function spotFacts(s, detail, { day, today, now, doc, topics = [] }) {
  const facts = [...officialFacts(s, doc)];
  if (s.classification?.class) {
    facts.push({ topic: 'rating', known: true, source: SOURCE.ea, date: String(s.classification.year || ''), link: s.classification.url || null,
      text: `Bathing water rating: ${s.classification.class} (${s.classification.year}).` });
  }
  const level = levelFact(s, day, doc);
  const restricts = facts.some((f) => f.topic === 'official' && f.restricts);
  // As the planner says it: the official advice comes first, and the forecast is separate information.
  facts.push(restricts ? { ...level, text: `Follow the official advice above. The sewage forecast is separate information: ${level.text}` } : level);
  if (s.algae?.date) {
    facts.push({ topic: 'algae', known: true, source: SOURCE.ea, date: s.algae.date, link: null,
      text: `Algae at the Environment Agency's last check: ${s.algae.phrase}.` });
  }
  facts.push(waterFact(s, day, today, now), airFact(s, day, doc));
  facts.push({ topic: 'wind', known: false, source: SOURCE.swimsignal, date: null, link: null,
    text: WIND_UNKNOWN + (s.kind === 'lake' ? ' ' + LAKE_WIND : '') });
  const river = riverFact(s, now);
  if (river) facts.push(river);
  facts.push(...floodFacts(s));
  if (s.access?.text) {
    facts.push({ topic: 'access', known: true, source: SOURCE.access, date: s.access.checked_at || null, link: s.access.url || null,
      text: `Access: ${s.access.text}` });
  }
  const guide = guideFacts(detail, topics.length ? [...new Set([...topics, 'rules'])] : []);   // the rules always
  facts.push(...guide);
  const unknown = facts.filter((f) => f.known === false).map((f) => f.text);
  if (!detail?.guide?.facts?.length) unknown.push(NO_GUIDE);
  else if (topics.length && !guide.length) unknown.push(`The guide says nothing about ${topics.join(', ')}.`);
  return { facts, unknown, level: level.level, level_known: level.known,
    restricts, raised: ORDER[level.level] >= 2 };
}

// One line a spot for search_spots: enough to choose which to look at.
export function spotSummary(s, day, doc, from) {
  const level = levelFact(s, day, doc);
  const off = officialFacts(s, doc)[0];
  return {
    id: s.id, name: s.name, kind: s.kind, area: s.area,
    miles: from ? Math.round(milesBetween(from.lat, from.lon, s.lat, s.lon) * 10) / 10 : null,
    level: level.known ? dayHeadline(s, day) : 'Forecast not known for that day',
    official: off.restricts ? 'restricts swimming' : off.source === SOURCE.ea && !s.official ? 'could not be checked today' : s.official ? 'notice' : 'none in data',
    isolated: isolated(s),
  };
}
