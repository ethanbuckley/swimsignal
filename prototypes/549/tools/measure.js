(() => {
  const vis = e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const main = document.querySelector('main, #panel') || document.body;
  const words = t => (t.match(/\S+/g) || []).length;
  const H = innerHeight;
  const leaf = [...main.querySelectorAll('p, li, h1, h2, h3, summary, dt, dd, td, th, .sub, .small')].filter(vis);
  const above = leaf.filter(e => e.getBoundingClientRect().top < H - 70);
  const muted = leaf.filter(e => { const c = getComputedStyle(e).color; const m = c.match(/\d+/g).map(Number); return m[0] > 70 && Math.abs(m[0]-m[1]) < 25; });
  const details = [...main.querySelectorAll('details')].filter(vis);
  return { pageH: document.documentElement.scrollHeight, screens: +(document.documentElement.scrollHeight / H).toFixed(1),
    wordsTotal: words(main.innerText), wordsFirstScreen: above.reduce((n, e) => n + words(e.innerText), 0) ,
    paragraphs: main.querySelectorAll('p').length, mutedBlocks: muted.length, details: details.length,
    headings: [...main.querySelectorAll('h1,h2,h3')].filter(vis).map(h => h.innerText.trim().slice(0, 40)).slice(0, 30) };
})()
