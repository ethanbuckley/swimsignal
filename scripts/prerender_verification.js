// The Accuracy page's figures, tables and lists, written into verification.html at build from this
// build's data/verification.json. Drawn only by the page's
// script, they came in above the page's last paragraph after the file arrived, and the page moved by
// thousands of pixels (CLS 0.45). This runs the page's own script in Node, with a document that only
// keeps what the script writes, so the words and figures are the page's.
//
//   node scripts/prerender_verification.js site/verification.html site/data/verification.json
//
// The page may come on stdin, as -.
// Prints {built, top, answer, short, live, offline}: built is when the live scores were made (live.generated_at,
// or null), the rest the HTML of the page's five boxes. The page draws them again only from newer scores.
const fs = require('fs');
const vm = require('vm');

const BOXES = ['top', 'answer', 'short', 'live', 'offline'];
// The text of a heading, as textContent gives it (the contents list puts it back into HTML as it is).
const text = h => h.replace(/<[^>]*>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

async function prerender(page, data) {
  const start = page.lastIndexOf('<script>'), end = page.lastIndexOf('</script>');
  let code = page.slice(start + '<script>'.length, end);
  // The script starts itself on its last line, and puts any failure on the page: here main() is called
  // below, so a failure stops the build's copy instead.
  const call = /^main\(\)\.catch\(.*$/m;
  if (!call.test(code)) throw new Error("verification.html's script no longer ends with main().catch(...)");
  code = code.replace(call, '');
  const el = Object.fromEntries(BOXES.map(id => [id, { id, innerHTML: '' }]));
  const document = {
    getElementById: id => el[id] || null,
    querySelector: s => { if (s === 'main') return { dataset: {} }; throw new Error(`querySelector(${s}) not stubbed`); },
    // contents(): the level-2 sections the data produced, in #live then #offline, as section() writes them.
    querySelectorAll: s => {
      if (s !== '#live section[id] > h2, #offline section[id] > h2') throw new Error(`querySelectorAll(${s}) not stubbed`);
      return ['live', 'offline'].flatMap(id => [...el[id].innerHTML.matchAll(/<section id="([^"]+)"><h2>([\s\S]*?)<\/h2>/g)]
        .map(m => ({ parentElement: { id: m[1] }, textContent: text(m[2]) })));
    },
  };
  const ctx = vm.createContext({ console, document, location: { hash: '' }, URL, Intl,
    fetch: async () => ({ ok: true, json: async () => data }) });
  vm.runInContext(code, ctx, { filename: 'verification.html' });
  await vm.runInContext('main()', ctx);
  return { built: (data.live || {}).generated_at || null, ...Object.fromEntries(BOXES.map(id => [id, el[id].innerHTML])) };
}

if (require.main === module) {
  const [page, json] = process.argv.slice(2);
  if (!page || !json) {
    console.error('usage: node scripts/prerender_verification.js <verification.html, or - for stdin> <verification.json>');
    process.exit(2);
  }
  prerender(fs.readFileSync(page === '-' ? 0 : page, 'utf8'), JSON.parse(fs.readFileSync(json, 'utf8')))
    .then(out => process.stdout.write(JSON.stringify(out)), e => { console.error(e.stack || e); process.exit(1); });
}

module.exports = { prerender };
