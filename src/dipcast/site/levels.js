// A spot's pollution level and headline from its forecast: the one copy of the rules, used by the
// page (index.html loads this first), by the build for the alerts file (scripts/alerts.js) and so
// by the alerts themselves, which must never disagree with the page.
//
// A plain script, not a module: in the page its names are globals the page's own script uses,
// and in Node the last lines export them.

// The forecast's own date: the build's date, not the phone's, so "today" is the day the forecast
// was issued for. The page sets it from spots.json; Node calls setToday.
let serverToday = null;
const setToday = iso => { serverToday = iso; };

const ORDER = {low:0, moderate:1, high:2, 'very high':3};
const NOT_COVERED = 'not covered', NO_FORECAST = 'no forecast', NO_OVERFLOWS = 'no overflows';
const NO_RIVER = 'no river connection';   // an isolated lake: no river flows into it in the network
const localISO = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return localISO(d); };
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const hasData = x => x.risk !== null && x.risk !== undefined;
const today = () => serverToday ?? localISO(new Date());
const shortDay = iso => iso === today() ? 'Today' : new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', {weekday:'short'});
// A day in a sentence: "today", "tomorrow", "on Monday"; dayName drops the "on". Headlines name a
// later day in full, as the five days' sentence does: "High risk on Monday", not "on Mon".
const dayWord = iso => iso === today() ? 'today' : iso === addDays(today(), 1) ? 'tomorrow'
  : 'on ' + new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', {weekday:'long'});
