// Each spot's level, headline and what to do, for the alerts service (push/): written beside
// spots.json by scripts/build_site.py. The rules are the page's own (src/dipcast/site/levels.js),
// run here in Node, so an alert says what the page says.
//
//   node scripts/alerts.js site/data/spots.json site/data/alerts.json https://example.org/swim/
const fs = require('fs');
const path = require('path');
const L = require(path.join(__dirname, '..', 'src', 'dipcast', 'site', 'levels.js'));

const [src, out, root] = process.argv.slice(2);
if (!src || !out || !root || !root.endsWith('/')) {
  console.error('usage: node scripts/alerts.js <spots.json> <alerts.json> <site root ending in />');
  process.exit(2);
}
const data = JSON.parse(fs.readFileSync(src, 'utf8'));
L.setToday(data.generated_at.slice(0, 10));
const PAGE_ID = /^[A-Za-z0-9_-]+$/;   // the page and build_site.py use the same rule
// The lowest level of the four days after today and the days that have it, for the weekly note
// (push/src/weekly.js), in the page's words: "Saturday, low risk", "tomorrow and Sunday, moderate
// risk", "low risk every day from tomorrow to Monday". Only where the level changes from day to day.
// A water rated poor is at least high every day, which is what its note says.
const dayName = x => L.dayWord(x.date).replace(/^on /, '');
const andList = ws => ws.length < 2 ? ws[0] : `${ws.slice(0, -1).join(', ')} and ${ws.at(-1)}`;
function best(s) {
  if (!L.daily(s)) return null;
  const ahead = s.days.slice(1, 5), days = ahead.map(x => ({ x, l: L.dayLevel(s, x.date) })).filter(d => L.ORDER[d.l] !== undefined);
  if (!days.length) return null;
  const level = days.reduce((low, d) => L.rank(d.l) < L.rank(low) ? d.l : low, days[0].l), at = days.filter(d => d.l === level);
  const words = L.risk(s, at[0].x).by === 'record' ? 'at least high risk every day'
    : at.length === ahead.length && at.length > 1 ? `${level} risk every day from ${dayName(ahead[0])} to ${dayName(ahead.at(-1))}`
    : `${andList(at.map(d => dayName(d.x)))}, ${level} risk`;
  return { date: at[0].x.date, level, words };
}
// The forecast's five days (`dates`), and at each spot whose level changes from day to day each
// day's level, headline and what to do, as a picked day shows them, for alerts about a date
// (push/src/dates.js): "tell me when 14 June enters the forecast, and again if its level changes".
// Compact, since the alert service reads this file every 2 minutes on a 10 ms budget: `days` follows
// `dates`, each day [level, headline, action] with the two sentences as places in `words`, or null
// for a day with no level (no rain forecast yet). Elsewhere the level is the spot's own on every
// day, and the alerts use the spot's headline and action.
const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const dates = [0, 1, 2, 3, 4].map(n => addDays(L.today(), n)), words = [], at = new Map();
const word = w => { if (!at.has(w)) { at.set(w, words.length); words.push(w); } return at.get(w); };
const daysOf = s => dates.map(iso => { const l = L.dayLevel(s, iso);
  return L.ORDER[l] === undefined ? null : [l, word(L.dayHeadline(s, iso)), word(L.dayAction(s, iso))]; });
const spots = {};
for (const s of data.spots) {
  const level = L.level(s), b = best(s);
  spots[s.id] = { name: s.name, rank: L.rank(level), level, headline: L.headline(s), action: L.levelAction(s),
    url: PAGE_ID.test(s.id) ? `${root}spot/${s.id}/` : `${root}?spot=${encodeURIComponent(s.id)}`, ...(b ? { best: b } : {}),
    ...(L.daily(s) ? { days: daysOf(s) } : {}) };
}
// The data credits travel with every published data file (build_site.data_credits).
fs.writeFileSync(out, JSON.stringify({ generated_at: data.generated_at, ...(data.credits ? { credits: data.credits } : {}), dates, words, spots }));
