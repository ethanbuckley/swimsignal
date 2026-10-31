// The top of each spot's page and its five days, written into spot/<id>/index.html at build so the
// answer shows before the forecast arrives. The words are the
// page's own: this runs index.html's spotTop and daysTile, with levels.js and the other page scripts
// they use, in Node, on this build's spots.json, as at the moment the forecast was issued. The page's
// script then draws the same markup in the same place, so nothing moves.
//
//   node scripts/prerender_spots.js site/data/spots.json out.json https://example.org/swim/
//
// out.json is {id: html}; - writes it to stdout. Only top-level definitions of index.html's inline script that the two
// functions reach are run (pageDefs): the rest of the script needs a browser.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SITE = path.join(__dirname, '..', 'src', 'dipcast', 'site');
// The page's scripts the two functions use, run whole, in the page's order. lists.js gives Save its
// label; eatoday.js decides whether the answer points at "Today's EA advice".
const SCRIPTS = ['eatoday.js', 'experience.js', 'levels.js', 'lists.js'];
const ROOTS = ['spotTop', 'daysTile', 'ageReadings'];
// Definitions that need a browser as they run, which the prerender gives itself instead (context):
// where the site is, and the map (an object key "map" reaches it; nothing here draws one).
const GIVEN = ['ROOT', 'map', 'TOUCH', 'STILL'];

// Code without its comments, strings and regular expressions, so a word in a sentence ("Open map")
// does not count as a use of the name (map). A template literal's ${...} parts stay: they are code.
function codeOnly(s) {
  let out = '', i = 0, prev = '';
  const stack = [];   // brace depths at which a template's ${ was opened
  let depth = 0;
  const regexCanStart = () => /^$|[(,=:[!&|?{};+\-*%<>~^]$/.test(prev) || /\b(return|typeof|case|in|of)$/.test(out.trimEnd());
  while (i < s.length) {
    const c = s[i], n = s[i + 1];
    if (c === '/' && n === '/') { while (i < s.length && s[i] !== '\n') i++; continue; }
    if (c === '/' && n === '*') { i = s.indexOf('*/', i + 2); i = i < 0 ? s.length : i + 2; continue; }
    if (c === '"' || c === "'") { i++; while (i < s.length && s[i] !== c) i += s[i] === '\\' ? 2 : 1; i++; out += ' "" '; prev = '"'; continue; }
    if (c === '`' || (c === '}' && stack.length && stack[stack.length - 1] === depth)) {
      if (c === '}') { stack.pop(); depth--; }
      i++;
      while (i < s.length && s[i] !== '`' && !(s[i] === '$' && s[i + 1] === '{')) i += s[i] === '\\' ? 2 : 1;
      if (s[i] === '$') { i += 2; depth++; stack.push(depth); out += ' ( '; prev = '('; } else { i++; out += ' "" '; prev = '"'; }
      continue;
    }
    if (c === '/' && regexCanStart()) {
      i++; let cls = false;
      while (i < s.length && (s[i] !== '/' || cls)) { if (s[i] === '\\') i++; else if (s[i] === '[') cls = true; else if (s[i] === ']') cls = false; i++; }
      i++; while (/[a-z]/.test(s[i] || '')) i++;
      out += ' /x/ '; prev = '/'; continue;
    }
    if (c === '{') depth++;
    if (c === '}') depth--;
    out += c; if (!/\s/.test(c)) prev = c; i++;
  }
  return out;
}

// The inline script's top-level definitions: each name, with the statement that defines it. A
// statement runs from a line that starts with const, let, function or async function at the left
// margin to the next such line (or blank line), as tests/site_tile_lines.test.cjs reads them.
function pageDefs(html) {
  const start = html.lastIndexOf('<script>\nconst BRAND'), end = html.indexOf('</script>', start);
  if (start < 0 || end < 0) throw new Error("index.html's inline script not found");
  const lines = html.slice(start + '<script>\n'.length, end).split('\n'), defs = new Map(), order = [];
  const DECL = /^(?:const|let|var|function|async function)\s+([A-Za-z_$][\w$]*)/;
  lines.forEach((l, i) => {
    const m = l.match(DECL); if (!m) return;
    let j = i + 1; while (j < lines.length && lines[j].trim() !== '' && !DECL.test(lines[j]) && /^[\s})\]+:?.]/.test(lines[j])) j++;
    const text = lines.slice(i, j).join('\n'), code = codeOnly(text);
    // const a = 1, b = 2: every name declared at the statement's own level, not inside its braces.
    const names = [m[1]];
    if (!/^(?:async )?function/.test(l)) {
      let d = 0;
      for (let k = 0; k < code.length; k++) {
        const ch = code[k];
        if ('([{'.includes(ch)) d++; else if (')]}'.includes(ch)) d--;
        else if (ch === ',' && d === 0) { const mm = code.slice(k + 1).match(/^\s*([A-Za-z_$][\w$]*)\s*=(?![=>])/); if (mm) names.push(mm[1]); }
        else if (ch === ';' && d === 0) break;
      }
    }
    const def = { at: i, text, uses: new Set(code.match(/(?<![.\w$])[A-Za-z_$][\w$]*/g) || []) };
    order.push(def);
    for (const name of names) defs.set(name, def);
  });
  return { defs, order };
}