const dayName = iso => dayWord(iso).replace(/^on /, '');
// ------------------------------------------------------------------------------ risk
// A day's level is the worse of two forecasts and one record, because sewage from overflows is
// only part of what makes river water dirty: before this, every Thames spot read "low".
//  - Sewage spills: the exposure index's level, where monitored overflows are upstream.
//  - Water quality: the E. coli estimate, the calibrated chance a sample would be over 900 per 100 ml,
//    where it was tested (rivers with overflows upstream). Low under 10%: the minimum inland
//    standard ("sufficient", Bathing Water Regulations 2013, schedule 5) is a 90th percentile at
//    or under 900, so a water can be over 900 about one sample in ten and still pass. Moderate to
//    25%, high to 50%, very high above, when a sample would more likely than not be over. Not
//    tighter: on 29 Sep 2026 the model put Pangbourne and Wallingford on the Thames at 11-15%
//    while none of the 20 samples at each this season had been over 900, so a 10% line for
//    "high" would have called clean water poor.
//    In season only (May to September, `in_validated_season`). The EA takes no samples from
//    October to April, so nothing tests the figure then, and on 1 Oct 2026 it alone put 35 of 89
//    spots on high or very high while the spill forecast read low at 78 of 87: a list that red all
//    winter, from an untested number, would tell a swimmer nothing and cost the site its credibility.
//    Out of season the figure is still shown, in its own row and in the day cells, marked untested
//    (†), but it does not set the level or the headline.
//  - The Environment Agency's rating of a designated bathing water: at "poor", advice against
//    bathing applies while the rating stands, so the spot is at least high on every day, whatever
//    the forecast. The local authority that controls the water issues that advice, not the EA
//    (Bathing Water Regulations 2013, reg 13(1)(b)), so the page names no one; the EA issues it
//    for short-term pollution, which the level does not get (below). 13 of the 38 designated spots were
//    rated poor for 2025; on 29 Sep 2026 all 13 read
//    "low" for today, and 7 of them for today and tomorrow.
//  - The EA sampler's latest look at a bathing water, if under 14 days old: algae "enough to be
//    objectionable" makes the day at least high, "some at intervals" at least moderate. It cannot
//    tell blue-green algae from harmless kinds, so it is a reason to look before going in.
// Where there is no daily forecast (nothing monitored upstream, or no river connection) a rating or an
// algae check sets the level only where it raises it: sufficient moderate, poor high, algae moderate
// or high. Otherwise the level is a plain one of its own, which says what is true there: "No sewage
// risk from monitored overflows" (the trace found none within its 60 km), or, for an isolated lake,
// "No river connection: overflows cannot reach this lake". Before 3 Oct 2026 an excellent or good
// rating made such a spot "low", the same word as a forecast that had looked and found nothing, and
// without a rating the page named only what the forecast lacked, which a swimmer read as no
// information. Not included: the EA's short-term advice against bathing after
// an incident (Frensham Great Pond's algae warning since 19 Jun 2026, say). Its service refuses
// the build's machines and does not answer other sites' pages, so no code here can read it. A
// spot's page links to the EA's page, and its "Today's EA advice" (eatoday.js) loads the EA's own
// panel in a frame the page cannot read, so the panel never sets a level.
// The cut-offs between the four levels, as fractions: the spill exposure's (transport.risk_label,
// whose labels arrive in spots.json) and the E. coli estimate's. The page draws its scales from these.
const SPILL_CUTS = [0.15, 0.40, 0.70], ECOLI_CUTS = [0.10, 0.25, 0.50];
const ECOLI_BANDS = [...ECOLI_CUTS, Infinity].map((t, i) => [t, ['low', 'moderate', 'high', 'very high'][i]]);
const CLASS_LEVEL = { excellent: 'low', good: 'low', sufficient: 'moderate', poor: 'high' };
const rank = l => ORDER[l] ?? -1;
const higher = (a, b) => rank(b) > rank(a) ? b : a;
const nil = v => v === null || v === undefined;
const overflows = s => (s.upstream_summary || {}).overflows || 0;
const classOf = s => s.classification && s.classification.class ? String(s.classification.class).toLowerCase() : null;
const advisedAgainst = s => classOf(s) === 'poor';
const daily = s => !s.error && overflows(s) > 0;   // a forecast that changes from day to day
const isolated = s => String(s.error || '').startsWith('An isolated lake');   // forecast.py's words for it
const ecoliTested = s => daily(s) && (s.location || {}).mode !== 'lake';
// The figure's band, for its own row and cell, in any month.
const ecoliBand = (s, x) => ecoliTested(s) && x && !nil(x.p_ecoli_gt900) ? ECOLI_BANDS.find(([t]) => x.p_ecoli_gt900 < t)[1] : null;
// Untested from October to April (the build marks each day): shown, but not counted in the level.
const ecoliUntested = x => !!x && x.in_validated_season === false;
const ecoliLevel = (s, x) => ecoliUntested(x) ? null : ecoliBand(s, x);
const algaeAge = a => (Date.parse(today()) - Date.parse(a.date)) / 864e5;
const algaeLevel = s => { const a = s.algae; if (!a || nil(a.level) || algaeAge(a) > 14) return null;
  return a.level >= 3 ? 'high' : a.level >= 2 ? 'moderate' : null; };
// One day, or right now (isNow, from the live overflow status): the level and what set it, 'spill',
// 'water', 'record' or 'algae'. The rating is named unless a forecast is worse; then a tie goes to
// the spills, whose reasons the page can give, then the water, then the algae.
function risk(s, x, isNow = false) {
  const sp = !daily(s) || !x ? null : isNow ? (ORDER[x.label] !== undefined ? x.label : null) : hasData(x) ? x.label : null;
  const wq = isNow ? null : ecoliLevel(s, x), rec = advisedAgainst(s) ? 'high' : null, alg = algaeLevel(s);
  const lv = [sp, wq, rec, alg].reduce(higher, null);
  if (lv === null) return { level: null, by: null };
  return { level: lv, by: rec && rank(rec) >= rank(lv) ? 'record' : lv === sp ? 'spill' : lv === wq ? 'water' : 'algae' };
}
// Right now, today and tomorrow: what the headline and the map colour go by, and the worst of them.
const near = s => [[risk(s, s.now, true), 'right now'], [risk(s, s.days[0]), 'today'], [risk(s, s.days[1]), 'tomorrow']];
const worstNear = s => near(s).reduce((a, b) => rank(b[0].level) > rank(a[0].level) ? b : a);
const worst = s => worstNear(s)[0].level;
const level = s => {
  if (s.error && String(s.error).startsWith('forecast failed')) return NO_FORECAST;
  if (!daily(s)) { const raised = higher(CLASS_LEVEL[classOf(s)] ?? null, algaeLevel(s));
    if (s.error && !isolated(s)) return raised || NOT_COVERED;   // no water within reach: the old rule
    return rank(raised) >= 1 ? raised : isolated(s) ? NO_RIVER : NO_OVERFLOWS; }
  return worst(s) ?? NO_FORECAST;
};
// A later day (2 to 4 days ahead) worse than now, today and tomorrow: [its risk, the day].
const laterDay = s => { const w = rank(worst(s));
  const x = s.days.slice(2, 5).map(d => [risk(s, d), d]).filter(([r]) => r.level).reduce((a, b) => !a || rank(b[0].level) > rank(a[0].level) ? b : a, null);
  return x && rank(x[0].level) > w ? x : null; };
