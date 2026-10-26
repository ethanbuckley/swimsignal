// Catchment replay (prototype, docs/CATCHMENT-REPLAY-2026-10.md): the last 48 hours upstream of a spot,
// from data/spot/<id>-replay.json (src/dipcast/replay.py). Shown only with ?replay=1 in the address
// (index.html, mountReplay), so the page is unchanged without it.
//
// Three kinds of thing, told apart in words and in the drawing's marks, never by colour alone:
//   reported   what a company's live feed said: a spill (solid bar), a monitor with no reading (a grey
//              bar). Observed, as the feed gave it.
//   modelled   when the spill's water was estimated to reach the spot: the spill moved on by the
//              overflow's travel time (outlined bar, "modelled"). An estimate, said so every time.
//   not held   a spill end the feed never gave, an hour of rain missing: nothing drawn, and the table
//              says it is not known. No line is drawn across a gap.
// Nothing here says a spill caused anything at the spot: "reported upstream", "modelled to reach".
//
// A plain script, like guide.js: in the page its names are globals (each begins replay or REPLAY), and
// in Node the last lines export them (tests/site_replay.test.cjs). The table is the full text; the
// drawing repeats it for the eye, with the table as its description.

const REPLAY_TZ = 'Europe/London';
const replayEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const replayMs = iso => (iso ? Date.parse(iso) : NaN);
// "Sat 14:26" in UK time; with the date where the day alone could be another week's.
function replayTime(iso) {
  const p = new Intl.DateTimeFormat('en-GB', { timeZone: REPLAY_TZ, weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    .formatToParts(new Date(iso));
  const v = t => p.find(x => x.type === t).value;
  return `${v('weekday')} ${v('hour')}:${v('minute')}`;
}
const replayName = o => (typeof overflowNames === 'function' ? overflowNames({ site_id: o.site_id, site_name: o.name }).plain : (o.name || o.site_id || ''));
const replayCompany = c => (typeof companyName === 'function' ? companyName(c) : String(c ?? ''));
const REPLAY_STATE = {
  live: 'live reading',
  stale: 'reading may be out of date: its feed has not updated within 6 hours',
  offline: 'no current reading: the monitor or its feed is not reporting',
  no_feed: 'no live feed from its company',
};

// One spill in words: what was reported, then the modelled arrival, labelled as an estimate.
function replaySpillSaid(s) {
  let said;
  if (s.running) said = `Reported spilling since ${replayTime(s.start)}, still discharging at the last reading.`;
  else if (!s.end_known) said = `Reported spilling from ${replayTime(s.start)}. Its end was not reported.`;
  else said = s.start === s.end ? `Reported spilling at ${replayTime(s.start)}, for under a minute.`
    : `Reported spilling ${replayTime(s.start)} to ${replayTime(s.end)}.`;
  const a = s.arrival;
  if (!a) return `${said} No travel time to the spot is modelled.`;
  const when = a.to && a.to !== a.from ? `around ${replayTime(a.from)} to ${replayTime(a.to)}` : `from around ${replayTime(a.from)}`;
  const tail = a.state === 'due' ? (a.to ? 'not there yet' : 'not there yet, and when it would pass is not known')
    : a.state === 'at_spot' ? (s.running ? 'still arriving' : 'arriving now')
      : a.state === 'passed' ? 'passed'
        : 'when it passed is not known';
  return `${said} Modelled to reach the spot ${when} (estimate; ${tail}).`;
}
function replayOfflineSaid(o) {
  const what = o.feed_down ? 'Company feed not answering' : 'No reading (monitor offline)';
  return o.to ? `${what} ${replayTime(o.from)} to ${replayTime(o.to)}.` : `${what} from ${replayTime(o.from)}; when it came back is not recorded.`;
}

// The rain line: the total over the hours held, the hours not held, and what the numbers are.
function replayRainSaid(rain) {
  if (!rain || rain.unavailable) return `Rain: not available here (${replayEsc((rain && rain.unavailable) || 'not held')}).`;
  const fc = replayMs(rain.forecast_from), start = replayMs(rain.start);
  let past = 0, ahead = 0, missing = 0;
  rain.mm.forEach((v, i) => { if (v === null) missing++; else if (start + i * 36e5 >= fc) ahead += v; else past += v; });
  const cells = `${rain.cells} rain-model cell${rain.cells === 1 ? '' : 's'} holding the overflows upstream`;
  return `Rain over the ${cells}: ${past.toFixed(1)} mm in the hours shown (Open-Meteo's model record, not rain gauges)`
    + (ahead > 0 ? `, and ${ahead.toFixed(1)} mm forecast for the hours after it was issued` : '')
    + (missing ? `. ${missing} hour${missing === 1 ? '' : 's'} not held, left blank.` : '.');
}
function replayGaugeSaid(g) {
  if (!g || g.unavailable) return `River level: ${replayEsc((g && g.unavailable) || 'not held')}.`;
  const at = g.station ? ` at ${replayEsc(g.station)}` : '';
  if (g.level_m == null) return `River level${at}: no current reading${g.last_level_m != null ? ` (last ${g.last_level_m.toFixed(2)} m, ${replayTime(g.observed_at)})` : ''}. Earlier readings are not held.`;
  const rise = g.rise_6h_m != null ? `, ${g.rise_6h_m >= 0 ? 'up' : 'down'} ${Math.abs(g.rise_6h_m).toFixed(2)} m since ${replayTime(g.rise_from)}` : '';
  return `River level${at}: ${g.level_m.toFixed(2)} m at ${replayTime(g.observed_at)}${rise}. Earlier readings are not held, so no line is drawn for it.`;
}
function replayQuietSaid(r) {
  const q = r.quiet || {}, out = [];
  if (q.live) out.push(`${q.live.n} other counted overflow${q.live.n === 1 ? '' : 's'} with a live reading reported no spill in these hours.`);
  const dark = ['stale', 'offline', 'no_feed'].reduce((n, k) => n + ((q[k] || {}).n || 0), 0);
  if (dark) out.push(`${dark} counted overflow${dark === 1 ? ' has' : 's have'} no current reading, so a spill there would not show here.`);
  if (r.more_with_events) out.push(`${r.more_with_events} more with reported spills, smaller reach, are not listed.`);
  return out.join(' ');
}

const replayAway = h => (h == null || !Number.isFinite(h) ? 'no travel time modelled'
  : h < 1 ? 'under an hour away (modelled)' : `about ${Math.round(h)} h away (modelled)`);
// The table: every fact the drawing shows, as text. One row an overflow, nearest reach first.
function replayTable(r) {
  const rows = (r.overflows || []).map(o => {
    const said = [...(o.spills || []).map(replaySpillSaid), ...(o.offline || []).map(replayOfflineSaid)];
    if (o.earlier_spills) said.unshift(`${o.earlier_spills} earlier spill${o.earlier_spills === 1 ? '' : 's'} in these hours not listed.`);
    return `<tr><th scope="row">${replayEsc(replayName(o))}<span class="rp-meta">${replayEsc(replayCompany(o.company))} · ${o.km} km upstream · `
      + `${replayAway(o.travel_h)} · ${REPLAY_STATE[o.state] || replayEsc(o.state)}</span></th>`
      + `<td>${said.map(t => `<p>${t}</p>`).join('')}</td></tr>`;
  }).join('');
  return `<table class="rp-table"><caption>Reported spills upstream and their modelled arrival here, ${replayTime(r.window.from)} to ${replayTime(r.window.to)}</caption>`
    + `<thead><tr><th scope="col">Overflow</th><th scope="col">What was reported, and when its water was modelled to arrive</th></tr></thead>`
    + `<tbody>${rows || '<tr><td colspan="2">No counted overflow upstream reported a spill or a gap in these hours.</td></tr>'}</tbody></table>`;
}

// The drawing. Width 340 user units, scaled to the tile; a block an overflow: its name, then two lanes on
// one time axis, reported above, modelled below. Hours ahead of now are drawn only for water still due.
const REPLAY_W = 340, REPLAY_PAD = 4, REPLAY_LANE = 9, REPLAY_RAIN_H = 30;
function replayScale(r) {
  const a = replayMs(r.window.from), now = replayMs(r.window.to), b = Math.max(now, replayMs(r.window.ahead_to) || now);
  const x = t => REPLAY_PAD + (Math.min(Math.max(t, a), b) - a) / (b - a) * (REPLAY_W - 2 * REPLAY_PAD);
  return { a, b, now, x };
}
function replaySvg(r) {
  const { a, b, now, x } = replayScale(r);
  let y = 0;
  const out = [];
  // Rain: a bar an hour; blank where not held, with a hatched strip at the foot to show the gap; the
  // forecast hours hatched.
  const rain = r.rain || {};
  if (rain.mm) {
    const top = Math.max(2, ...rain.mm.filter(v => v !== null)), fc = replayMs(rain.forecast_from), t0 = replayMs(rain.start);
    out.push(`<text x="${REPLAY_PAD}" y="${y + 10}" class="rp-lab">Rain upstream, mm an hour (model record)</text>`);
    y += 14;
    rain.mm.forEach((v, i) => {
      const s = t0 + i * 36e5, x0 = x(s), w = Math.max(0.5, x(s + 36e5) - x0 - 0.4);
      if (s + 36e5 <= a || s >= b) return;
      if (v === null) out.push(`<rect x="${x0.toFixed(1)}" y="${y + REPLAY_RAIN_H - 3}" width="${w.toFixed(1)}" height="3" class="rp-gap"/>`);
      else if (v > 0) { const h = Math.max(1, v / top * REPLAY_RAIN_H);
        out.push(`<rect x="${x0.toFixed(1)}" y="${(y + REPLAY_RAIN_H - h).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" class="${s >= fc ? 'rp-rain rp-fc' : 'rp-rain'}"/>`); }
    });
    out.push(`<text x="${REPLAY_W - REPLAY_PAD}" y="${y + 8}" text-anchor="end" class="rp-tick">${top.toFixed(1)} mm</text>`);
    y += REPLAY_RAIN_H + 8;
  }
  for (const o of r.overflows || []) {
    out.push(`<text x="${REPLAY_PAD}" y="${y + 10}" class="rp-lab">${replayEsc(replayName(o))}, ${o.km} km</text>`);
    y += 14;
    const lane1 = y, lane2 = y + REPLAY_LANE + 3;
    out.push(`<rect x="${REPLAY_PAD}" y="${lane1}" width="${REPLAY_W - 2 * REPLAY_PAD}" height="${REPLAY_LANE}" class="rp-track"/>`);
    for (const g of o.offline || []) {
      const x0 = x(replayMs(g.from)), x1 = g.to ? x(replayMs(g.to)) : x0 + 2;
      out.push(`<rect x="${x0.toFixed(1)}" y="${lane1}" width="${Math.max(1, x1 - x0).toFixed(1)}" height="${REPLAY_LANE}" class="rp-off"/>`);
    }
    for (const s of o.spills || []) {
      const s0 = replayMs(s.start), s1 = s.running ? now : s.end_known ? replayMs(s.end) : null;
      const x0 = x(s0), x1 = s1 === null ? x0 + 2 : x(s1);
      out.push(`<rect x="${x0.toFixed(1)}" y="${lane1}" width="${Math.max(1.5, x1 - x0).toFixed(1)}" height="${REPLAY_LANE}" class="rp-spill"/>`);
      if (s1 === null) out.push(`<text x="${(x0 + 3).toFixed(1)}" y="${lane1 + 8}" class="rp-tick">end not reported</text>`);
      const ar = s.arrival;
      if (ar) {
        const t0 = replayMs(ar.from), t1 = ar.to ? replayMs(ar.to) : (s.running ? now + (t0 - s0) : null);
        if (t0 < b && (t1 === null || t1 > a)) {
          const ax0 = x(t0), ax1 = t1 === null ? ax0 + 2 : x(t1);
          out.push(`<rect x="${ax0.toFixed(1)}" y="${lane2 + 0.5}" width="${Math.max(1.5, ax1 - ax0).toFixed(1)}" height="${REPLAY_LANE - 1}" class="rp-arr"/>`);
        }
      }
    }
    y = lane2 + REPLAY_LANE + 8;
  }
  // The axis: midnight and midday ticks in UK time, and now.
  const axis = y;
  for (let t = Math.ceil(a / 432e5) * 432e5 - 36e5 * 2; t <= b; t += 36e5) {
    const p = new Intl.DateTimeFormat('en-GB', { timeZone: REPLAY_TZ, hour: '2-digit', hourCycle: 'h23', weekday: 'short' }).formatToParts(new Date(t));
    const hr = +p.find(q => q.type === 'hour').value;
    if (t < a || (hr !== 0 && hr !== 12)) continue;
    const xx = x(t).toFixed(1);
    out.push(`<line x1="${xx}" y1="0" x2="${xx}" y2="${axis}" class="rp-grid"/>`);
    out.push(`<text x="${xx}" y="${axis + 11}" text-anchor="middle" class="rp-tick">${hr === 0 ? p.find(q => q.type === 'weekday').value : '12:00'}</text>`);
  }
  out.push(`<line x1="${x(now).toFixed(1)}" y1="0" x2="${x(now).toFixed(1)}" y2="${axis + 2}" class="rp-now"/>`
    + `<text x="${(x(now) - 2).toFixed(1)}" y="${axis + 22}" text-anchor="${b > now ? 'middle' : 'end'}" class="rp-tick rp-nowlab">Now</text>`);
  const h = axis + 26;
  return `<svg class="rp-svg" viewBox="0 0 ${REPLAY_W} ${h}" width="100%" role="img" aria-labelledby="rp-title" aria-describedby="rp-desc" focusable="false">`
    + `<title id="rp-title">Timeline of reported spills upstream and their modelled arrival here</title>`
    + `<desc id="rp-desc">The same as the table below it.</desc>`
    + `<defs><pattern id="rp-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" class="rp-hatchline"/></pattern></defs>`
    + out.join('') + '</svg>';
}
// The key: each mark drawn as the chart draws it, small, beside its words (no CSS gradient: docs/DESIGN.md).
const replaySwatch = inner => `<svg class="rp-sw" viewBox="0 0 16 9" aria-hidden="true" focusable="false">${inner}</svg>`;
const replayKey = () => '<p class="rp-key">'
  + `<span>${replaySwatch('<rect width="16" height="9" class="rp-spill"/>')}reported spilling (observed)</span>`
  + `<span>${replaySwatch('<rect x=".5" y=".5" width="15" height="8" class="rp-arr rp-arr-key"/><path d="M0 9L9 0M5 9L14 0M10 9L16 3" class="rp-hatchline"/>')}modelled to reach the spot (estimate)</span>`
  + `<span>${replaySwatch('<rect width="16" height="9" class="rp-off"/>')}no reading</span>`
  + `<span>${replaySwatch('<rect y="6" width="16" height="3" class="rp-gap"/>')}rain not held</span></p>`;

// The tile: folded, like the overflows, with a heading that can be reached by keyboard (its summary).
function replayTile(r) {
  if (!r || !r.window) return '';
  return `<details class="tile fold" id="replay" open><summary><span class="t-lab"><span>Upstream, the last 48 hours</span></span></summary>`
    + `<p class="t-say">What the company feeds reported at the overflows upstream, and when the model estimates each spill's water `
    + `reached, or will reach, this spot. The arrival times are an estimate from travel time down the river; they say nothing about what any spill did to the water here.</p>`
    + replaySvg(r) + replayKey()
    + `<p class="t-say">${replayRainSaid(r.rain)}</p><p class="t-say">${replayGaugeSaid(r.gauge)}</p>`
    + (replayQuietSaid(r) ? `<p class="t-say">${replayQuietSaid(r)}</p>` : '')
    + `<div class="rp-scroll" tabindex="0" role="region" aria-label="Table of reported spills">${replayTable(r)}</div>`
    + `<p class="sub">Prototype. Reported: the companies' live feeds as SwimSignal polled them, every 30 minutes; if two spills start and stop between two polls, only the second is recorded. `
    + `Modelled: the spill's start and end moved on by the overflow's travel time, as the forecast counts it. Times are UK time.</p></details>`;
}

// The page's styles for the tile, added once when it is first shown: only tokens (docs/DESIGN.md, Rules).
const REPLAY_CSS = `
.rp-svg { display:block; margin:8px 0 4px; font-family:var(--font-text); }
.rp-lab { font-size:11px; fill:var(--ink); }
.rp-tick { font-size:9px; fill:var(--muted); }
.rp-nowlab { fill:var(--ink); font-weight:600; }
.rp-track { fill:var(--track); opacity:.35; }
.rp-spill { fill:var(--veryhigh); }
.rp-arr { fill:url(#rp-hatch); stroke:var(--veryhigh); stroke-width:1; stroke-dasharray:2 1.5; }
.rp-hatchline { stroke:var(--veryhigh); stroke-width:1.5; }
.rp-off { fill:var(--ov-off); }
.rp-gap { fill:var(--unknown); }
.rp-rain { fill:var(--rain); }
.rp-fc { fill-opacity:.4; stroke:var(--rain); stroke-width:.5; }
.rp-grid { stroke:var(--line); stroke-width:.5; }
.rp-now { stroke:var(--ink); stroke-width:1; }
.rp-key { font-size:var(--fs-meta); color:var(--muted); display:flex; flex-wrap:wrap; gap:4px 12px; align-items:center; margin:4px 0 8px; }
.rp-sw { display:inline-block; width:16px; height:9px; margin-right:4px; vertical-align:middle; }
.rp-arr-key { fill:none; }
.rp-scroll { overflow-x:auto; }
.rp-scroll:focus-visible { outline:2px solid var(--focus); outline-offset:2px; border-radius:var(--radius-ring); }
.rp-table { width:100%; border-collapse:collapse; font-size:var(--fs-note); }
.rp-table caption { text-align:left; font-weight:600; padding:4px 0; }
.rp-table th, .rp-table td { text-align:left; vertical-align:top; padding:6px 4px; border-top:1px solid var(--line); }
.rp-table th[scope=row] { font-weight:600; width:38%; }
.rp-table td p { margin:0 0 4px; }
.rp-meta { display:block; font-weight:400; font-size:var(--fs-meta); color:var(--muted); }
@media (max-width:480px) { .rp-table thead { display:none; } .rp-table tr, .rp-table th, .rp-table td { display:block; width:auto; }
  .rp-table th[scope=row] { width:auto; border-top:1px solid var(--line); } .rp-table td { border-top:0; padding-top:0; } }
`;
function replayStyle(doc) {
  if (!doc || doc.getElementById('rp-style')) return;
  const s = doc.createElement('style');
  s.id = 'rp-style';
  s.textContent = REPLAY_CSS;
  doc.head.appendChild(s);
}

if (typeof module === 'object' && module.exports) {
  module.exports = { replayTime, replaySpillSaid, replayOfflineSaid, replayRainSaid, replayGaugeSaid, replayQuietSaid, replayTable,
    replaySvg, replayTile, replayKey, replaySwatch, replayStyle, REPLAY_CSS, REPLAY_STATE };
}