// The definitions the roots reach, in the script's order (a const must come after what it calls at once).
function reached(html, roots = ROOTS, given = GIVEN) {
  const { defs } = pageDefs(html), want = new Set(), todo = [...roots];
  while (todo.length) {
    const name = todo.pop(), d = defs.get(name);
    if (!d || want.has(d) || given.includes(name)) continue;
    want.add(d);
    for (const u of d.uses) if (defs.has(u) && !want.has(defs.get(u))) todo.push(u);
  }
  return [...want].sort((a, b) => a.at - b.at).map(d => d.text).join('\n');
}

// A context with what the page's code expects of a browser that has stored nothing: the forecast
// (DATA), the clock stopped at the time it was issued, no saved spots, no history state, online.
function context(data, root) {
  const issuedAt = Date.parse(data.generated_at);
  const store = { getItem: () => null, setItem() {}, removeItem() {} };
  // ROOT is where the site is (index.html: from the <base>), its path the back link's address.
  const ctx = vm.createContext({ console, URL, URLSearchParams, Intl, history: { state: null }, location: new URL(root),
    navigator: { onLine: true }, localStorage: store, sessionStorage: store, addEventListener() {}, setTimeout, clearTimeout,
    ROOT: new URL(root), map: null, TOUCH: false, STILL: false });
  ctx.window = ctx;
  vm.runInContext(`Date.now = () => ${issuedAt};`, ctx);
  for (const f of SCRIPTS) vm.runInContext(fs.readFileSync(path.join(SITE, f), 'utf8'), ctx, { filename: f });
  vm.runInContext(reached(fs.readFileSync(path.join(SITE, 'index.html'), 'utf8')), ctx, { filename: 'index.html' });
  vm.runInContext(`setToday(${JSON.stringify(data.generated_at.slice(0, 10))});`, ctx);
  ctx.DATA_IN = data;
  vm.runInContext('DATA = DATA_IN;', ctx);
  return ctx;
}

// Each spot's top and, where it has days, its five days, as render() puts them: the five days are
// the first tile in the stack. "Issued ..., N min ago" loses its age, which would be wrong by the
// time the page is read; the script puts it back when it draws.
function prerender(data, root) {
  const ctx = context(data, root), out = {};
  for (const s of data.spots) {
    ctx.S = s;
    const h = vm.runInContext('ageReadings(S, Date.now()); spotTop(S) + (S.error ? "" : `<div class="stack">${daysTile(S)}</div>`)', ctx);
    out[s.id] = h.replace(/(<p class="issued">Issued [^<,]+), (<span data-ago="\d+">)?[^<]*(<\/span>)? ago<\/p>/, '$1</p>');
  }
  return out;
}

if (require.main === module) {
  const [src, dst, root] = process.argv.slice(2);
  if (!src || !dst || !root || !root.endsWith('/')) {
    console.error('usage: node scripts/prerender_spots.js <spots.json> <out.json, or - for stdout> <site root ending in />');
    process.exit(2);
  }
  const json = JSON.stringify(prerender(JSON.parse(fs.readFileSync(src, 'utf8')), root));
  if (dst === '-') process.stdout.write(json); else fs.writeFileSync(dst, json);
}

module.exports = { codeOnly, pageDefs, reached, prerender };