// What set a level, in a forecast's words: "high E. coli likely". "Very poor water quality" read as
// the result of a test, which nothing here is.
const because = r => r.by === 'spill' ? 'sewage spills'
  : r.by === 'water' ? (r.level === 'moderate' ? 'E.\u00a0coli may be raised' : r.level === 'very high' ? 'high E.\u00a0coli likely' : 'raised E.\u00a0coli likely')
  : r.by === 'algae' ? 'algae at the last check' : 'rated poor';
// What set right now's level. A spill counts until 48 h after its water has passed the spot, so right now
// can be raised with no overflow upstream discharging: then the spills are recent ones, not running now.
// Before, Eden at Armathwaite (4 Oct 2026) read "Moderate risk right now: sewage spills" over a tile
// saying "0 of 60 discharging". Where the count is not known, the words stay as they were.
const nowBecause = (s, r) => r.by === 'spill' && (s.now || {}).discharging_upstream === 0 ? 'recent sewage spills' : because(r);
// A water rated poor, on a day (iso). Advice against bathing applies in the bathing season, 15 May to
// 30 September (Bathing Water Regulations 2013); the rating keeps the level at least high on every day
// of the year all the same. So the advice is named only in season, and out of season the words say
// why the level is high and when the advice applies: "advice against bathing" beside a sentence
// saying it applies only in summer read as a contradiction in October. One wording for the
// headline's reason, the rating's sentence, the days' sentence and the alerts.
const inBathingSeason = iso => { const md = String(iso).slice(5, 10); return md >= '05-15' && md <= '09-30'; };
const poorReason = iso => inBathingSeason(iso) ? 'advice against bathing' : 'advice against bathing from 15 May';
const poorAdvice = iso => inBathingSeason(iso)
  ? 'Advice against bathing applies here while the rating is poor, and should be shown on signs at the water.'
  : 'The rating is poor, so the spot stays at high risk or worse; advice against bathing applies 15 May to 30 September.';   // the council's, not the EA's (above)
// The words for a spot without a risk level, the same wherever it is described (the headline, so the
// list row, the map's tooltip, the saved card and the alerts; the page's spills row; the comparison).
const COVER = { [NO_FORECAST]: 'No forecast in this update', [NOT_COVERED]: 'Not covered by the forecast',
  [NO_OVERFLOWS]: 'No sewage risk from monitored overflows', [NO_RIVER]: 'No river connection: overflows cannot reach this lake' };
