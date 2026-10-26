// Plain, testable evidence summaries. No invented measurements or confidence scores.
// The level rules (levels.js): the page loads them after this file, so they are looked up when a
// summary is made; Node requires them.
const rules = () => typeof headParts === 'function'
  ? { coverage, FOUND_NONE, daily, dayLevel, dayHeadline, nowUnknown, nowUnknownWhy, eaUnchecked, EA_UNCHECKED, rank } : require('./levels.js');
const dayMonthYear = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
// The latest lab sample in the words of a spot's "What the level rests on" (evidence.js, evidenceSample),
// as plain text; the page loads that file before this one, and Node requires it. Where there is none, it
// says so: none this season, none in this update (the build had no samples file), or none taken here.
const sampleWords = () => typeof evidenceSample === 'function' ? evidenceSample : require('./evidence.js').evidenceSample;
function waterSamples(s, now = Date.now()) {
  const cl = s.classification, said = sampleWords()(s.lab_sample, now);
  const page = cl?.url ? ' Check the Environment Agency’s page for every result and current advice.' : '';
  if (said) return said + page;
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
  return [
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
  return (R.nowUnknown(s) && mon ? `Not known here: ${R.nowUnknownWhy(s)}. ` : '') + overflowWords()(s, generatedAt).say
    + (mon < total ? ' Missing reports do not mean no spills.' : '');
}
// Today's advice from the Environment Agency, against bathing after pollution or algae: the build and the
// page cannot read it (eatoday.js), so at a designated bathing water the cell says it was not checked and
// links to the EA's page, which has it. The EA gives none elsewhere.
const eaPageFor = () => typeof eaTodayPage === 'function' ? { eaTodayPage, eaTodayId } : require('./eatoday.js');
function compareAdvice(s) {
  const R = rules();
  if (R.eaUnchecked(s)) {
    const E = eaPageFor(), id = E.eaTodayId(s), url = /^https:\/\//.test(s.classification.url || '') ? s.classification.url : id ? E.eaTodayPage('', id) : '';
    return htmlText(R.EA_UNCHECKED) + (url ? ` <a href="${htmlText(url)}">The EA's page</a> has any advice against bathing there today.` : '');
  }
  if (s.source === 'designated') return 'Not known: this update has no Environment Agency page for this bathing water.';
  return 'None: not a designated bathing water, so the Environment Agency gives no bathing advice for it.';
}
// Access at the spot (access.py: a desk check of the authority's guidance, for the spots from OpenStreetMap):
// what it found, in its own words, and when. A plan's row gives the status in a few words (ACCESS_WORDS,
// index.html's planWhy). A spot without a check says so.
const ACCESS_WORDS = { restricted_guidance: 'Swimming here is restricted: check the signs.', unconfirmed: 'Permission to swim at this point is not confirmed.' };
function compareAccess(s) {
  const a = s.access;
  if (!a) return 'No access information.';
  return htmlText(a.text || ACCESS_WORDS[a.status] || 'Not known whether swimming is allowed at this point.') + ' '
    + htmlText(a.checked_at ? `Desk check ${a.checked_at}; current signs not inspected.` : 'Not known when it was checked.')
    + (/^https:\/\//.test(a.url || '') ? ` <a href="${htmlText(a.url)}">Authority guidance</a>.` : '');
}
// The rows under the five days, as [label, HTML], for one spot; iso is the day picked, whose E. coli
// model limits the last row gives.
function compareRows(s, iso, generatedAt = null, now = Date.now()) {
  const f = Object.fromEntries(evidenceRows(s, iso, generatedAt, now)), t = k => htmlText(f[k]);
  return [['Right now', compareNow(s, generatedAt)], ['Environment Agency rating', t('Environment Agency rating')],
    ["Today's EA advice", compareAdvice(s)], ['Water samples', t('Water samples')], ['Algae observation', t('Algae observation')],
    ['Access', compareAccess(s)], ['Local warnings', t('Local warnings')], ['Model limits', t('Model limits')]];
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
