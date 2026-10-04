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
const spots = {};
for (const s of data.spots) {
  const level = L.level(s), b = best(s);
  spots[s.id] = { name: s.name, rank: L.rank(level), level, headline: L.headline(s), action: L.levelAction(s),
    url: PAGE_ID.test(s.id) ? `${root}spot/${s.id}/` : `${root}?spot=${encodeURIComponent(s.id)}`, ...(b ? { best: b } : {}) };
}
// The data credits travel with every published data file (build_site.data_credits).
fs.writeFileSync(out, JSON.stringify({ generated_at: data.generated_at, ...(data.credits ? { credits: data.credits } : {}), spots }));
