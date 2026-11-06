// Copies every hour record (KV keys h/...) from the deployed SHADOW namespace to a local folder, for the
// offline scorer. Reads only; deletes nothing. Run from river-shadow/, signed in to Cloudflare:
//
//   node scripts/export.mjs <out dir>
//
// One file a record, <out dir>/<issue with ':' as '-'>.json, plus keys.json (the listing). A record already
// in the folder is not asked for again, so a stopped export is resumed by running it again. Each key is
// one `wrangler kv key get`, a second or two each: about 2,200 records by 28 Feb 2027.

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const out = process.argv[2];
if (!out) {
  console.error('usage: node scripts/export.mjs <out dir>');
  process.exit(2);
}
mkdirSync(out, { recursive: true });
const wrangler = (...args) => execFileSync('npx', ['wrangler', 'kv', 'key', ...args, '--binding', 'SHADOW', '--remote'],
  { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'inherit'] });

const listing = JSON.parse(wrangler('list', '--prefix', 'h/'));
writeFileSync(join(out, 'keys.json'), JSON.stringify(listing, null, 1) + '\n');
const names = listing.map((k) => k.name).filter((n) => /^h\/\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$/.test(n)).sort();
let got = 0, kept = 0;
for (const name of names) {
  const file = join(out, `${name.slice(2).replaceAll(':', '-')}.json`);
  if (existsSync(file)) { kept++; continue; }
  const text = wrangler('get', name);
  JSON.parse(text);   // a record that is not JSON stops the export here, before it is saved
  writeFileSync(file, text.endsWith('\n') ? text : text + '\n');
  got++;
}
console.log(`${names.length} records listed; ${got} fetched, ${kept} already in ${out}`);
// The stop marker and failure count, for the uptime check (not records).
for (const key of ['state/stopped', 'state/failures']) {
  try {
    const text = wrangler('get', key);
    JSON.parse(text);   // an absent key answers with a message, not JSON
    writeFileSync(join(out, `${key.replace('/', '-')}.json`), text);
  } catch { /* absent */ }
}
