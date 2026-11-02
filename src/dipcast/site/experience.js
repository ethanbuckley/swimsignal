// Plain, testable evidence summaries. No invented measurements or confidence scores.
// The level rules (levels.js): the page loads them after this file, so they are looked up when a
// summary is made; Node requires them.
// A check's date as people write it, "3 Oct 2026", not "2026-10-03"; anything else as given.
const experienceWhen = (d => /^\d{4}-\d{2}-\d{2}$/.test(String(d)) ? new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' }) : d);
const rules = () => typeof headParts === 'function'
  ? { coverage, FOUND_NONE, daily, dayLevel, dayHeadline, nowUnknown, nowUnknownWhy, eaUnchecked, EA_UNCHECKED, rank, liveHead } : require('./levels.js');
const dayMonthYear = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
// The latest lab sample in the words of a spot's "What the level rests on" (evidence.js, evidenceSample),
// as plain text; the page loads that file before this one, and Node requires it. Where there is none, it
// says so: none this season, none in this update (the build had no samples file), or none taken here.
const sampleWords = () => typeof evidenceSample === 'function' ? evidenceSample : require('./evidence.js').evidenceSample;
function waterSamples(s, now = Date.now()) {
  const cl = s.classification, said = sampleWords()(s.lab_sample, now);
  const page = cl?.url ? ' Check the Environment Agency’s page for every result and current advice.' : '';
  if (said) return said + page;
  if (s.source === 'sepa') return 'SEPA samples this loch in the bathing season. Its results are on SEPA’s page; SwimSignal does not republish them.';
  if (s.source !== 'designated' && !cl) return 'No lab samples here.';   // the rating row says it is not a bathing water
  return (s.lab_sample === null ? 'No lab sample this season.' : 'No lab sample in this update.') + page;
}
// The comparison's rows in plain text, for one spot on one day (iso), each a fact or what is not known.
// No "Forecast" or "Live spill feeds" row: the five days and Right now (compareRows) say both, and more.
function evidenceRows(s, iso, generatedAt = null, now = Date.now()) {
  const total = s.upstream_summary?.overflows || 0;
  const day = (s.days || []).find(x => x.date === iso), cl = s.classification;
  // The build's mark on the day, as the page goes by (ecoliUntested); a day without one (no forecast
  // that day, or one built before the mark) goes by the calendar month, May to September.
  const offSeason = day && typeof day.in_validated_season === 'boolean' ? !day.in_validated_season
    : ![5, 6, 7, 8, 9].includes(Number(iso.slice(5, 7)));
  const sr = (s.sepa || {}).rating;
  return [
    s.source === 'sepa' ? ['SEPA rating', sr?.value ? `${sr.value}${sr.year ? ' · ' + sr.year : ''}. SEPA's rating from its samples over up to four seasons; not today’s water quality.` : 'SEPA designated bathing water; no rating available in this update.'] :
    ['Environment Agency rating', cl?.class ? `${cl.class.charAt(0).toUpperCase() + cl.class.slice(1)}${cl.year ? ' · ' + cl.year : ''}. Based on up to four seasons of samples; not today’s water quality.`
      : s.source === 'designated' ? 'Designated bathing water; no rating available in this update.' : 'Not an Environment Agency designated bathing water. No bathing-water rating shown.'],
    ['Water samples', waterSamples(s, now)],
    ['Model limits', total && !s.error && s.location?.mode !== 'lake'
      ? (offSeason ? 'Outside May–September: the E. coli estimate is untested for this season.' : 'E. coli model tested on river bathing waters in May–September; it is not a test of this spot today.')
      : 'No validated daily E. coli estimate is shown here.'],
    ['Algae observation', s.algae?.date ? `${s.algae.phrase || 'Visual check'} · ${dayMonthYear(s.algae.date)}. A past visual observation, not a current algae warning.` : 'No algae observation in this update. This does not mean algae are absent.'],
    ['Local warnings', [...flowFacts(s, Date.now(), generatedAt).filter(f => f.flood).map(f => flowSentence(f)),
      floodUnchecked(s, Date.now(), generatedAt) ? floodUncheckedLine() : '',
      floodUnmatched(s, Date.now(), generatedAt) ? floodUnmatchedLine() : '',
      'Short-term pollution warnings are not fetched by this app. Check official advice and signs at the water.'].filter(Boolean).join(' ')]
  ];
}

// ------------------------------------------------------------------------------ the comparison
// Compare (Saved's "Compare your spots" and Plan a swim's "Compare these spots", for "which of these
// places should I look into further for Saturday?"). Up to three
// spots side by side (index.html, compareTable): the five days, then what each level rests on and what it
// leaves out. Every cell says something; where the data is missing it says it is not known, never nothing,
// which a reader takes for nothing wrong.
//
// The five days, a cell each, in the words a row of the list gives the day (levels.js, dayHeadline): a day
// without a forecast says so. A spot whose level is the same every day (no monitored overflow upstream, a
// forecast that failed, a standing rating) is `same`, and the table gives it one cell for the five.
function compareDays(s, dates) {
  const R = rules();
  return { same: !R.daily(s), days: dates.map(iso => ({ date: iso, level: R.dayLevel(s, iso), words: R.dayHeadline(s, iso) })) };
}
// The Saved page's day by day (index.html, savedGrid): a spot's row of cells, each the day's level in two
// words ("Moderate risk"), with the day's headline for a screen reader
// ("Moderate risk: sewage spills"), or "No forecast" for a day the forecast does not have. `rule`: the cell is
// a level, so it carries the level's 4 px rule; nothing else does. A spot whose level does not change from
// day to day has one cell for the five (same), in its headline's words: "No monitored overflow found
// upstream" is not a level and never reads as one.
function weekCells(s, dates) {
  const R = rules(), d = compareDays(s, dates), lv = l => R.rank(l) >= 0;
  if (d.same) { const x = d.days[0]; return { same: true, level: x.level, rule: lv(x.level), words: x.words, said: x.words, cells: [] }; }
  return { same: false, cells: d.days.map(x => ({ date: x.date, level: x.level, rule: lv(x.level), said: x.words,
    words: lv(x.level) ? `${x.level[0].toUpperCase()}${x.level.slice(1)} risk` : 'No forecast' })) };
}
// Right now: the overflows upstream as a spot's "What the level rests on" gives them (evidence.js,
// evidenceOverflows): discharging, stopped lately, how many report live, and why the others do not (offline,
// no live feed, a feed down or not updated). The page loads evidence.js first; Node requires it. Where right
// now is not known (levels.js, nowUnknown), it says so first, in the headline's words.
const overflowWords = () => typeof evidenceOverflows === 'function' ? evidenceOverflows : require('./evidence.js').evidenceOverflows;
function compareNow(s, generatedAt = null) {
  const R = rules(), total = s.upstream_summary?.overflows || 0, n = s.now || {};
  if (s.error) return htmlText(`${R.coverage(s)}.`);
  if (!total) return `${R.FOUND_NONE}, so no spills to report. Other pollution sources may still affect this water.`;
  if (n.monitored_upstream == null) return `Not known: this update has no live status for the ${total} overflow${total === 1 ? '' : 's'} upstream.`;
  const mon = Math.min(total, n.monitored_upstream);
  return (R.nowUnknown(s) && mon ? `${R.liveHead(s)}: right now not known here. ` : '') + overflowWords()(s, generatedAt).say
    + (mon < total ? ' Missing reports do not mean no spills.' : '');
}
// Today's advice from the Environment Agency, against bathing after pollution or algae: the build and the
// page cannot read it (eatoday.js), so at a designated bathing water the cell says it was not checked and
// links to the EA's page, which has it. The EA gives none elsewhere.
const eaPageFor = () => typeof eaTodayPage === 'function' ? { eaTodayPage, eaTodayId, eaTodayAdvice: typeof eaTodayAdvice === 'function' ? eaTodayAdvice : () => [],
  eaTodayBrief: typeof eaTodayBrief === 'function' ? eaTodayBrief : () => '',
  eaTodayFirst: typeof eaTodayFirst === 'function' ? eaTodayFirst : () => 'Read the official notice first' } : require('./eatoday.js');
// A reviewed notice (spots.json `official`) is said in its compact form, with its publisher's page, in place
// of "could not be checked", as the spot page's coverage line does (eatoday.js, eaTodayCover).
function compareAdvice(s) {
  const R = rules(), E = eaPageFor(), o = E.eaTodayAdvice(s)[0];
  if (o) return `Official: ${htmlText(E.eaTodayBrief(s))}. ${E.eaTodayFirst(s)}.`   // follow only a restricting notice
    + (/^https:\/\/[^\s"<>]+$/.test(o.link || '') ? ` <a href="${htmlText(o.link)}">The ${htmlText(o.publisher)}'s page</a> has the latest.` : '');
  if (R.eaUnchecked(s)) {
    const id = E.eaTodayId(s), url = /^https:\/\//.test(s.classification.url || '') ? s.classification.url : id ? E.eaTodayPage('', id) : '';
    return htmlText(R.EA_UNCHECKED) + (url ? ` <a href="${htmlText(url)}">The EA's page</a> has any advice against bathing there today.` : '');
  }
  if (s.source === 'designated') return 'Not known: this update has no Environment Agency page for this bathing water.';
  if (s.source === 'sepa') return 'Not checked: SEPA’s page and the sign at the water give any advice for today.';
  return 'None: not a designated bathing water, so the Environment Agency gives no bathing advice for it.';
}
// Access at the spot (access.py: a desk check of the authority's guidance, for the spots from OpenStreetMap
// and the curated ones in the Peak District): what it found, in its own words, and when. A plan's row gives the status in a few words (ACCESS_WORDS,
// index.html's planWhy). A spot without a check says so.
const ACCESS_WORDS = { restricted_guidance: 'Park guidance restricts river swimming; not checked here.', unconfirmed: 'Permission to swim at this point is not confirmed.' };
function compareAccess(s) {
  const a = s.access;
  if (!a) return vTag('none', 'No access information');
  // When it was checked is its kind and time; "signs at the water not inspected" is the row's note (compareRows).
  return htmlText(a.text || ACCESS_WORDS[a.status] || 'Not known whether swimming is allowed at this point.') + ' '
    + (a.checked_at ? vTag('measured', `Checked ${htmlText(experienceWhen(a.checked_at))}`) : vTag('none', 'Not known when it was checked'))
    + (/^https:\/\//.test(a.url || '') ? ` <a href="${htmlText(a.url)}">Authority guidance</a>` : '');
}
// The rows under the five days, as [label, HTML, note], for one spot; iso is the day picked, whose E. coli
// model limits the last row gives. Short cells (2 Nov 2026): the caveat every column shares is the note, which the
// table says once under the row's label (index.html, compareTable); a cell keeps only what is its own. The spot's own
// "not confirmed", official advice and missing data stay in its cell.
const vTag = (kind, words) => typeof valueTag === 'function' ? valueTag(kind, words) : `<span class="vt vt-${kind}">${words}</span>`;
function compareRating(s) {
  const cl = s.classification, sr = (s.sepa || {}).rating;
  if (s.source === 'sepa') return sr?.value ? `${htmlText(sr.value)}${sr.year ? ', ' + htmlText(sr.year) : ''} (SEPA)` : vTag('none', 'No SEPA rating in this update');
  if (cl?.class) return `${htmlText(cl.class.charAt(0).toUpperCase() + cl.class.slice(1))}${cl.year ? ', ' + htmlText(cl.year) : ''}`;
  return s.source === 'designated' ? vTag('none', 'No rating in this update') : 'Not a designated bathing water';
}
function compareSample(s, now) {
  const said = sampleWords()(s.lab_sample, now);
  if (said) return htmlText(said);
  if (s.source === 'sepa') return 'SEPA’s page has its results';
  if (s.source !== 'designated' && !s.classification) return vTag('none', 'None taken here');
  return vTag('none', s.lab_sample === null ? 'None this season' : 'None in this update');
}
function compareAlgae(s) {
  const a = s.algae;
  const said = String(a?.phrase || 'Visual check');
  return a?.date ? `${htmlText(said.charAt(0).toUpperCase() + said.slice(1))} ${vTag('measured', `Seen ${dayMonthYear(a.date)}`)}` : vTag('none', 'None recorded in this update');
}
function compareWarnings(s, generatedAt, now) {
  const said = [...flowFacts(s, now, generatedAt).filter(f => f.flood).map(f => flowSentence(f)),
    floodUnchecked(s, now, generatedAt) ? floodUncheckedLine() : '', floodUnmatched(s, now, generatedAt) ? floodUnmatchedLine() : ''].filter(Boolean);
  if (said.length) return htmlText(said.join(' '));
  if (generatedAt && hoursAgo(generatedAt, now) > FLOW_MAX_H.build) return vTag('none', 'Not known') + ' ' + vTag('stale', 'This forecast is over a day old');
  return Array.isArray(s.flood_alerts) ? 'No flood alert matched to this spot' : vTag('none', 'Not known');
}
function compareRows(s, iso, generatedAt = null, now = Date.now()) {
  const f = Object.fromEntries(evidenceRows(s, iso, generatedAt, now));
  // Official advice first, as everywhere (2 Nov 2026).
  return [["Today's official advice", compareAdvice(s)], ['Right now', compareNow(s, generatedAt), 'Live spill reports from overflows upstream'],
    ['Bathing-water rating', compareRating(s), 'From up to four seasons of samples; not today’s water quality'],
    ['Latest lab sample', compareSample(s, now), 'E. coli on the day it was taken; the Environment Agency’s page has every result'],
    ['Algae', compareAlgae(s), 'A past visual check, not a current warning. None recorded does not mean none there'],
    ['Access', compareAccess(s), 'A desk check of published sources; signs at the water not inspected'],
    ['Flood warnings', compareWarnings(s, generatedAt, now), 'Short-term pollution warnings are not fetched here: check official advice and the signs at the water'],
    ['Model limits', htmlText(f['Model limits'])]];
}
// "Too high to swim" (build_site.attach_flow_state): the river high or rising fast at a gauge on the
// spot's own river, and the Environment Agency's flood alerts and warnings in force whose area's outline
// covers the spot's point on its water, or reaches its lake (build_site.attach_flow_state), the most
// severe first: "in force here", since the EA's outline says where an alert applies. A different hazard
// from pollution, so never part of the level. Each is said only
// while it can still be true when read: not from a gauge reading over a day old (flows.MAX_READING_AGE_H),
// a rise whose last reading is over six hours old, or a build over a day old. So a stale reading never
// shows "River high", whether the build found it stale or it went stale on a phone since.
const FLOW_MAX_H = { reading: 24, rise: 6, build: 24 };
const FLOOD_SERVICE = 'https://check-for-flooding.service.gov.uk/';
const hoursAgo = (iso, now) => { const t = Date.parse(iso); return Number.isNaN(t) ? Infinity : (now - t) / 36e5; };
const clockTime = iso => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });
function flowFacts(s, now = Date.now(), generatedAt = null) {
  if (generatedAt && hoursAgo(generatedAt, now) > FLOW_MAX_H.build) return [];
  const rs = s.river_state || {}, out = [];
  const current = !rs.stale && !!rs.station && hoursAgo(rs.observed_at, now) <= FLOW_MAX_H.reading;
  if (s.flow_state === 'high' && current) out.push({ lead: 'River high', say: `the gauge at ${rs.station} is above its usual range` });
  else if (s.flow_state === 'rising fast' && current && typeof rs.rise_6h_m === 'number' && hoursAgo(rs.rise_to, now) <= FLOW_MAX_H.rise)
    out.push({ lead: 'River rising fast', say: `the gauge at ${rs.station} rose ${rs.rise_6h_m.toFixed(2)} m between ${clockTime(rs.rise_from)} and ${clockTime(rs.rise_to)}` });
  const fl = (s.flood_alerts || []).filter(f => f && f.severity);
  if (fl.length) out.push({ flood: true, lead: `${fl[0].severity} in force here`, area: fl[0].area || '', url: fl[0].url || '', more: fl.length - 1 });
  return out;
}
// null is "the EA did not answer" (after one retry, build_site.attach_flow_state), which must not read
// as none in force ([]); a spot without the field (an unlisted point) says nothing. Said quietly, under
// the level tile, and not beside the answer: in bold above the five days it read like a hazard (48 of
// 105 pages, 16 Oct 2026). Not from a build over a day old, as flowFacts.
const floodUnchecked = (s, now = Date.now(), generatedAt = null) =>
  s.flood_alerts === null && !(generatedAt && hoursAgo(generatedAt, now) > FLOW_MAX_H.build);
const floodUncheckedLine = (html = false) => 'Flood warnings not checked for this forecast. '
  + (html ? `<a href="${FLOOD_SERVICE}">See the Environment Agency</a>.` : `See the Environment Agency: ${FLOOD_SERVICE}`);
// Alerts in force that could not be matched to this spot (flows.split_flood_alerts, "unknown": for its
// own river or lake but an area that does not cover it, or an area with no outline or no named water):
// said, neutrally, beside the unchecked line, never as a named warning and never as none. Alerts for
// other water (another river, the coast) are not this spot's and are not said (`flood_alerts_other`).
// Not from a build over a day old.
const floodUnmatched = (s, now = Date.now(), generatedAt = null) =>
  Array.isArray(s.flood_alerts) && s.flood_alerts_unmatched > 0 && !(generatedAt && hoursAgo(generatedAt, now) > FLOW_MAX_H.build);
const floodUnmatchedLine = (html = false) => 'A flood alert or warning is in force that could not be matched to this spot. '
  + (html ? `<a href="${FLOOD_SERVICE}">Check the Environment Agency's flood map</a>.` : `Check the Environment Agency's flood map: ${FLOOD_SERVICE}`);
// One fact as a sentence: plain text for the comparison, or HTML for the answer (escaped here, with
// the lead in bold and the flood area linked to the Environment Agency's page for it).
const htmlText = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[c]);
function flowSentence(f, html = false) {
  const e = html ? htmlText : x => x, lead = html ? `<b>${e(f.lead)}</b>` : f.lead;
  if (!f.flood) return `${lead}: ${e(f.say)}.`;
  const area = !f.area ? '' : html && f.url ? `<a href="${e(f.url)}">${e(f.area)}</a>` : e(f.area);
  return `${lead} (Environment Agency)${area ? ': ' + area : ''}${f.more ? ` and ${f.more} more` : ''}.`;
}
// A list kept in localStorage (saved spots, the swim log), read back safely: anything but an array
// (a hand edit, another version's format, a broken write) reads as empty, and entries keep() turns
// down are dropped, so that the page cannot stop on them.
function storedList(text, keep = () => true) {
  let v; try { v = JSON.parse(text || '[]'); } catch (e) { return []; }
  return Array.isArray(v) ? v.filter(keep) : [];
}
function comparisonIds(ids, available) {
  const valid = new Set(available.map(s => s.id));
  return [...new Set(ids.filter(id => valid.has(id)))].slice(0,3);
}
if (typeof module === 'object' && module.exports) module.exports = {evidenceRows, compareDays, weekCells, compareNow, compareAdvice, compareAccess, compareRows, ACCESS_WORDS,
  comparisonIds, storedList, flowFacts, flowSentence, floodUnchecked, floodUncheckedLine, floodUnmatched, floodUnmatchedLine};