// The two plain levels, where the model has nothing to forecast: under the level, one line kept in view.
const plainLevel = l => l === NO_OVERFLOWS || l === NO_RIVER;
const OTHER_RISKS = 'Other risks apply: algae, wildlife, runoff and bathers. Check the signs at the water.';
// A spot whose forecast could not be made (s.error): failed in this update, an isolated lake, or out of the model's reach.
const coverage = s => COVER[String(s.error).startsWith('forecast failed') ? NO_FORECAST : isolated(s) ? NO_RIVER : NOT_COVERED];
// The gist in a few words, for the list and the top of a spot's page: the worst of now, today and
// tomorrow, when, and what set it; or, if those are all low, the first worse day after them.
// [the level and when, what set it]; the list joins them, a spot's page puts them on two lines.
// A level always says "risk": a bare "Very high today" read as very high what.
function headParts(s) {
  const l = level(s);
  if (COVER[l]) return [COVER[l], ''];
  if (!daily(s) && rank(algaeLevel(s)) > rank(CLASS_LEVEL[classOf(s)] ?? null)) return [`${cap(l)} risk`, 'algae at the last check'];
  if (!daily(s) || worstNear(s)[0].by === 'record')
    return advisedAgainst(s) ? ['Rated poor', poorReason(today())] : [`Rated ${classOf(s)} by the Environment Agency`, ''];
  const [r, when] = worstNear(s);
  if (rank(r.level) > 0) return [`${cap(r.level)} risk ${when}`, when === 'right now' ? nowBecause(s, r) : because(r)];
  const x = laterDay(s);
  if (x) return [`Low risk now · ${cap(x[0].level)} risk ${dayWord(x[1].date)}`, ''];
  return [s.days.slice(0, 5).every(hasData) ? 'Low risk for the next five days' : 'Low risk on every day with a forecast', ''];
}
const headline = s => headParts(s).filter(Boolean).join(': ');
// The level on one day (a date in s.days), for the map's day picker and the alerts: where the
// forecast does not change from day to day, the spot's own level, the same on every day.
const dayLevel = (s, iso) => {
  if (!daily(s)) return level(s);
  const x = s.days.slice(0, 5).find(d => d.date === iso);
  return x ? risk(s, x).level ?? NO_FORECAST : NO_FORECAST;
};

