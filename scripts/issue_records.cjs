// The records the issued-forecast history keeps (src/dipcast/issue_history.py, docs/ISSUED-HISTORY-2026-10.md):
// for each spot in a build's spots-lite.json, what its page shows and the inputs behind it, made by the page's own
// rules (since.js, seenRecord) on the issue's own day, so the record and the page cannot drift apart. Reads the
// file named on the command line and writes one JSON object to stdout: { issued_at, records: { id: record } }.
// A spot whose forecast failed in this issue has no record (seenRecord gives null).
const fs = require('node:fs');
const path = require('node:path');
const L = require(path.join(__dirname, '..', 'src', 'dipcast', 'site', 'levels.js'));
const S = require(path.join(__dirname, '..', 'src', 'dipcast', 'site', 'since.js'));

const doc = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const at = Date.parse(doc.generated_at);
if (!Number.isFinite(at)) throw new Error('spots-lite.json has no readable generated_at');
L.setToday(new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date(at)));   // the issue's UK day
const records = {};
for (const s of doc.spots || []) {
  const r = S.seenRecord(s, doc.generated_at, at);
  if (!r) continue;
  const { id, at: _, ...rest } = r;   // the id is the key; the moment a reader looked means nothing here
  records[id] = rest;
}
process.stdout.write(JSON.stringify({ issued_at: doc.generated_at, records }));
