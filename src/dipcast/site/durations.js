// Spill durations (durations.html): how long storm overflow spills lasted in 2024 and 2025, from the Environment
// Agency's start/stop records (docs/SPILL-DURATIONS-CONTRACT-v1.md), read from the files the build splits the research
// export into (build_site.write_spill_durations): data/research/spill_durations.json, the export without its overflows,
// with the spots that have a file; data/research/spill_durations/<spot id>.json, the overflows upstream of one spot.
//
// What it may say is the contract's, and only that: how long a given overflow's spills lasted in 2024 and 2025 (typical,
// long end, longest), and how often, across a company's overflows, a spill already running some hours was still running
// hours later. Never when a running spill will end (that would be a forecast, and none has been shown to work), how much
// was discharged, that a short spill was harmless, or that companies record spills alike (they do not). The export's own
// sentence (`claim.public_wording`) stands beside a spot's figures, its `not_claimed` list is said in full, and every
// figure names its years. The page is history: its years are said first, and nothing on it is about today.
//
// A plain script, like lakes.js: in the page its names are globals (each begins durations or DURATIONS), and in Node the
// last lines export them (tests/site_durations.test.cjs).

const durationsEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const durationsCount = n => (typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('en-GB') : '–');
const durationsPct = v => (typeof v === 'number' && Number.isFinite(v) ? `${Math.round(v * 100)}%` : '–');
const durationsPlural = (n, one, many = `${one}s`) => `${durationsCount(n)} ${n === 1 ? one : many}`;
// The Environment Agency's spelling of Dŵr Cymru has no circumflex (levels.js, companyName).
const durationsCompany = s => String(s ?? '').replace(/\bDwr Cymru\b/, 'Dŵr Cymru');

// A spill's length in words: minutes under an hour, hours to two days, days beyond, the number and its unit kept on one
// line (a no-break space). profile.py's hours_said says the same.
function durationsHours(h) {
  if (typeof h !== 'number' || !Number.isFinite(h)) return '–';
  if (h < 1) { const m = Math.round(h * 60); return m < 1 ? 'under\u00a01\u00a0min' : `${m}\u00a0min`; }
  if (h < 10) return `${h.toFixed(1).replace(/\.0$/, '')}\u00a0h`;
  if (h < 48) return `${Math.round(h)}\u00a0h`;
  const d = h / 24;
  return `${d < 10 ? d.toFixed(1).replace(/\.0$/, '') : Math.round(d)}\u00a0days`;
}