// A picked day's headline, the one form for the list, the map's tooltips, Nearby, the comparison and
// the shared picture: "Moderate risk: sewage spills", "Low risk". Standing ratings stay distinct from
// daily predictions.
function dayHeadline(s, iso) {
  if (!daily(s)) return headline(s);
  const x = s.days.slice(0, 5).find(d => d.date === iso), r = x ? risk(s, x) : {level:null};
  if (!r.level) return 'No forecast for this day';
  if (r.by === 'record') return `Rated poor: ${poorReason(iso)}`;
  return `${cap(r.level)} risk${rank(r.level) > 0 ? ': ' + because(r) : ''}`;
}
// ------------------------------------------------------------------------------ what to do
// One line under the level saying what to do, as NSW Beachwatch gives an action with each of its
// forecasts. A level with no action left the swimmer to turn "Moderate risk" into a decision alone.
// The words are SwimSignal's own; each line rests on these, all read on 4 Oct 2026:
//  - NSW Beachwatch, "Is it safe to swim?" (https://www.beachwatch.nsw.gov.au/whatIsBeachwatch/safeToSwim):
//    "Pollution possible": caution, young children, the elderly and people with some health
//    conditions at more risk, consider waiting; "Pollution likely": "Avoid swimming today"; no
//    forecast: look for signs of pollution; inland waters: avoid swimming up to three days after heavy rain.
//  - Swim healthy, Environment Agency and UK Health Security Agency, updated 24 Jun 2019
//    (https://www.gov.uk/government/publications/swim-healthy-leaflet/swim-healthy): children are more
//    likely to swallow water, people with an impaired immune system catch infections more easily,
//    heavy rain washes bacteria from farms, towns and sewage into rivers; avoid higher-risk days;
//    try not to swallow water, cover cuts, wash hands before eating; keep out of algal blooms and
//    scum, since you cannot tell by looking whether they are harmful, and children and pet owners
//    take care with them.
//  - The Environment Agency's Swimfo help (https://environment.data.gov.uk/bwq/profiles/help-understanding-data.html):
//    a water rated poor has a sign advising against bathing, which is not a ban.
//  - Surfers Against Sewage, FAQs on the Safer Seas and Rivers Service
//    (https://www.sas.org.uk/water-quality/sewage-pollution-alerts/): a pollution risk forecast means
//    bathing is not advised; a poor rating means bathing is not advised; a sewage alert stays for 48
//    hours after a discharge stops, the period the water industry's own project proposes.
//  - NHS, Leptospirosis (https://www.nhs.uk/conditions/leptospirosis/): cover cuts and grazes with
//    waterproof plasters before river, canal or lake water.
// The groups named are Beachwatch's and Swim healthy's. Low is not "enjoy your swim", as on Beachwatch:
// nothing here says a spot is safe, and the page's caveat to check the signs stays beside it.
// Very high names its day (a level set by right now, today, tomorrow, or a picked day), since the
// headline's level may be tomorrow's while today is low; the others hold whichever day it is.
const ACTION = {
  low: 'Usual care: cover cuts, try not to swallow water and wash your hands before eating.',
  moderate: 'Take more care: young children, older people and anyone with a weakened immune system may want a lower day or spot.',
  high: 'Better to choose a lower day or spot. If you do swim, try not to swallow any water.',
};
const veryHighAction = when => `Avoid swimming here${when ? ' ' + when : ''}: choose a lower day or spot.`;
// A water rated poor: advice against bathing in season, and still rated poor out of it.
const POOR_ACTION = 'Choose a spot with a better rating if you can.';
// Algae set the level: the bacteria advice would miss the point.
const ALGAE_ACTION = 'Stay out of any scum or bloom, and keep children and dogs away: toxic algae look like harmless ones.';
// No level (a plain level, or no forecast): rain is what there is to go by.
const PLAIN_ACTION = 'After heavy rain, wait a couple of days before swimming if you can.';
// The line for a risk ({level, by}, from risk()) on a day named by when ("today", "on Monday").
const actionFor = (r, when = '') => !r || ORDER[r.level] === undefined ? PLAIN_ACTION
  : r.by === 'record' ? POOR_ACTION : r.by === 'algae' ? ALGAE_ACTION
  : r.level === 'very high' ? veryHighAction(when) : ACTION[r.level];
// The line for the headline's level, by headParts' own steps.
function levelAction(s) {
  const l = level(s);
  if (ORDER[l] === undefined) return PLAIN_ACTION;
  if (!daily(s)) return actionFor({ level: l, by: rank(algaeLevel(s)) > rank(CLASS_LEVEL[classOf(s)] ?? null) ? 'algae' : advisedAgainst(s) ? 'record' : 'rating' });
  const [r, when] = worstNear(s);
  return actionFor(r, when);
}
// The line for a picked day (a date in s.days); where the forecast does not change from day to day, the spot's.
function dayAction(s, iso) {
  if (!daily(s)) return levelAction(s);
  const x = s.days.slice(0, 5).find(d => d.date === iso);
  return actionFor(x ? risk(s, x) : null, dayWord(iso));
}
// Where the five days go from the answer, as Apple's high and low: the day a raised level falls to low
// (or to its lowest), or the later day a low one rises. The search starts after where the level came
// from (worstNear's right now, today or tomorrow), not after the first day with the same level: a level
// set by right now (an overflow discharging) is on none of the days, so the search then starts at
// today, "Low risk later today", even when a later day happens to share it (Greenholme, 4 Oct 2026:
// right now moderate, Thursday moderate, and the line was blank).
function weekNext(s) {
  if (advisedAgainst(s)) return 'At least high risk every day';
  if (!daily(s)) return '';
  const ds = s.days.slice(0, 5).map((x, i) => hasData(x) && { x, i, l: risk(s, x).level }).filter(o => o && o.l), l0 = level(s);
  if (!ds.length) return '';
  if (rank(l0) >= 1) {
    const at = ['right now', 'today', 'tomorrow'].indexOf(worstNear(s)[1]) - 1, after = ds.filter(o => o.i > at);   // -1, from right now: every day
    const to = after.find(o => o.l === 'low') || after.reduce((a, b) => rank(b.l) < rank(a ? a.l : l0) ? b : a, null);
    if (!to) return ds.every(o => o.l === l0) ? `${cap(l0)} risk on all five days` : '';
    const d = to.x.date;
    // Right now is part of today, so today's lower forecast is "later today".
    return `${cap(to.l)} risk ${d === today() ? (at < 0 ? 'later today' : 'today') : d === addDays(today(), 1) ? 'tomorrow' : 'by ' + dayName(d)}`;
  }
  const later = laterDay(s);
  return later ? `${cap(later[0].level)} risk ${dayWord(later[1].date)}` : '';
}

