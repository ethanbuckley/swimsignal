// The page's first draw over the build's own copy of a view's opening (data-built: the home page's
// .lead, build_site.home_lead, and a spot's answer, scripts/prerender_spots.js). The opening must stay
// the same element: replaced, its picture is painted a second time, later, and page-speed tests time
// the load by that second paint (LCP, 17 Oct 2026). index.html's setPanel calls overBuilt for it.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {reached} = require('../scripts/prerender_spots.js');

const PAGE = fs.readFileSync(path.join(__dirname, '../src/dipcast/site/index.html'), 'utf8');

// Just enough of a DOM for overBuilt and patchNode: elements, text, a fragment, and a parser for the
// plain markup below (double-quoted attributes, no void elements).
class Node {
  constructor(type, name, value = null) { Object.assign(this, {nodeType: type, nodeName: name, nodeValue: value, childNodes: [], parentNode: null, attrs: new Map()}); }
  get attributes() { return [...this.attrs].map(([name, value]) => ({name, value})); }
  getAttribute(n) { return this.attrs.has(n) ? this.attrs.get(n) : null; }
  setAttribute(n, v) { this.attrs.set(n, String(v)); }
  removeAttribute(n) { this.attrs.delete(n); }
  hasAttribute(n) { return this.attrs.has(n); }
  get id() { return this.getAttribute('id') || ''; }
  get className() { return this.getAttribute('class') || ''; }
  get classList() { return {contains: c => this.className.split(' ').includes(c)}; }
  get children() { return this.childNodes.filter(n => n.nodeType === 1); }
  get firstChild() { return this.childNodes[0] || null; }
  get nextSibling() { const p = this.parentNode; return p ? p.childNodes[p.childNodes.indexOf(this) + 1] || null : null; }
  remove() { const p = this.parentNode; if (p) { p.childNodes.splice(p.childNodes.indexOf(this), 1); this.parentNode = null; } }
  insert(at, nodes) { nodes = nodes.flatMap(n => n.nodeType === 11 ? [...n.childNodes] : [n]); nodes.forEach(n => n.remove());
    this.childNodes.splice(at === null ? this.childNodes.length : this.childNodes.indexOf(at), 0, ...nodes); nodes.forEach(n => { n.parentNode = this; }); }
  append(...ns) { this.insert(null, ns); }
  before(...ns) { this.parentNode.insert(this, ns); }
  after(...ns) { const p = this.parentNode, next = this.nextSibling; ns.forEach(n => n.remove()); p.insert(next && next.parentNode === p ? next : null, ns); }
  replaceWith(n) { this.before(n); this.remove(); }
  replaceChildren(...ns) { [...this.childNodes].forEach(c => c.remove()); this.append(...ns); }
  isEqualNode(o) { return html(this) === html(o); }
}
const html = n => n.nodeType === 3 ? n.nodeValue : n.nodeType === 11 ? n.childNodes.map(html).join('')
  : `<${n.nodeName.toLowerCase()}${n.attributes.map(a => ` ${a.name}="${a.value}"`).join('')}>${n.childNodes.map(html).join('')}</${n.nodeName.toLowerCase()}>`;
function parse(h, into = new Node(11, '#document-fragment')) {
  const stack = [into];
  for (const [, close, tag, attrs, text] of h.matchAll(/<(\/?)([a-z0-9]+)([^>]*)>|([^<]+)/g)) {
    if (text) { stack[0].append(new Node(3, '#text', text)); continue; }
    if (close) { stack.shift(); continue; }
    const el = new Node(1, tag.toUpperCase());
    for (const [, k, v] of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) el.setAttribute(k, v ?? '');
    stack[0].append(el); stack.unshift(el);
  }
  return into;
}
const document = {createElement: () => { const content = new Node(11, '#document-fragment'); return {content, set innerHTML(h) { parse(h, content); }}; }};
const ctx = vm.createContext({document});
vm.runInContext(reached(PAGE, ['overBuilt'], []), ctx);
const find = (n, test) => test(n) ? n : n.childNodes.map(c => find(c, test)).find(Boolean) || null;
const box = h => parse(h, new Node(1, 'DIV'));

const BUILT = '<div class="top-row"><a id="back">All spots</a></div><section class="answer" id="risk-hero"><h1 class="spot-name">A</h1>'
  + '<div id="answer-words"><h2 class="big low">Low risk</h2><p class="issued">Issued Tue 08:00</p></div></section>'
  + '<div class="stack"><section class="tile">Five days</section></div><noscript>No scripts</noscript>';
