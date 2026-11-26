/* Research Lab exhibit 6, the overflow ledger (docs/OVERFLOW-LEDGER-CONTRACT-v1.md). Every figure is read from the research
   file when the page loads, or added up from it here; nothing is typed in. An account of the model, not of measured bacteria.
   Ethan, 19 Nov 2026: overflows are not named nationally in public and the by-company table is not shown. So the national
   view is by spot, and overflows are named only in one catchment's grid, as each spot's page and exhibit 2 name them. */
(() => {
  'use strict';
  const FILE = '../../../data/research/overflow_ledger.v1.json';
  const SHOW = 20;
  const $ = id => document.getElementById(id);
  const esc = LAB.esc;
  const num = (v, dp) => v == null ? '<span class="na">not given</span>' : Number(v).toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  const pct = v => Math.round(100 * v) + '%';
  const title = s => s == null ? 'Name not given' : String(s).replace(/\//g, ' ').replace(/\s+/g, ' ').trim();
  const plural = (n, one, many) => `${n.toLocaleString('en-GB')} ${n === 1 ? one : many}`;

  let doc, rows, spots;
  const state = { sort: 'weight_sum', all: false };
  const SORTS = [['weight_sum', 'Summed weight'], ['n', 'Overflows traced'], ['top_share', "Largest one's share"]];

  // The file's overflows are columns; a row each is easier to read.
  function build(d) {
    const o = d.overflows, out = [];
    for (let i = 0; i < o.site_id.length; i++) {
      const r = { i };
      for (const k of Object.keys(o)) r[k] = o[k][i];
      out.push(r);
    }
    return out;
  }

  // Each traced spot's own weights, from the links: how many, their sum, the largest, its share, and how few carry half.
  function bySpot() {
    const per = doc.spots.map(() => []);
    for (const r of rows) for (const ln of r.links) per[ln[0]].push(ln[1]);
    return doc.spots.map((s, i) => {
      const w = per[i].slice().sort((a, b) => b - a);
      if (!w.length) return { ...s, i, n: 0 };
      const sum = w.reduce((a, b) => a + b, 0);
      let k = 0, c = 0;
      while (c < sum / 2) c += w[k++];
      return { ...s, i, n: w.length, weight_sum: s.weight_sum, weight_max: w[0], top_share: w[0] / sum, half: k };
    });
  }

  const traced = () => spots.filter(s => s.n);
  const median = a => { const b = a.slice().sort((x, y) => x - y), m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; };

  function front() {
    const c = doc.coverage, t = traced(), one = t.filter(s => s.top_share >= 0.5).length, half = median(t.map(s => s.half));
    LAB.answer($('front-answer'),
      `The model traces ${num(c.overflows, 0)} monitored overflows to ${c.spots_with_overflows} of the ${c.spots} listed spots. ` +
      `At ${one} of those spots one overflow carries half or more of the spot's summed weight; at the middle spot, ${plural(half, 'overflow carries', 'overflows carry')} half. ` +
      `${c.spots_no_overflow} spots have no monitored overflow within ${doc.source_export.settings.max_upstream_km} km upstream, which does not make them clean.`,
      `${num(c.links, 0)} links from an overflow to a spot. ${num(c.overflows_reaching_one_spot, 0)} overflows reach one listed spot only; ` +
      `${c.groups} groups of spots share at least one overflow. ${c.spots_off_network} spots sit off the mapped rivers. ` +
      `${c.overflows_without_average} overflows have no long-term average spill count in the annual return. ` +
      `The settings are the forecast's own: river speed ${doc.source_export.settings.river_velocity_ms} m/s, T90 ${doc.source_export.settings.t90_h} hours, dilution "${esc(doc.source_export.settings.dilution_mode)}".`);
    $('evidence-text').textContent = `${doc.claim.evidence.text} (Tested on unseen river samples, read ${LAB.day(doc.claim.evidence.read)}. The ledger itself was not tested.)`;
    $('not').innerHTML = doc.claim.not_claimed.map(t => `<li>It does not say ${esc(t)}.</li>`).join('')
      + `<li>It does not say how the weights were on another day. They are the forecast's network trace of ${LAB.day(doc.source_export.made)}; the forecast remakes its own at every build, and an overflow added or closed since is not in this table.</li>`;
    $('attrib').textContent = doc.attribution.join('. ') + '.';
  }

  function overview() {
    const el = $('overview');
    LAB.loadOutline('../').then(() => {
      LAB.drawMap(el, rows.filter(r => r.lat != null).map(r => ({ id: r.site_id, lat: r.lat, lon: r.lon, name: '', mark: '<circle r="1.6" class="lg-dot"/>' })), { inert: true });
      $('overview-cap').textContent = `Every monitored overflow the model traces to a listed spot, ${num(rows.length, 0)} dots. Unnamed here: section 4 and exhibit 2 name them place by place. Map: ${LAB.credit()}.`;
    }).catch(() => { el.hidden = true; });
  }

  function spotTable() {
    const t = traced(), k = state.sort;
    t.sort((a, b) => b[k] - a[k] || b.weight_sum - a.weight_sum);
    const shown = state.all ? t : t.slice(0, SHOW), max = Math.max(...t.map(s => s.weight_sum), 0.0001);
    $('spots-aside').textContent = `${shown.length} of ${t.length} spots with an overflow traced`;
    $('spots').innerHTML = '<table><caption>Model weights, not measurements. A weight is survival × dilution, from 0 to 1.</caption><thead><tr>'
      + '<th>Spot</th><th class="n">Overflows traced</th><th class="n">Summed weight</th><th class="n">Largest weight</th>'
      + "<th class=\"n\">Largest one's share</th><th class=\"n\">Overflows carrying half</th></tr></thead><tbody>"
      + shown.map(s => `<tr><td><a href="../pollution/#spot=${encodeURIComponent(s.id)}">${esc(s.name)}</a><small>${s.kind === 'lake' ? 'Lake' : 'River'} · ${esc(s.area)}</small></td>`
        + `<td class="n">${s.n}</td><td class="n">${num(s.weight_sum, 2)}<span class="bar" style="width:${(100 * s.weight_sum / max).toFixed(1)}%"></span></td>`
        + `<td class="n">${num(s.weight_max, 2)}</td><td class="n">${pct(s.top_share)}</td><td class="n">${s.half}</td></tr>`).join('')
      + '</tbody></table>';
    const more = $('more');
    more.hidden = t.length <= SHOW;
    more.textContent = state.all ? `Show the first ${SHOW}` : `Show all ${t.length}`;
  }

  function untraced() {
    const none = spots.filter(s => s.status === 'no_overflow'), off = spots.filter(s => s.status === 'off_network');
    const list = a => a.map(s => esc(s.name)).join('; ');
    $('untraced').innerHTML = `<b>Not in the table.</b> ${none.length} spots with no monitored overflow within ${doc.source_export.settings.max_upstream_km} km upstream: ${list(none)}. `
      + (off.length ? `${off.length} off the mapped rivers, so not traced: ${list(off)}. ` : '')
      + 'None of them is called clean: the model holds no treated sewage, farm or road runoff, and an overflow it does not trace may still reach them.';
  }

  function shared() {
    const by = {};
    for (const r of rows) by[r.spots_reached] = (by[r.spots_reached] || 0) + 1;
    const keys = Object.keys(by).map(Number).sort((a, b) => a - b), max = Math.max(...Object.values(by));
    $('reach').innerHTML = '<table><caption>Overflows by how many listed spots the model traces them to.</caption><thead><tr><th>Spots reached</th><th class="n">Overflows</th><th class="bar-col"><span class="vh">Share of the largest count</span></th></tr></thead><tbody>'
      + keys.map(k => `<tr><td>${k}</td><td class="n">${num(by[k], 0)}</td><td class="bar-col"><span class="bar" style="width:${(100 * by[k] / max).toFixed(1)}%"></span></td></tr>`).join('')
      + '</tbody></table>';
    const g = doc.groups.slice().sort((a, b) => b.spots.length - a.spots.length || b.overflows - a.overflows)[0];
    $('shared-note').textContent = `An overflow upstream of several spots counts at each of them, so the summed weights of two spots overlap. `
      + `${doc.groups.length} groups of spots share at least one overflow; the largest, ${g.name} and the spots joined to it, holds ${g.spots.length} spots and ${g.overflows} overflows. `
      + 'A group is a catchment as the model sees it, not a mapped catchment boundary.';
  }

  function grid() {
    const g = doc.groups[Number($('group').value)];
    const mine = rows.filter(r => r.group === g.id).sort((a, b) => b.weight_sum - a.weight_sum);
    $('group-note').textContent = `${plural(g.spots.length, 'spot', 'spots')}, ${plural(g.overflows, 'overflow', 'overflows')}, ${plural(g.links, 'link', 'links')}. `
      + 'Each cell is the model\'s weight for that overflow at that spot. A hatched cell means the model does not trace the overflow to the spot.';
    $('grid').innerHTML = '<table><caption>Model weights (survival × dilution, 0 to 1), not measurements.</caption><thead><tr><th>Overflow</th>'
      + g.spots.map(s => `<th class="n">${esc(doc.spots[s].name)}</th>`).join('') + '<th class="n">Summed</th></tr></thead><tbody>'
      + mine.map(r => {
        const by = {};
        for (const ln of r.links) by[ln[0]] = ln[1];
        return `<tr><td>${esc(title(r.name))}<small>${esc(r.water || 'Watercourse not given')} · ${esc(r.site_id)}</small></td>`
          + g.spots.map(s => by[s] == null ? '<td class="none"><span class="vh">not traced</span></td>' : `<td class="w" style="--w:${by[s]}">${num(by[s], 2)}</td>`).join('')
          + `<td class="n">${num(r.weight_sum, 2)}</td></tr>`;
      }).join('') + '</tbody></table>';
    $('grid-key').innerHTML = '<span><i class="sw w1"></i>darker: a larger weight</span><span><i class="sw gap"></i>not traced to this spot</span>';
    const first = doc.spots[g.spots[0]];
    $('group-live').innerHTML = g.spots.map(s => `<a href="${LAB.spotURL(doc.spots[s].id)}">Today's forecast for ${esc(doc.spots[s].name)}</a>`).join(' · ');
    try { history.replaceState(null, '', '#spot=' + encodeURIComponent(first.id)); } catch (e) { /* a file: page */ }
  }

  function controls() {
    $('sort').innerHTML = SORTS.map(s => `<button type="button" data-k="${s[0]}" aria-pressed="${s[0] === state.sort}">${s[1]}</button>`).join('');
    $('sort').onclick = e => {
      const b = e.target.closest('button');
      if (!b) return;
      state.sort = b.dataset.k;
      for (const x of $('sort').children) x.setAttribute('aria-pressed', String(x === b));
      spotTable();
    };
    $('more').onclick = () => { state.all = !state.all; spotTable(); };
    $('group').innerHTML = doc.groups.map(g => `<option value="${g.id}">${esc(g.name)}${g.spots.length > 1 ? ` and ${g.spots.length - 1} more` : ''} (${plural(g.overflows, 'overflow', 'overflows')})</option>`).join('');
    // The Wharfe above Ilkley unless the address names a spot (#spot=<id>, or #g=<id> from the prototype). A spot the
    // ledger lacks, or one with no overflow traced, is said in a status line: never another place swapped in quietly.
    const h = new URLSearchParams(location.hash.slice(1)), want = h.get('spot') || h.get('g');
    const si = want ? doc.spots.findIndex(s => s.id === want) : -1;
    const hit = si >= 0 && doc.groups.find(g => g.spots.includes(si));
    const home = doc.groups.find(g => g.spots.includes(doc.spots.findIndex(s => s.id === 'bw-uke4100-08901'))) || doc.groups[0];
    $('group').value = String((hit || home).id);
    if (want && !hit) {
      $('group-status').textContent = si < 0
        ? `That spot is not in this ledger, made ${LAB.day(doc.source_export.made)}. Showing the Wharfe above Ilkley instead.`
        : `The model traces no monitored overflow to ${doc.spots[si].name}. Showing the Wharfe above Ilkley instead.`;
    }
    $('group').onchange = () => { $('group-status').textContent = ''; grid(); };
  }

  fetch(FILE).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then(d => {
    if (d.schema !== 'swimsignal.overflow-ledger' || String(d.version).split('.')[0] !== '1') throw new Error('an unknown file version');
    doc = d; rows = build(d); spots = bySpot();
    front(); overview(); controls(); spotTable(); untraced(); shared(); grid();
  }).catch(err => LAB.failed($('front-answer'), err));
})();