// The day with the most spots at low, among those with a forecast that changes from day to day:
// "lowest pollution risk this week" on the list and the Saved page. Null without such a spot.
// Ties go to the earlier day. A day with no level anywhere (no rain data) is skipped.
function bestDay(spots, dates) {
  const scored = spots.filter(daily);
  let best = null;
  for (const iso of dates) {
    const known = scored.filter(s => ORDER[dayLevel(s, iso)] !== undefined).length;
    if (!known) continue;
    const low = scored.filter(s => dayLevel(s, iso) === 'low').length;
    if (!best || low > best.low) best = { date: iso, low, known };
  }
  return best;
}
// Saved spots with nothing upstream have no daily level, so a count of levelled spots can be lower
// than the saved total the page states ("your 4 spots", then "2 of your 3 spots"). Say which three.
const yoursLevelled = (d, spots) => d.known < spots.length ? ' with a daily level' : '';
// How the weekend looks, beside the week's best day, while the five days reach a Saturday or a
// Sunday: "Best this weekend: Saturday, 64 spots at low risk." On a Saturday the weekend is today
// and tomorrow. On a Tuesday Saturday is the fifth day and alone, so no "best": "This weekend: 64
// spots at low risk on Saturday." Equal days are said together. Empty on a Sunday, when the weekend
// is today and the list already shows it (Ethan, 4 Oct 2026); without a weekend day that has a
// level; and when the week's best day is itself a weekend day: the best-day sentence names it
// already, and the line names a day once. `yours` counts the saved spots.
function weekendWords(spots, dates, yours = false) {
  const week = bestDay(spots, dates), weekend = iso => [0, 6].includes(new Date(iso + 'T12:00:00').getDay());
  const days = dates.filter(weekend).map(iso => bestDay(spots, [iso])).filter(Boolean);
  if (!week || !days.length || days.some(d => d.date === week.date) || new Date(today() + 'T12:00:00').getDay() === 0) return '';
  const n = d => yours ? `${d.low || 'none'} of your ${d.known} spots${yoursLevelled(d, spots)}` : `${d.low || 'no'} spot${d.low === 1 ? '' : 's'}`;
  const [a, b] = days;
  if (b && a.low !== b.low) { const w = b.low > a.low ? b : a; return `Best this weekend: ${dayName(w.date)}, ${n(w)} at low risk.`; }
  return `This weekend: ${n(a)} at low risk ${dayWord(a.date)}${b ? (a.low ? ' and ' : ' or ') + dayName(b.date) : ''}.`;
}

if (typeof module === 'object' && module.exports) {
  module.exports = { ORDER, NOT_COVERED, NO_FORECAST, NO_OVERFLOWS, NO_RIVER, OTHER_RISKS, SPILL_CUTS, ECOLI_CUTS, setToday, today, dayWord, rank, risk,
    level, dayLevel, headParts, headline, nowBecause, dayHeadline, weekNext, coverage, COVER, plainLevel, inBathingSeason, poorReason, poorAdvice, daily, ecoliBand, ecoliLevel, ecoliUntested, bestDay, weekendWords, yoursLevelled,
    ACTION, POOR_ACTION, ALGAE_ACTION, PLAIN_ACTION, actionFor, levelAction, dayAction };
}