// The records' years, from the export's `period`: "2024 and 2025", "2024-25", and the span in full.
const DURATIONS_DATE = iso => new Date(`${String(iso).slice(0, 10)}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
function durationsYears(period) {
  const p = period || {}, a = String(p.from || '2024').slice(0, 4), b = String(p.to || '2025').slice(0, 4);
  return { from: a, to: b, said: a === b ? a : `${a} and ${b}`, short: a === b ? a : `${a}-${b.slice(2)}`,
    span: p.from && p.to ? `${DURATIONS_DATE(p.from)} to ${DURATIONS_DATE(p.to)}` : `${a} to ${b}` };
}

// ------------------------------------------------------------------------------ a table
// Numbers right; on a phone each row is a block, its name over its figures, each with its column's name (data-l), as on
// a spot's overflow history (profile.html).
function durationsTable(head, rows, label) {
  const th = head.map(([h, num]) => `<th scope="col"${num ? ' class="num"' : ''}>${durationsEsc(h)}</th>`).join('');
  const body = rows.map(r => '<tr>' + r.map((c, i) => (i === 0 ? `<th scope="row" class="ov">${c}</th>`
    : `<td${head[i][1] ? ' class="num"' : ''} data-l="${durationsEsc(head[i][0])}">${c}</td>`)).join('') + '</tr>').join('');
  return `<div class="tw" tabindex="0" role="region" aria-label="${durationsEsc(label)}, scrolls sideways"><table class="dut"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// ------------------------------------------------------------------------------ the whole file
// What the records are, first: their years, that they are history, how many overflows and spills, and the nine companies.
function durationsSummary(index) {
  if (!index || !index.available) return `<p class="du-none">No spill durations are published in this update${index && index.why ? ` (${durationsEsc(index.why)})` : ''}.</p>`;
  const y = durationsYears(index.period), c = index.coverage || {}, n = (index.companies || []).length;
  return `<p class="du-sum"><b>History: ${durationsEsc(y.span)}.</b> Nothing after that is in these records. `
    + `${durationsPlural(c.spills, 'spill')} at ${durationsPlural(c.overflows, 'storm overflow')} of ${n === 9 ? 'the nine' : durationsCount(n)} English water companies, `
    + `from the monitor records the companies send the Environment Agency. ${durationsCount(c.overflows_few)} of the overflows had fewer than ${durationsEsc((index.method || {}).few_below ?? 5)} spills in the two years.</p>`;
}

// Each company's spill lengths: overflows, spills, typical (median), long end (1 in 10 longer), and the share over 6 and 24 hours.
function durationsCompanies(index) {
  const rows = (index && index.company) || [];
  if (!rows.length) return '';
  const y = durationsYears(index.period);
  return durationsTable([['Company', false], ['Overflows', true], ['Spills', true], ['Typical spill', true], ['Long end', true],
    ['Over 6 hours', true], ['Over 24 hours', true]],
  rows.map(r => [durationsEsc(durationsCompany(r.company)), durationsCount(r.overflows), durationsCount(r.spills), durationsHours(r.median_h),
    durationsHours(r.p90_h), durationsPct(r.share_over_6h), durationsPct(r.share_over_24h)]), `Spill lengths by company, ${y.short}`);
}

// ------------------------------------------------------------------------------ spills already running
const DURATIONS_LATER = [1, 3, 6, 12, 24];
const DURATIONS_ALL = 'all nine';
const durationsAts = index => [...new Set(((index && index.still_running) || []).map(r => r.running_at_least_h))].sort((a, b) => a - b);
// "had been running" (0: any running hour) or "had already run at least 3 hours".
const durationsAtSaid = at => (at > 0 ? `had already run at least ${durationsPlural(at, 'hour')}` : 'was running');
// The rows for one "already running" length: each company in the export's order, then all nine together.
function durationsRunning(index, at) {
  const rows = ((index && index.still_running) || []).filter(r => r.running_at_least_h === at);
  return [...rows.filter(r => r.company !== DURATIONS_ALL), ...rows.filter(r => r.company === DURATIONS_ALL)];
}
// One figure in words, with the count behind it: across a company's overflows (or all nine), at the hours when a spill
// had already run `at` hours, the share at which it was still running `later` hours on. A description of the years, not
// of any spill now.
function durationsStillSentence(row, at, later, period) {
  if (!row) return '';
  const v = row[`still_after_${later}h`], y = durationsYears(period);
  if (typeof v !== 'number') return '';
  const who = row.company === DURATIONS_ALL ? 'Across all nine companies' : `At ${durationsCompany(row.company)}'s overflows`;
  return `${who} in ${y.said}, a spill that ${durationsAtSaid(at)} was still running ${durationsPlural(later, 'hour')} later at ${durationsPct(v)} `
    + `of the ${durationsCount(row.hours)} hours checked.`;
}
function durationsAtPicker(index, at) {
  return `<label class="du-pick">Spills that<select id="du-at">${durationsAts(index).map(a => `<option value="${a}"${a === at ? ' selected' : ''}>${a > 0 ? `had already run at least ${durationsPlural(a, 'hour')}` : 'were running, at any point'}</option>`).join('')}</select></label>`;
}
// The sentence for all nine, then each company's figures at every later time, with the hours behind each row.
function durationsStill(index, at, later = 6) {
  const rows = durationsRunning(index, at);
  if (!rows.length) return '';
  const y = durationsYears(index.period), all = rows.find(r => r.company === DURATIONS_ALL);
  return `<p class="du-still">${durationsEsc(durationsStillSentence(all, at, later, index.period))} That describes ${durationsEsc(y.said)}. It does not say when a spill running now will end.</p>`
    + durationsTable([['Company', false], ['Hours checked', true], ...DURATIONS_LATER.map(h => [`${h} h later`, true])],
      rows.map(r => [r.company === DURATIONS_ALL ? '<b>All nine</b>' : durationsEsc(durationsCompany(r.company)), durationsCount(r.hours),
        ...DURATIONS_LATER.map(h => durationsPct(r[`still_after_${h}h`]))]),
      `Still running, spills that ${durationsAtSaid(at)}, ${y.short}`);
}

// ------------------------------------------------------------------------------ one spot's overflows
function durationsSpotPicker(index, sel) {
  const spots = [...((index && index.spots) || [])].sort((a, b) => String(a.name).localeCompare(String(b.name), 'en-GB'));
  return `<label class="du-pick">Swim spot<select id="du-spot-select"><option value="">Choose a spot</option>${spots.map(s => `<option value="${durationsEsc(s.id)}"${s.id === sel ? ' selected' : ''}>${durationsEsc(s.name)}</option>`).join('')}</select></label>`;
}
// The spot's overflows that the records have, in the order of its overflow history page (the one whose spills matter
// most there first), the export's own sentence beside them; then those it has not, said as no record, never as no spills.
function durationsSpot(one, index) {
  const y = durationsYears((one && one.period) || (index && index.period)), rows = (one && one.overflows) || [], absent = (one && one.absent) || [];
  const wording = ((index && index.claim) || {}).public_wording || '';
  const link = `<a href="spot/${durationsEsc(encodeURIComponent(one.id))}/profile/">Its overflow history</a>, with each year's annual return`;
  let out = `<h3 id="du-spot-h">${durationsEsc(one.name || one.id)}</h3><p class="du-claim"><b>History: ${durationsEsc(y.said)}.</b>${rows.length ? ` ${durationsEsc(wording)}` : ''}</p>`;   // the export's sentence beside figures only
  if (rows.length) {
    out += durationsTable([['Overflow and id', false], ['Company', false], [`Typical spill, ${y.short}`, true], ['Long end', true], ['Longest', true],
      [`Spills ${y.from}`, true], [`Spills ${y.to}`, true]],
    rows.map(r => [`${durationsEsc(r.name || r.site_id)}<br><span class="muted">${r.own ? `${durationsEsc(r.own)} · ` : ''}${durationsEsc(r.site_id)}</span>`,
      durationsEsc(durationsCompany(r.company)), durationsHours(r.median_h) + (r.few ? ', few spills' : ''), durationsHours(r.p90_h), durationsHours(r.longest_h),
      durationsCount(r.spills_2024), durationsCount(r.spills_2025)]), `Spill lengths upstream of ${one.name || one.id}, ${y.short}`);
  }
  if (absent.length) {
    const k = absent.length, welsh = absent.some(a => /cymru/i.test(String(a.company || '')));
    const lead = rows.length ? `${durationsCount(k)} of the ${durationsCount(rows.length + k)} overflows upstream ${k === 1 ? 'has' : 'have'} no spill`
      : `None of the ${durationsCount(k)} overflows upstream has a spill`;
    out += `<p class="du-absent">${lead} in these ${durationsEsc(y.short)} records: none was recorded, or there is no record${welsh ? " (Dŵr Cymru Welsh Water's overflows are not in them)" : ''}. `
      + 'That is not the same as no spills.</p>';
  }
  return out + `<p class="du-more">${link}.</p>`;
}

// ------------------------------------------------------------------------------ in the page
function durationsMount(root) {
  const host = root.getElementById('durations');
  if (!host) return;
  const get = p => fetch(p, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  get('data/research/spill_durations.json').then(index => {
    const put = (id, html) => { const el = root.getElementById(id); if (el) el.innerHTML = html; };
    if (!index) { host.innerHTML = '<p class="du-none">The spill durations could not be loaded.</p>'; return; }
    host.innerHTML = durationsSummary(index);
    if (!index.available) return;
    const y = durationsYears(index.period);
    root.querySelectorAll('[data-years]').forEach(el => { el.textContent = el.dataset.years === 'short' ? y.short : y.said; });
    const not = root.getElementById('du-not'), attrib = root.getElementById('du-attrib');
    if (not && index.claim && Array.isArray(index.claim.not_claimed) && index.claim.not_claimed.length) not.innerHTML = index.claim.not_claimed.map(t => `<li>${durationsEsc(t)}</li>`).join('');
    if (attrib && Array.isArray(index.attribution) && index.attribution.length) attrib.textContent = index.attribution.join('. ').replace(/\.?$/, '.');
    put('du-companies', durationsCompanies(index));
    const ats = durationsAts(index);
    let at = ats.includes(3) ? 3 : ats[0];
    const drawStill = () => {
      put('du-still', durationsAtPicker(index, at) + durationsStill(index, at));
      const sel = root.getElementById('du-at');
      if (sel) sel.addEventListener('change', () => { at = +sel.value; drawStill(); const again = root.getElementById('du-at'); if (again) again.focus(); });
    };
    drawStill();
    const pickId = () => decodeURIComponent((location.hash.match(/^#spot=([A-Za-z0-9-]+)$/) || [])[1] || '');
    const drawSpot = () => {
      const id = pickId();
      put('du-spot', durationsSpotPicker(index, id) + '<div id="du-one" aria-live="polite"></div>');
      const sel = root.getElementById('du-spot-select');
      if (sel) sel.addEventListener('change', () => { location.hash = sel.value ? `spot=${encodeURIComponent(sel.value)}` : ''; });
      const one = root.getElementById('du-one');
      if (!one || !id || !(index.spots || []).some(s => s.id === id)) return;
      one.innerHTML = '<p class="du-none">Loading…</p>';
      get(`data/research/spill_durations/${encodeURIComponent(id)}.json`).then(doc => {
        if (pickId() !== id) return;
        one.innerHTML = doc ? durationsSpot(doc, index) : '<p class="du-none">This spot could not be loaded.</p>';
      });
    };
    window.addEventListener('hashchange', drawSpot);
    drawSpot();
  });
}
if (typeof document === 'object' && document.getElementById) durationsMount(document);

if (typeof module === 'object' && module.exports) {
  module.exports = { durationsHours, durationsYears, durationsSummary, durationsCompanies, durationsAts, durationsRunning, durationsStillSentence,
    durationsAtPicker, durationsStill, durationsSpotPicker, durationsSpot, durationsCompany, durationsPct, DURATIONS_LATER };
}