const DRAWN = '<div class="top-row"><a id="back">All spots</a><button class="save">Save</button></div><div data-notices=""></div>'
  + '<section class="answer" id="risk-hero"><h1 class="spot-name">A</h1><div id="answer-words"><h2 class="big low">Low risk</h2>'
  + '<p class="issued">Issued Tue 08:00, 5 min ago</p></div></section><div class="stack"><section class="tile">Five days</section><div id="nearby-host"></div></div>';

test("a spot's answer stays the element the build wrote, changed only where the script's words differ", () => {
  const b = box(BUILT), hero = find(b, n => n.id === 'risk-hero'), h1 = find(hero, n => n.nodeName === 'H1'), issued = find(hero, n => n.className === 'issued');
  ctx.overBuilt(b, DRAWN);
  assert.equal(html(b).replace(/^<div>|<\/div>$/g, ''), DRAWN);   // the view is the script's, all of it
  assert.equal(find(b, n => n.id === 'risk-hero'), hero);   // in the same element: its picture is not painted again
  assert.equal(find(b, n => n.nodeName === 'H1'), h1);
  assert.equal(find(b, n => n.className === 'issued'), issued);   // "Issued" keeps its line; only its words are new
  assert.equal(b.children.indexOf(hero), 2);   // after the top row and the notices, as the script draws them
  assert.equal(find(b, n => n.nodeName === 'NOSCRIPT'), null);
});

test("the home page's opening is updated where it stands, and what comes after a changed line is new", () => {
  const built = '<div class="lead"><section class="intro"><h1>Check the water</h1><p class="lede">For 3 spots, or <span class="w-touch">tap</span>'
    + '<span class="w-click">click</span> any river.</p></section><div class="toolbar"><select id="listday"><option value="">Today and tomorrow</option></select>'
    + '<button class="chip-btn low" aria-pressed="false">Low</button></div></div><p class="sr" aria-busy="true">Loading</p><div class="skel tile"></div>';
  const drawn = '<div class="lead"><section class="intro"><h1>Check the water</h1><p class="lede">For 3 spots, or tap any river.</p></section>'
    + '<div class="toolbar"><select id="listday"><option value="">Today and tomorrow</option><option value="2026-10-17">Today</option></select>'
    + '<button class="chip-btn low" aria-pressed="false" aria-describedby="low-note-list">Low</button></div><p class="planner-note best-day">Best</p>'
    + '<div data-notices=""></div></div><section class="group tile" id="all-group">All spots</section>';
  const b = box(built), lead = find(b, n => n.className === 'lead'), h1 = find(b, n => n.nodeName === 'H1'), select = find(b, n => n.id === 'listday');
  ctx.overBuilt(b, drawn);
  assert.equal(html(b).replace(/^<div>|<\/div>$/g, ''), drawn);
  assert.equal(find(b, n => n.className === 'lead'), lead);
  assert.equal(find(b, n => n.nodeName === 'H1'), h1);   // above the change: kept
  // Below the changed line ("tap or click" in a phone's words) the controls are new: kept, they
  // could have moved, and a moved element counts as a layout shift where a new one does not.
  assert.notEqual(find(b, n => n.id === 'listday'), select);
});

test("a line that grows in a spot's answer brings new lines under it, not moved ones", () => {
  const b = box(BUILT.replace('<h2 class="big low">Low risk</h2>', '<h2 class="big low">Low risk</h2><p class="why">For the next five days</p>')),
    hero = find(b, n => n.id === 'risk-hero'), issued = find(hero, n => n.className === 'issued');
  ctx.overBuilt(b, DRAWN.replace('<h2 class="big low">Low risk</h2>', '<h2 class="big low">Low risk</h2><p class="why">Forecast only: the overflows have not reported</p>'));
  assert.equal(find(b, n => n.id === 'risk-hero'), hero);
  assert.notEqual(find(b, n => n.className === 'issued'), issued);
});

test('another view over the built opening (an old ?spot= link on the home page) replaces it', () => {
  const b = box('<div class="lead"><h1>Check the water</h1></div><div class="skel tile"></div>');
  ctx.overBuilt(b, DRAWN);
  assert.equal(html(b).replace(/^<div>|<\/div>$/g, ''), DRAWN);
  assert.equal(find(b, n => n.className === 'lead'), null);
});
