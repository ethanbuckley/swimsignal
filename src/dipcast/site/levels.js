// A spot's pollution level and headline from its forecast: the one copy of the rules, used by the
// page (index.html loads this first), by the build for the alerts file (scripts/alerts.js) and so
// by the alerts themselves, which must never disagree with the page.
//
// A plain script, not a module: in the page its names are globals the page's own script uses,
// and in Node the last lines export them.

// The forecast's own date: the build's date, not the phone's, so "today" is the day the forecast
// was issued for. Node calls setToday; the page sets it from spots.json, and to the phone's date
// between midnight and the next build (readerDay).
let serverToday = null;
const setToday = iso => { serverToday = iso; };

const ORDER = {low:0, moderate:1, high:2, 'very high':3};
const NOT_COVERED = 'not covered', NO_FORECAST = 'no forecast', NO_OVERFLOWS = 'no overflows';
// An isolated lake: the river network links no monitored overflow to it. A flooded quarry or gravel pit
// with no river in, or a tarn whose becks the network does not draw. The key stays as it was: the
// alerts, the journal and the push Worker store it; the words are COVER's.
const NO_RIVER = 'no river connection';
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
// The reader's day. Builds come up to 7.7 h apart, so with the build's date as "today" everywhere,
// between midnight and the next build the page would call yesterday "Today". While the forecast is no
// more than `freshMin` minutes old (the page's stale notice comes after that) the page's day is the
// device's, if later; fromDay then moves the rows before it out of each spot's five days. The alerts,
// the organisers' record and the other pages keep the build's day (setToday with the build's date).
function readerDay(generatedAt, nowMs, freshMin) {
  const built = String(generatedAt).slice(0, 10), mine = localISO(new Date(nowMs));
  return mine > built && nowMs - Date.parse(generatedAt) <= freshMin * 6e4 ? mine : built;
}
// A spot's forecast from the day `iso`, `built` being the build's date: the rows before it move to `past`
// (a spot's page greys the last as "Yesterday"), and each overflow's chances of a spill, one a day from
// the build's date (p_spill_days), lose as many, so "today" in its list is today's. Changes the spot in
// place, and only once: a spot's own file, merged in later, brings its overflows back, and they are moved then.
function fromDay(s, iso, built) {
  const n = Math.round((Date.parse(iso + 'T12:00:00') - Date.parse(built + 'T12:00:00')) / 864e5);
  if (!(n > 0)) return s;
  const days = s.days || [], k = days.filter(x => x.date < iso).length;
  if (k) { s.past = days.slice(0, k); s.days = days.slice(k); }
  for (const c of s.contributors || []) {
    if (!Array.isArray(c.p_spill_days) || c.days_from === iso) continue;
    c.p_spill_days = c.p_spill_days.slice(n); c.days_from = iso;
    c.p_spill_today = c.p_spill_days[0] ?? null; c.p_spill_tomorrow = c.p_spill_days[1] ?? null;
  }
  return s;
}
// ------------------------------------------------------------------------------ risk
// A day's level is the worse of two forecasts and one record, because sewage from overflows is
// only part of what makes river water dirty: from spills alone, every Thames spot would read "low".
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
//  - The EA's latest lab sample at a bathing water, from the same visit, if under 14 days old and over
//    900 E. coli per 100 ml: the day is at least moderate (sampleLevel, below).
//  - Today only: right now's spills (the live status). The days come from the rain model alone
//    (forecast.py), so a day can read moderate while an overflow upstream is discharging now. Today is
//    at least right now.
// Where there is no daily forecast (nothing monitored upstream, or an isolated lake) a rating, an algae
// check or a sample sets the level only where it raises it: sufficient moderate, poor high, algae
// moderate or high, a sample moderate. Otherwise the level is a plain one of its own: "No monitored
// overflow found upstream", the same words whether the trace found none within its 60 km or the
// river network draws nothing into the lake (an isolated lake; the spot's page says which). The words
// claim no more than that: not "no risk", and not "no river connection", which is false at a fell tarn
// with becks in and out that the river network does not draw (Loughrigg Tarn). Nor "low", whatever the
// rating: that is the word for a forecast that had looked and found nothing.
// Not included: the EA's short-term advice against bathing after an incident (Frensham Great Pond's
// harmful-algae warning since 19 Jun 2026, say). Its service refuses the build's machines (HTTP 403
// in every build since 28 Sep 2026) and sends no access-control-allow-origin, so the page cannot read
// it either (checked again 11 Oct 2026, for the API and for the EA's widget). "Today's EA advice"
// (eatoday.js) loads the EA's own panel in a frame the page cannot read. So at every designated
// bathing water the answer says the advice could not be checked (eaUnchecked, below), rather than
// leave "Low risk" and "Usual care" to stand for it.
// The cut-offs between the four levels, as fractions: the spill exposure's (transport.risk_label,
// whose labels arrive in spots.json) and the E. coli estimate's. The page draws its scales from these.
const SPILL_CUTS = [0.15, 0.40, 0.70], ECOLI_CUTS = [0.10, 0.25, 0.50];
// A risk's level from the score shown, Math.round(100 x risk), as transport.risk_label has it: 0.149 shows
// as 15, so it is moderate, not low.
const spillLevel = v => ['low', 'moderate', 'high', 'very high'][SPILL_CUTS.filter(c => Math.round(v * 100) >= Math.round(c * 100)).length];
const shownRisk = v => Math.round(v * 100) / 100;   // the risk as shown, for a bar to agree with the word beside it
const ECOLI_BANDS = [...ECOLI_CUTS, Infinity].map((t, i) => [t, ['low', 'moderate', 'high', 'very high'][i]]);
const CLASS_LEVEL = { excellent: 'low', good: 'low', sufficient: 'moderate', poor: 'high' };
const rank = l => ORDER[l] ?? -1;
const higher = (a, b) => rank(b) > rank(a) ? b : a;
const nil = v => v === null || v === undefined;
const overflows = s => (s.upstream_summary || {}).overflows || 0;
// The overflows upstream that carry no weight here (forecast.py, weighted_here): a reach that
// shows as 0%. `overflows` and every count leave them out; this says once that they are there.
const tooFar = s => (s.upstream_summary || {}).too_far || 0;
const allUpstream = s => overflows(s) + tooFar(s);
const tooFarSaid = s => { const n = tooFar(s), o = (s.upstream_summary || {}).too_far_overflow;
  return !n ? '' : n > 1 ? `${n} more overflows are upstream, but their model weight here is too small to count.`
    : `${o && o.site_name ? overflowNames(o).plain : 'One more overflow'} is upstream too, but its model weight here is too small to count.`; };
// An overflow's weight in words, the one definition the pages give (the overflows tile, the organisers' table): a
// modelled relative contribution weight from the transport assumptions (transport.py: travel time and die-off, and
// dilution), not a measured concentration and not a calibrated chance. Until 30 Oct 2026 the pages called it "reach",
// "the share of a spill's bacteria the model expects to arrive" or "the chance a spill there affects the spot".
const WEIGHT_SAID = 'Weight: a modelled relative contribution weight, from 0 to 1 and shown as a percentage, for how much a spill there counts here. It comes from the model\'s assumptions on travel time and die-off on the way, and dilution by the river. It is neither a measured bacterial concentration nor a calibrated chance of contamination.';
const classOf = s => s.classification && s.classification.class ? String(s.classification.class).toLowerCase() : null;
const advisedAgainst = s => classOf(s) === 'poor';
const daily = s => !s.error && overflows(s) > 0;   // a forecast that changes from day to day
const isolated = s => String(s.error || '').startsWith('An isolated lake');   // forecast.py's words for it
const ecoliTested = s => daily(s) && (s.location || {}).mode !== 'lake';
// The figure's band, for its own row and cell, in any month.
const ecoliBand = (s, x) => ecoliTested(s) && x && !nil(x.p_ecoli_gt900) ? ECOLI_BANDS.find(([t]) => x.p_ecoli_gt900 < t)[1] : null;
// Untested from October to April (the build marks each day): not counted in the level, and its figure
// stays out of the main view (ECOLI_OFF, below).
const ecoliUntested = x => !!x && x.in_validated_season === false;
const ecoliLevel = (s, x) => ecoliUntested(x) ? null : ecoliBand(s, x);
// What stands in for the figure out of season. "Moderate risk" over a tile whose figure is "56%",
// labelled "Untested in October", reads as two answers to reconcile: a precise number gains authority
// whatever the words beside it say. So from October to April no percentage is in a tile's figure, a
// row's value, a summary line, the shared picture or the decision record: the tile says ECOLI_OFF, is
// named experimental, and keeps the daily figures under a fold of that name (ECOLI_FOLD). The
// day-by-day numbers, a folded table, keep them marked †. The band is out of the main view too ("Very
// high risk" under a "Low risk" answer read as a contradiction).
const ECOLI_OFF = 'Out of season';
const ECOLI_EXPERIMENTAL = 'Experimental E. coli estimate', ECOLI_FOLD = 'Experimental estimate';
const ECOLI_OFF_SAID = 'Out of season. The E. coli estimate is tested only for May to September, when the Environment Agency takes samples. From October to April it is experimental, so it is not given here and does not set the level.';
const algaeAge = a => (Date.parse(today()) - Date.parse(a.date)) / 864e5;
const algaeLevel = s => { const a = s.algae; if (!a || nil(a.level) || algaeAge(a) > 14) return null;
  return a.level >= 3 ? 'high' : a.level >= 2 ? 'moderate' : null; };
// A lab sample over the line, recent enough to count. Without it a page could show "3,800 E. coli per
// 100 ml" under "Low risk for the next five days", with nothing joining the two. The rule:
//  - The line is 900 per 100 ml, the one the E. coli estimate and the page's sample row already use (the
//    inland "sufficient" standard's, Bathing Water Regulations 2013, schedule 5). One sample sets no
//    rating, but a count over it is a measured failure of the water the level is about.
//  - It counts for 14 days from the day it was taken, as the algae check from the same EA visit does:
//    the EA samples about weekly in season, so that is the latest sample and one missed visit. Older,
//    one sample says little about the water now.
//  - It makes every day at least moderate, the level whose line says to take more care, as algae
//    "some at intervals" does. Not high: a single count, days old, is not a forecast that the water is
//    poor now. The headline names it ("a recent EA sample over 900 E. coli").
// A count given as a limit (">10000", "<10") counts only where the limit settles it.
const SAMPLE_LINE = 900, SAMPLE_DAYS = 14;
const sampleOver = x => { if (!x || !x.taken_at || nil(x.ecoli) || x.ecoli === '' || !Number.isFinite(Number(x.ecoli))) return false;
  const n = Number(x.ecoli); return x.qualifier === '<' ? false : x.qualifier === '>' ? n >= SAMPLE_LINE : n > SAMPLE_LINE; };
const sampleAge = x => (Date.parse(today()) - Date.parse(String(x.taken_at).slice(0, 10))) / 864e5;
const sampleLevel = s => sampleOver(s.lab_sample) && sampleAge(s.lab_sample) <= SAMPLE_DAYS ? 'moderate' : null;
// Where the level does not change from day to day: the highest of the rating, the algae and the sample,
// and which set it ('rating', 'sample' or 'algae'). A tie goes to the rating, then the sample.
const standingLevel = s => { const c = CLASS_LEVEL[classOf(s)] ?? null, a = algaeLevel(s), m = sampleLevel(s), l = [c, a, m].reduce(higher, null);
  return { level: l, by: !l ? null : rank(c) >= rank(l) ? 'rating' : rank(m) >= rank(l) ? 'sample' : 'algae' }; };
// Right now not known: overflows upstream, none of them reporting live and none discharging, the Right
// now tile's "Unknown" (index.html, nowTile). forecast.py sends right now as low, risk 0, even from no
// readings at all: Dŵr Cymru's overflows have no live feed SwimSignal reads, and a company's feed can
// be over six hours old. Taken as a real low, that would put "Low risk on every day with a forecast"
// beside a tile saying no overflow there reported. So a low right now with no reading behind it is no
// level at all: it sets nothing, and the headline does not claim it.
// A raised right now (spills that stopped lately, from the records the feeds last gave) still counts.
// What is watched is judged by weight where the build gives it (forecast.live_counts): right now is
// known when the overflows reporting live carry at least half the weight upstream. Sandy Lane, Chester,
// with its Caldy Brook overflows joined (12 Oct 2026): 1 of its 13 reports live, with 0.3% of the
// weight. On the live data of that day the rule changed Sandy Lane alone: the next lowest share is the
// Medway at Tonbridge, 66%, then 92%.
const NOW_WATCHED_SHARE = 0.5;
const nowWatched = s => { const n = s.now || {}, total = overflows(s), mon = Math.min(total, n.monitored_upstream ?? total);
  if (!mon) return 0;
  const w = Number(n.upstream_weight), m = Number(n.monitored_weight);
  return w > 0 && Number.isFinite(m) ? Math.min(1, Math.max(0, m) / w) : 1; };
const nowUnknown = s => { if (!daily(s) || !s.now || rank(s.now.label) >= 1 || (s.now.discharging_upstream || 0)) return false;
  return nowWatched(s) < NOW_WATCHED_SHARE; };
// Why right now is not known, after "Low risk forecast": none reports, or the ones that do matter little here.
const nowUnknownWhy = s => !Math.min(overflows(s), (s.now || {}).monitored_upstream ?? overflows(s))
  ? 'no overflow upstream reports live' : 'the overflows that matter most here do not report live';
// The live status behind a spot, in counts, said wherever a level is shown (review of PR #463, 30 Oct 2026:
// at the Wye at Symonds Yat, "Low risk from sewage spills" over five low days read as an observation, though
// none of its 14 overflows reports live). The statuses are what the companies' feeds said at the last poll
// before the update, counted as forecast.live_counts counts them (monitored_upstream: discharging, a spill
// lately, or a current "not discharging"), after the page has aged stale feeds (index.html, ageReadings).
// kind: 'none' (no overflow upstream gives a current status), 'partial' or 'full'; null where there is no daily
// forecast or the update gives no count. The modelled forecast is left as it is: a missing status never makes a
// level, and a valid forecast is never taken away (nowUnknown already keeps a low right now from setting one).
const LIVE_NONE = 'Live sewage spill status unavailable';
const liveCover = s => { const n = s.now || {}, total = overflows(s);
  if (!daily(s) || !total || !Number.isFinite(n.monitored_upstream)) return null;
  const mon = Math.min(total, Math.max(0, n.monitored_upstream));
  return { mon, total, kind: !mon ? 'none' : mon < total ? 'partial' : 'full' }; };
// "Live sewage spill status unavailable", "Live status from 1 of 13 overflows upstream", "Live status from all 16
// overflows upstream". '' where liveCover is null.
const liveHead = s => { const c = liveCover(s); if (!c) return '';
  return c.kind === 'none' ? LIVE_NONE : c.kind === 'partial' ? `Live status from ${c.mon} of ${c.total} overflows upstream`
    : c.total === 1 ? 'Live status from the overflow upstream' : `Live status from all ${c.total} overflows upstream`; };
// The same with what those statuses said, as at the last poll, and the ones with none said as unknown, never
// as dry: the line at the top of a spot's answer, before the level, on today's view.
const liveLine = s => { const c = liveCover(s); if (!c) return '';
  const k = Math.min(c.mon, (s.now || {}).discharging_upstream || 0), rest = c.total - c.mon;
  if (c.kind === 'none') return `${LIVE_NONE}: ${c.total === 1 ? 'the overflow upstream does not report live' : `none of the ${c.total} overflows upstream reports live`}, so whether any is spilling is not known`;
  const said = c.total === 1 ? (k ? 'spilling at the last poll' : 'not spilling at the last poll') : `${k ? `${k} spilling` : 'none spilling'} at the last poll`;
  return `${liveHead(s)}: ${said}${rest ? `; ${rest} ${rest === 1 ? 'does' : 'do'} not report, so could be spilling unseen` : ''}`; };
// The live status over a level on today's view, for the spot's answer (index.html, answerParts): `live`, the line at the top
// of the answer, in counts; `blind`, no overflow upstream gives a current status, when the answer leads with
// "Live sewage spill status unavailable" and labels the level as the modelled forecast; `cardLive`, the
// short form a saved card gives above its level where right now is not known (nowUnknown) or nothing reports.
const MODELLED_FROM = "From the rain forecast and each overflow's past spills, not from live readings";
const liveParts = (d, isToday) => { const c = isToday ? liveCover(d) : null;
  return c ? { live: liveLine(d), blind: c.kind === 'none', cardLive: c.kind === 'none' || nowUnknown(d) ? liveHead(d) : '' } : { live: '', blind: false, cardLive: '' }; };
// Right now's level from the live status, where it has one.
const nowSpill = s => daily(s) && s.now && !nowUnknown(s) && ORDER[s.now.label] !== undefined ? s.now.label : null;
// One day, or right now (isNow, from the live overflow status): the level and what set it, 'spill',
// 'water', 'record', 'sample' or 'algae'. The rating is named unless a forecast is worse; then a tie
// goes to the spills, whose reasons the page can give, then the water, the sample and the algae.
// Today is at least right now (see the list above): where right now raises it, `now` is true, and the
// reason says "right now".
function risk(s, x, isNow = false) {
  let sp = !daily(s) || !x ? null : isNow ? (ORDER[x.label] !== undefined && !nowUnknown(s) ? x.label : null) : hasData(x) ? x.label : null;
  const lift = !isNow && !!x && x.date === today() && rank(nowSpill(s)) >= 1 && rank(nowSpill(s)) > rank(sp);   // a low right now raises nothing
  if (lift) sp = nowSpill(s);
  const wq = isNow ? null : ecoliLevel(s, x), rec = advisedAgainst(s) ? 'high' : null, alg = algaeLevel(s), smp = sampleLevel(s);
  const lv = [sp, wq, rec, alg, smp].reduce(higher, null);
  if (lv === null) return { level: null, by: null };
  const by = rec && rank(rec) >= rank(lv) ? 'record' : lv === sp ? 'spill' : lv === wq ? 'water' : lv === smp ? 'sample' : 'algae';
  return lift && by === 'spill' ? { level: lv, by, now: true } : { level: lv, by };
}
// Right now, today and tomorrow: what the headline and the map colour go by, and the worst of them.
const near = s => [[risk(s, s.now, true), 'right now'], [risk(s, s.days[0]), 'today'], [risk(s, s.days[1]), 'tomorrow']];
const worstNear = s => near(s).reduce((a, b) => rank(b[0].level) > rank(a[0].level) ? b : a);
const worst = s => worstNear(s)[0].level;
const level = s => {
  if (s.error && String(s.error).startsWith('forecast failed')) return NO_FORECAST;
  if (!daily(s)) { const raised = standingLevel(s).level;
    if (s.error && !isolated(s)) return raised || NOT_COVERED;   // no water within reach: not covered
    return rank(raised) >= 1 ? raised : isolated(s) ? NO_RIVER : NO_OVERFLOWS; }
  return worst(s) ?? NO_FORECAST;
};
// A later day (2 to 4 days ahead) worse than now, today and tomorrow: [its risk, the day]; the worst
// of them, the first where two are as bad.
const laterDay = s => { if (!daily(s)) return null; const w = rank(worst(s));
  const x = (s.days || []).slice(2, 5).map(d => [risk(s, d), d]).filter(([r]) => r.level).reduce((a, b) => !a || rank(b[0].level) > rank(a[0].level) ? b : a, null);
  return x && rank(x[0].level) > w ? x : null; };
// That day in the headline's words, "Very high risk on Tuesday", or ''.
const laterWords = s => { const x = laterDay(s); return x ? `${cap(x[0].level)} risk ${dayWord(x[1].date)}` : ''; };
// What set a level, in a forecast's words: "high E. coli likely". "Very poor water quality" read as
// the result of a test, which nothing here is. Today raised by right now's spills says so.
const because = r => r.by === 'spill' ? (r.now ? 'sewage spills right now' : 'sewage spills')
  : r.by === 'water' ? (r.level === 'moderate' ? 'E.\u00a0coli may be raised' : r.level === 'very high' ? 'high E.\u00a0coli likely' : 'raised E.\u00a0coli likely')
  : r.by === 'sample' ? 'a recent EA sample over 900 E.\u00a0coli'
  : r.by === 'algae' ? 'algae at the last check' : 'rated poor';
// What set right now's level. A spill counts until 48 h after its water has passed the spot, so right
// now can be raised with no overflow upstream discharging: then the spills are recent ones, not running
// now, as a tile saying "0 of 60 discharging" beside them shows. Where the count is not known,
// because()'s words.
const nowBecause = (s, r) => r.by === 'spill' && (s.now || {}).discharging_upstream === 0 ? 'recent sewage spills' : because(r);
// What set a day's level: right now's words where right now raised today.
const dayBecause = (s, r) => r.now ? nowBecause(s, r) : because(r);
// A water rated poor, on a day (iso). Advice against bathing applies in the bathing season, 15 May to
// 30 September (Bathing Water Regulations 2013); the rating keeps the level at least high on every day
// of the year all the same. So the advice is named only in season, and out of season the words say
// why the level is high and when the advice applies: "advice against bathing" beside a sentence
// saying it applies only in summer read as a contradiction in October. One wording for the
// headline's reason, the rating's sentence, the days' sentence and the alerts.
// The reason follows the level and its noun ("High risk: rated poor"), never replaces them, so every
// row on the list at a water rated poor says "High risk".
const inBathingSeason = iso => { const md = String(iso).slice(5, 10); return md >= '05-15' && md <= '09-30'; };
const poorReason = iso => inBathingSeason(iso) ? 'rated poor, advice against bathing' : 'rated poor';
const poorAdvice = iso => inBathingSeason(iso)
  ? 'Advice against bathing applies here while the rating is poor, and should be shown on signs at the water.'
  : 'The rating is poor, so the spot stays at high risk or worse; advice against bathing applies 15 May to 30 September.';   // the council's, not the EA's (above)
// The words for a spot without a risk level, the same wherever it is described (the headline, so the
// list row, the map's tooltip, the saved card and the alerts; the page's spills row; the comparison).
// The two plain levels share their words: what is true at both is that no monitored overflow was found
// upstream, and neither says there is no risk. Where an isolated lake's own reason adds something,
// ISOLATED_WHY says it (the spot's spills row, the organisers' page).
const FOUND_NONE = 'No monitored overflow found upstream';
const COVER = { [NO_FORECAST]: 'No forecast in this update', [NOT_COVERED]: 'Not covered by the forecast',
  [NO_OVERFLOWS]: FOUND_NONE, [NO_RIVER]: FOUND_NONE };
const ISOLATED_WHY = 'The river network draws no river or beck into this lake, so no monitored overflow can be traced to it. Small becks it does not draw are not checked.';
// The two plain levels, where the model has nothing to forecast: under the level, one line kept in view.
const plainLevel = l => l === NO_OVERFLOWS || l === NO_RIVER;
const OTHER_RISKS = 'Other risks apply: algae, wildlife, runoff and bathers. Check the signs at the water.';
// The Environment Agency's advice for today, at a designated bathing water. The EA's own panel can say
// "Bathing is not advised today due to pollution from harmful algae" (Frensham Great Pond, 11 Oct 2026)
// on a day the forecast reads "Low risk for the next five days" and "Usual care". Neither the build nor
// the page can read that advice (the list above), so where the EA gives it, the answer says it could
// not be checked and where to look, beside the level and its action: on the spot's page, the embed and
// the shared picture. A clicked point off the list is not checked against the bathing waters.
const eaUnchecked = s => !!s && !s.unlisted && s.source === 'designated' && !!s.classification;
const EA_UNCHECKED = "The Environment Agency's advice for today could not be checked.";
// Overflows in Wales: Dŵr Cymru Welsh Water's overflows in Wales are not in the data (no licence to
// reuse them yet), so at a spot whose traced river runs partly through Wales the
// forecast misses whatever they do. The build measures how much of the river the trace walks (within
// its 60 km) is in Wales (forecast.py, upstream_summary.wales_share; network/nations.py): on 11 Oct
// 2026 Sandy Lane, Chester 73%, Shrewsbury 44%, Hereford 29%, Ludlow 12%; Symonds Yat and Ironbridge
// 0%, their Welsh water being beyond the 60 km. Said near the headline wherever it shows: in full on
// the spot's page and the embed, short in the list, the saved card and the shared picture.
const walesShare = s => { const w = Number(((s || {}).upstream_summary || {}).wales_share); return w > 0 ? Math.min(1, w) : 0; };
const walesPct = s => Math.max(1, Math.round(walesShare(s) * 100));
function walesWords(s, short = false) {
  if (!walesShare(s)) return '';
  if (short) return `Overflows in Wales not counted (${walesPct(s)}% of the river above)`;
  return `Overflows in Wales are not counted: about ${walesPct(s)}% of the river within ${((s.assumptions || {}).max_upstream_km) ?? 60} km above this ${s.unlisted ? 'point' : 'spot'} is in Wales.`;   // a clicked point too (anypoint.js)
}
// What the E. coli estimate is, said wherever it shows on a spot's page (all year, labelled with what
// is true today). check is spots.json's ecoli_check (build_site.ecoli_check): its record on live
// samples, read from the scores in each build, and the test on Welsh river samples
// (docs/WALES-PLAN-2026-10.md). x is the day shown. Sentences, in order: what the level and the
// estimate each count, so that "Low risk" and "Usual care" over a high estimate do not read as a
// contradiction; its tested season; how it has done on live samples; and, where the river runs from
// Wales, the Welsh test.
const pctShare = p => `${(p * 100).toFixed(p < 0.095 ? 1 : 0)}%`;
function ecoliNotes(s, check, x) {
  const off = ecoliUntested(x), out = [off
    ? 'The level above counts sewage spills. This estimate counts E. coli from any source, but it is tested only for May to September, so it is not part of the level now.'
    : 'This estimate counts E. coli from any source, and is part of the level above from May to September, the only months it is tested for.'];
  const live = (check || {}).live, w = (check || {}).wales;
  if (live && live.n_samples) out.push(live.skill
    ? `On the ${live.n_samples} Environment Agency samples since the forecast began, it did better than chance at picking out the ones over 900.`
    : `It has not yet shown skill on live samples: on the ${live.n_samples} Environment Agency samples since the forecast began, it did no better than chance at picking out the ones over 900.`);
  if (w && walesShare(s)) out.push(`A test on ${w.n_samples} Welsh river samples found it far too high: it averaged ${pctShare(w.mean)} where ${pctShare(w.observed)} were over 900.`);
  return out;
}
// What a daily level counts and what it does not, said once on a spot's page, under the answer; a plain
// level says it in its own line, OTHER_RISKS. Without it "Low risk" reads as "the water is fine". Rain
// washes in runoff from grazing land and roads whatever the overflows do, and at a lake the wind
// decides whether an overflow's water reaches the shore. The forecast takes in neither: lake
// water drifts at one fixed speed (config.LAKE_VELOCITY_MS). On rivers from May to September the E. coli
// estimate does count the other sources, as an average from the rain at the spot and the time of year,
// so that day says so. iso is a picked day; without it, today. methods.html#limits has each limit and
// what a swimmer can do instead.
function levelScope(s, iso = null) {
  if (!daily(s)) return '';
  const x = (s.days || []).slice(0, 5).find(d => d.date === (iso || today()));
  const out = ['This forecast counts sewage from the monitored storm overflows upstream, and the rain that makes them spill.',
    // Treated sewage from sewage works, let out every day, is a source of its own (11 Oct 2026: it was missing here).
    ecoliLevel(s, x) ? 'It counts treated sewage from sewage works, runoff, wildlife and other bathers only as an average. That average comes from the rain here and the time of year.'
      : 'It does not count treated sewage from sewage works, runoff from farmland and roads, wildlife or other bathers.'];
  if ((s.location || {}).mode === 'lake') out.push('In a lake, the wind decides where river water goes. The forecast does not use wind.');
  return out.join(' ');
}
// A spot whose forecast could not be made (s.error): failed in this update, an isolated lake, or out of the model's reach.
const coverage = s => COVER[String(s.error).startsWith('forecast failed') ? NO_FORECAST : isolated(s) ? NO_RIVER : NOT_COVERED];
// The gist in a few words, for the list and the top of a spot's page: the worst of now, today and
// tomorrow, when, and what set it; then the worst later day, where it is worse. If now, today and
// tomorrow are all low, the first words name that later day instead.
// [the level and when, what set it, the worse later day or '']; the list joins them, a spot's page puts
// the first two on two lines and the third under them (weekNext).
// A level always says "risk": a bare "Very high today" read as very high what.
// A worse later day is named whatever now, today and tomorrow are: "Moderate risk today" over a very
// high Tuesday would otherwise leave nothing above the five days to say so.
function headParts(s) {
  const l = level(s);
  if (COVER[l]) return [COVER[l], '', ''];
  if (!daily(s)) { const by = standingLevel(s).by;
    return [`${cap(l)} risk`, by === 'algae' ? 'algae at the last check' : by === 'sample' ? because({ by })
      : advisedAgainst(s) ? poorReason(today()) : `rated ${classOf(s)} by the Environment Agency`, '']; }
  if (worstNear(s)[0].by === 'record') return [`${cap(l)} risk`, poorReason(today()), laterWords(s)];
  const [r, when] = worstNear(s);
  // A raised day from the spill forecast where no overflow upstream reports live: modelled, and said so, so
  // "Moderate risk today: sewage spills" is not read as spills seen.
  const blind = (liveCover(s) || {}).kind === 'none' && r.by === 'spill' && !r.now;
  if (rank(r.level) > 0) return [`${cap(r.level)} risk ${when}`, when === 'right now' ? nowBecause(s, r) : because(r) + (blind ? ' (modelled, no live status)' : ''), laterWords(s)];
  const later = laterWords(s);
  // Right now not known (nowUnknown): the live status leads, in counts (liveHead), then the forecast's low,
  // named as a forecast, so a low is never read as a reading.
  if (nowUnknown(s)) return [liveHead(s) || 'Live sewage spill status not known', 'low risk forecast', later];
  if (later) return [`Low risk now · ${later}`, '', ''];
  // Four days between midnight and the next build, when yesterday's has left them (fromDay).
  return [s.days.slice(0, 5).every(hasData) ? `Low risk for the next ${s.days.length === 4 ? 'four' : 'five'} days` : 'Low risk on every day with a forecast', '', ''];
}
// "Moderate risk today: sewage spills · Very high risk on Tuesday".
const headline = s => { const [h, w, later] = headParts(s); return [h, w].filter(Boolean).join(': ') + (later ? ` · ${later}` : ''); };
// The answer's headline names what it covers: a bare "Moderate risk" reads as a verdict on the water,
// beside an E. coli tile that may seem to say something else. Where the sewage spill forecast or right
// now's spills set the level, and at low risk (the forecast looked and found little), the level's noun
// says so: "Moderate risk from sewage spills", the words all one size, and the line under it gives when
// ("Tomorrow"), not the cause again (spillSet). A poor rating, algae at the last check, a lab sample
// and the E. coli estimate are not forecasts of sewage spills: there the headline stays "High risk"
// over its cause. The list, the map's tooltips, Nearby, the comparison and the alerts keep headline(),
// whose raised rows already name the cause after a colon.
const HEAD_SCOPE = 'risk from sewage spills';
// Whether a level was set by the spills: r is a day's or right now's risk (risk()), at a spot with a daily forecast.
const spillSet = (s, r) => daily(s) && !!r && !!r.level && (r.by === 'spill' || rank(r.level) === 0);
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
  if (r.by === 'record') return `${cap(r.level)} risk: ${poorReason(iso)}`;
  return `${cap(r.level)} risk${rank(r.level) > 0 ? ': ' + dayBecause(s, r) : ''}`;
}
// One line on a tile of what the level rests on, saying how the tile's own figure stands to the level
// above: "High risk" over a spills tile at "Moderate risk" and a water tile marked out of season needs
// something to join them up. kind is 'spill', 'water', 'rating', 'algae' or 'now'. iso is a picked day,
// whose rows show that day's
// figures; without it the line is for the answer (right now, today and tomorrow) and the tiles,
// which show today's. Empty where there is nothing to say: no level above (a plain level, a failed
// forecast), no figure, or an E. coli estimate out of season, whose tile already says it is not counted.
function tileLine(s, kind, iso = null) {
  const x = iso ? (s.days || []).slice(0, 5).find(d => d.date === iso) : (s.days || [])[0];
  const c = classOf(s);
  if (level(s) === NO_FORECAST && !daily(s)) return '';   // a failed forecast: nothing is counted
  let L, by, when = 'today', lifted = false;
  if (!daily(s)) { L = ORDER[level(s)] === undefined ? null : level(s);
    by = { algae: 'algae', sample: 'sample' }[standingLevel(s).by] || 'record'; }
  else if (iso) { const r = x ? risk(s, x) : { level: null }; L = r.level; by = r.by; lifted = !!r.now; }
  else { const [r, w] = worstNear(s); L = r.level; by = r.by; when = w; }
  let t = null;
  if (kind === 'rating') {
    if (!c) return '';
    if (daily(s) ? c !== 'poor' : rank(CLASS_LEVEL[c]) < 1)
      return daily(s) ? 'Not counted in the level: only a poor rating is.' : 'Not counted in the level: only a rating of sufficient or poor is.';
    t = CLASS_LEVEL[c];
  } else if (kind === 'algae') {
    const a = s.algae; if (!a || nil(a.level)) return '';
    t = algaeLevel(s);
    if (!t) return algaeAge(a) > 14 ? 'Over two weeks old, so not counted in the level.' : 'Does not raise the level.';
  } else if (kind === 'spill') { t = daily(s) && x && hasData(x) ? x.label : null;
  } else if (kind === 'water') { t = x && !ecoliUntested(x) ? ecoliBand(s, x) : null;
  } else if (kind === 'now') { if (iso || !daily(s)) return ''; t = risk(s, s.now, true).level; }
  if (!L || !t) return '';
  // Right now is named only when it raises the level: at low, the spills tile says it for both.
  const sets = kind === 'now' ? when === 'right now' && by === 'spill' && rank(L) > 0
    : t === L && by === { spill: 'spill', water: 'water', rating: 'record', algae: 'algae' }[kind]
      && !(kind === 'spill' && when === 'right now' && rank(L) > 0);   // set by right now, whose tile says so
  if (sets) return 'This sets the level above.';
  if (kind === 'now') return '';
  if (t === L) return `On its own: ${t} risk too.`;
  if (rank(t) > rank(L)) return '';
  // What raises the level above the tile's own; on a picked today, right now's spills where they do.
  const day = when === 'today' ? 'The' : `${cap(when)}'s`, recent = nowBecause(s, { by }).startsWith('recent');
  const raiser = by === 'record' ? `The ${c} rating raises the level to ${L} risk.`
    : by === 'algae' ? `Algae at the last check raise the level to ${L} risk.`
    : by === 'sample' ? `A recent EA sample over 900 E. coli raises the level to ${L} risk.`
    : by === 'water' ? `${day} E. coli estimate raises the level to ${L} risk.`
    : lifted ? `${recent ? 'Recent spills' : 'Spills right now'} raise today's level to ${L} risk.`
    : when !== 'right now' ? `${day} sewage spill risk raises the level to ${L} risk.`
    : recent ? `Recent spills raise the level to ${L} risk right now.` : `Spills right now raise the level to ${L} risk.`;
  // A spills tile under a level set by spills on another day: the raiser says it all.
  return (kind === 'spill' && by === 'spill' ? '' : `On its own: ${t} risk. `) + raiser;
}
// ------------------------------------------------------------------------------ when it clears
// "When will it clear?": forecast.py's now.clears_at, the time right now's raised level should be back
// to low if no new spill starts (transport.clear_time: the spills running now stop now, and each
// spill's water passes the spot and dies off). Said as a clock time in
// UK time on the Right now tile and in the alerts (scripts/alerts.js writes it as `clears`): "The
// spills upstream should have passed and died off by Saturday 22:47." Only while right now is raised
// (moderate or worse, and known: nowSpill), and never a time already past (an old page, a late alert).
// The page's "where the risk comes from" says the same time as a part of the day, with its reason.
const UK_CLOCK = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'long', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
// "Saturday 22:47", the weekday even when it is today or tomorrow: an alert or a page read after midnight
// would make "tomorrow" wrong (the forecast's today, as in readerDay), and the weekday never is.
function clockWords(iso) {
  const p = Object.fromEntries(UK_CLOCK.formatToParts(new Date(iso)).map(x => [x.type, x.value]));
  return `${p.weekday} ${p.hour}:${p.minute}`;
}
function clearWords(s, nowMs = Date.now()) {
  const n = (s && s.now) || {};
  if (!n.clears_at || rank(nowSpill(s)) < 1 || !(Date.parse(n.clears_at) > nowMs)) return '';
  const k = n.discharging_upstream || 0, one = k + (n.recent_upstream || 0) <= 1;
  const by = `should have passed and died off by ${clockWords(n.clears_at)}`;
  if (!k) return `The spill${one ? '' : 's'} upstream ${by}.`;
  return `If ${k === 1 ? 'the overflow discharging upstream stops' : `the ${k} overflows discharging upstream stop`} now, ${k === 1 && one ? 'its spill' : `the spill${one ? '' : 's'}`} ${by}.`;
}
// ------------------------------------------------------------------------------ how old the rain is
// forecast.py's assumptions.rain_issued_at and rain_age_h: when the oldest rain forecast behind the spot
// was fetched, and how long before the forecast's issue. Open-Meteo is asked every 2 hours; a cell it did
// not send, or one the day's limit of requests left out, is served from the cache up to a day old, and
// the level then rests on old rain. Over RAIN_OLD_H the answer says so under "Issued", in UK time, with
// the day by the forecast's today. Only a failed request blames Open-Meteo (rain_fallback "no answer");
// the daily limit is the site's own. rain_mixed: other cells are newer, so only part of the rain is old.
const RAIN_OLD_H = 6;
const UK_DATE = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' });
const UK_HM = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const UK_WEEKDAY = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'long' });
function rainAgeLine(s) {
  const a = (s && s.assumptions) || {}, t = new Date(a.rain_issued_at);
  if (!a.rain_issued_at || !(a.rain_age_h > RAIN_OLD_H) || Number.isNaN(t.getTime())) return '';
  const iso = UK_DATE.format(t);
  const day = iso === today() ? 'today' : iso === addDays(today(), -1) ? 'yesterday' : `on ${UK_WEEKDAY.format(t)}`;
  const what = `${a.rain_mixed ? 'Part of the rain forecast is' : 'Rain forecast'} from ${UK_HM.format(t)} ${day}`;
  return `${what}: ${a.rain_fallback === 'no answer' ? 'Open-Meteo did not send a newer one' : 'this update had none newer'}.`;
}
// The first day back at low after a raised day in the five days, for the sentence over them: "Back to
// low risk on Saturday." Raised is the day's own level (risk: a day's spills, its E. coli, a rating,
// algae, and today's right now). Empty where no day is raised, or none after the first raised day is low
// (a water rated poor never is).
function backToLow(s) {
  if (!daily(s)) return '';
  const ls = s.days.slice(0, 5).map(x => ({ x, l: hasData(x) ? risk(s, x).level : null }));
  const up = ls.findIndex(o => rank(o.l) >= 1);
  const back = up < 0 ? null : ls.slice(up + 1).find(o => o.l === 'low');
  return back ? `Back to low risk ${dayWord(back.x.date)}.` : '';
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
  if (!daily(s)) { const by = standingLevel(s).by; return actionFor({ level: l, by: by === 'rating' && advisedAgainst(s) ? 'record' : by }); }
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
// today, "Low risk later today", even when a later day happens to share it.
// A later day worse than the answer's level comes first: "Very high risk on Tuesday" under
// "Moderate risk today" matters more than where the level falls.
function weekNext(s) {
  if (advisedAgainst(s)) return 'At least high risk every day' + (laterWords(s) ? `; ${laterWords(s).charAt(0).toLowerCase()}${laterWords(s).slice(1)}` : '');
  if (!daily(s)) return '';
  const ds = s.days.slice(0, 5).map((x, i) => hasData(x) && { x, i, l: risk(s, x).level }).filter(o => o && o.l), l0 = level(s);
  if (!ds.length) return '';
  if (rank(l0) >= 1 && laterWords(s)) return laterWords(s);
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
// The list's answer line ("Saturday: 64 of 105 spots at low risk"): the weekend's better day while the
// five days reach a Saturday or a Sunday, since that is when most people swim, and otherwise the week's
// best day. `n` is every listed spot, as the lede counts them ("forecasts for 105 spots"); a spot with
// no daily level is never counted low, so the line claims only what it counts. Null when no day has a
// level (bestDay). With a day picked (one of `dates`), that day's, so the line under "On Monday" is
// Monday's count. `weekend`: the day was chosen as the weekend's, with no day picked.
function lowAnswerDay(spots, dates, picked = null) {
  const weekend = dates.filter(iso => [0, 6].includes(new Date(iso + 'T12:00:00').getDay()));
  const one = picked && dates.includes(picked);
  const b = bestDay(spots, one ? [picked] : weekend.length ? weekend : dates);
  return b && { ...b, n: spots.length, weekend: !one && weekend.length > 0 };
}
// Under the list's "Today and tomorrow", a weekend day past tomorrow is said to be the weekend's: on the
// phone, 27 Oct 2026, "Saturday: 61 of 105 spots at low risk" under that filter read as a mismatch.
const lowAnswerWords = a => {
  const d = dayName(a.date), ahead = a.weekend && !['today', 'tomorrow'].includes(d);
  return `${ahead ? `This weekend, ${d}` : cap(d)}: ${a.low || 'none'} of ${a.n} spot${a.n === 1 ? '' : 's'} at low risk`;
};
// The line under it, when another of the five days has more spots at low risk: the same form, "Today:
// 43 of 105, the most this week". Without the count, under "Saturday: 19 of 105 spots at low risk",
// which never says it is the weekend's day, the two lines look to disagree.
const mostWords = a => `${cap(dayName(a.date))}: ${a.low} of ${a.n}, the most this week`;

// Saved spots with nothing upstream have no daily level, so a count of levelled spots can be lower
// than the saved total the page states ("your 4 spots", then "2 of your 3 spots"). Say which three.
const yoursLevelled = (d, spots) => d.known < spots.length ? ' with a daily level' : '';
// How the weekend looks, beside the week's best day, while the five days reach a Saturday or a
// Sunday: "Best this weekend: Saturday, 64 spots at low risk." On a Saturday the weekend is today
// and tomorrow. On a Tuesday Saturday is the fifth day and alone, so no "best": "This weekend: 64
// spots at low risk on Saturday." Equal days are said together. Empty on a Sunday, when the weekend is
// today and the list already shows it; without a weekend day that has a level; and when the week's best
// day is itself a weekend day: the best-day sentence names it already, and the line names a day once.
// `yours` counts the saved spots.
function weekendWords(spots, dates, yours = false) {
  const week = bestDay(spots, dates), weekend = iso => [0, 6].includes(new Date(iso + 'T12:00:00').getDay());
  const days = dates.filter(weekend).map(iso => bestDay(spots, [iso])).filter(Boolean);
  if (!week || !days.length || days.some(d => d.date === week.date) || new Date(today() + 'T12:00:00').getDay() === 0) return '';
  const n = d => yours ? `${d.low || 'none'} of your ${d.known} spots${yoursLevelled(d, spots)}` : `${d.low || 'no'} spot${d.low === 1 ? '' : 's'}`;
  const [a, b] = days;
  if (b && a.low !== b.low) { const w = b.low > a.low ? b : a; return `Best this weekend: ${dayName(w.date)}, ${n(w)} at low risk.`; }
  return `This weekend: ${n(a)} at low risk ${dayWord(a.date)}${b ? (a.low ? ' and ' : ' or ') + dayName(b.date) : ''}.`;
}

// ------------------------------------------------------------------------------ overflow names
// Overflow names that arrive in capitals ("LITTLE SALKELD WwTW") in normal case: words of four or more
// capitals, and of three in a name all in capitals ("BEN RHYDDING/STW" is "Ben Rhydding/STW", not "BEN
// Rhydding/STW"). Codes (KEEP_CAPS) and a reference that runs into a number ("DER096") stay as written.
const KEEP_CAPS = new Set(('STW WTW WRC WRW SPS SPST TPS IPS SWPS PS SP PSCSOEO PSCSO CEO SSO SSTO CSO CSOEO SO OV EO FEEO '
  + 'DWF XDWF FFT OOS NWL ESO EMO SWO HLR SCC SDC ICI RAF IOW').split(' '));
const nameCase = s => {
  const t = String(s ?? ''), shouty = !/[a-z]/.test(t.replace(/\b(?:WwTW|Wwtw|STWs|CSOs)\b/g, ''));
  return t.replace(/[A-Za-z']+/g, (w, i) => !/^[A-Z']+$/.test(w) || KEEP_CAPS.has(w) || /[0-9]/.test(t.charAt(i + w.length)) ? w
    : w.length >= 4 || (shouty && w.length === 3) ? w[0] + w.slice(1).toLowerCase() : w);
};
// An overflow's name in plain words, from the company's own: the place, then what the overflow is at.
// "Addingham/NO 1 SPS/Preliminary Treatment-STW/6Xdwf Overflow" is "Addingham sewage works overflow",
// "RIVADALE VIEW/CSO" "Rivadale View storm overflow". Pages show
// the company's name beside it (overflowNames), since that is the name to look it up by.
//  - The place is the first part, before "/", "_" or " - ", with the codes taken out; later parts are
//    added when they say something new: South West Water's town ("59 Barton Drive, Newton Abbot"),
//    Severn Trent's street ("Birmingham, Lionel Street"). Nothing is added that is not in the name.
//  - Codes, best first, because an overflow at a works or a pumping station is named for it:
//    STW, WwTW, WTW, WRC, WRW, "treatment works" => sewage works; SPS, PS, TPS, IPS, SP (Anglian),
//    CEO (Southern), PSCSOEO (South West) and "pumping station" => pumping station; SSO, SSTO =>
//    storm sewage overflow; CSO, SO, OV (Anglian) => storm overflow; EO => emergency overflow. What
//    each code stands for was checked against the asset types in the EA's 2025 annual returns
//    (data/processed/annual_returns.parquet): 331 of 356 CEOs and 234 of 239 SPs are at pumping stations.
//  - Technical tails go: "Preliminary Treatment", "6Xdwf Overflow", "Inlet", reference numbers. A storm
//    tank stays as words, because a works often has a tank overflow and another one, which would
//    otherwise read the same: "storm tank" for "Storm Tank", SSTO or SSO at a works, and Yorkshire's
//    3Xdwf (36 of its 40 are storm tanks; 26 of 29 6Xdwf are inlets). A number beside the code stays
//    at the end: "BOROUGHBRIDGE/NO 2 STW" is "Boroughbridge sewage works overflow 2".
//  - A name with no code, or no place left once the codes are out, is nameCase's: never a guess.
// src/dipcast/overflow_names.py is the same rules in Python, and tests/test_overflow_names.py checks the two
// agree on every name in tests/fixtures/overflow_names.txt.
const plainName = (() => {
  // [words, codes as written, phrases in any case], best first.
  const KINDS = [
    ['sewage works overflow', 'STW|STWs|WwTW|WWTW|Wwtw|WTW|WRC|WRW',
      'stw|(?:sewage |waste ?water |water )?treatment works|sewage (?:disposal )?works|water recycling centre'],
    ['pumping station overflow', 'SPS|SPST|TPS|IPS|SWPS|PS|SP|P\\.STN|PSCSOEO|PSCSO|CEO',
      '(?:sewage |terminal |storm water |surface water )?pumping station'],
    ['storm sewage overflow', 'SSO|SSTO', 'storm sew(?:age|er) overflow'],
    ['storm overflow', 'CSO|CSOs|CSOEO|SO|OV', 'combined sew(?:er|age) overflow|storm overflow'],
    ['emergency overflow', 'EO|FEEO', 'emergency overflow'],
    ['overflow', 'OVERFLOW', 'overflow'],
  ];
  const WORKS = 0, PUMP = 1, SSO = 2, NONE = KINDS.length;
  // A code, with a number just before it ("NO 2 STW", "#2") or after it ("CSO 4", "CSO#2").
  const NUM = '(?:[Nn][Oo]\\.? ?|#)?(\\d+)';
  const coded = (alts, flags) => new RegExp(`(?:(?<!\\S)${NUM} )?\\b(${alts})\\b(?: ?(?:#|[Nn][Oo]\\.? ?)?(\\d+)\\b)?`, flags);
  const CODES = coded(KINDS.map(k => k[1]).join('|'), 'g'), PHRASES = coded(KINDS.map(k => k[2]).join('|'), 'gi');
  const kindOf = code => KINDS.findIndex(k => new RegExp(`^(?:${k[1]})$`).test(code) || new RegExp(`^(?:${k[2]})$`, 'i').test(code));
  const TECH = /\b[4-9] ?x? ?dwf\b(?: overflow)?|\bpreliminary treatment\b|\bsettled storm\b|\bstorm treatment\b|\binlet(?: works)?\b|\bwaste ?water network\b|\bFFT\b/gi;
  const TANK = /\bstorm tanks?\b|\b3 ?x? ?dwf\b(?: overflow)?/gi;
  // The companies' reference numbers: "- 115858", "(Site ID 272GZ)", "(MAC0122)", "DER096", "- NWL name".
  const IDS = /\s*\((?:site id[^)]*|[A-Z]{3} ?\d{2,4}|\d{3,}[A-Z0-9]*|OOS)\)|\s+[-–] \d{4,}$|\s+[-–] NWL name$|\b(?:DER|NTY|LAK) ?\d{2,4}\b/gi;
  const SMALL = new Set(['of', 'the', 'on', 'in', 'and', 'at', 'upon', 'under', 'by', 'for', 'le', 'de', 'to', 'with', 'next']);
  // A part in capitals, in normal case: "STOKE ON TRENT" is "Stoke on Trent"; "A509" stays.
  const titleCase = s => s.split(' ').map((w, i) => /\d/.test(w) ? w : w.toLowerCase().split('-')
    .map((p, j) => (i || j) && SMALL.has(p) ? p : p.replace(/[a-z]/, c => c.toUpperCase())).join('-')).join(' ');
  const EDGE = /^(?:(?:and|at|for|of|to)\b|[&,.)\-–])\s*|\s*(?:\b(?:and|at|for|of|to|sewage)|[&,(\-–])$/i;
  const trimEdges = s => { let t = s.replace(/\(\s*\)/g, ' ').replace(/\s+/g, ' ').replace(/ ,/g, ',').trim(), u;
    while ((u = t.replace(EDGE, '').trim()) !== t) t = u;
    return t; };
  const stem = w => w.toLowerCase().slice(0, 4);
  return raw => {
    const s = String(raw ?? '').replace(/\s+/g, ' ').trim();
    if (!s) return '';
    // A "/" in "O/S" (outside) or "95/97" is not a separator: it is held as "∕" until the end.
    const t = s.replace(IDS, '').replace(/\b([A-Za-z])\/(?=[A-Za-z]\b)|(\d)\/(?=\d)/g, '$1$2∕').trim();
    const shouty = !/[a-z]/.test(t.replace(/\b(?:WwTW|Wwtw|STWs|CSOs)\b/g, ''));
    // The parts, each with the separator before it: "/" stays "/", the others become ", ". A bracket
    // of codes alone, "(CSO)", is a part; one of words and codes, "(Bardsley PS)", is about something
    // else and goes; one of words alone, "(Blackley)", stays in its part.
    const parts = [], sep = /\s*[-–]\s+|\s+[-–]\s*|_|\//g;
    let from = 0, joint = '', m;
    const add = (p, j) => {
      const asides = [];
      const body = p.replace(/\(([^)]*)\)/g, (all, inner) => {
        const codes = new RegExp(CODES.source, 'g'), phrases = new RegExp(PHRASES.source, 'gi');
        if (!codes.test(inner) && !phrases.test(inner)) return all;
        if (!inner.replace(codes, '').replace(phrases, '').replace(/[&,\s]|\band\b/gi, '')) asides.push(inner);
        return ' '; });
      parts.push([body, j], ...asides.map(a => [a, ', ']));
    };
    while ((m = sep.exec(t))) { add(t.slice(from, m.index), joint); joint = m[0].trim() === '/' ? '/' : ', '; from = m.index + m[0].length; }
    add(t.slice(from), joint);
    let best = NONE, tag = null, tank = false, sso = false;
    const places = [];
    for (const [part, j] of parts) {
      const found = [];
      const take = (all, before, code, after) => { found.push([kindOf(code), before || after]); return ' '; };
      // Phrases before codes: "STORM OVERFLOW" in capitals is one phrase, not "STORM" and the code OVERFLOW.
      const rest = trimEdges(part.replace(TECH, ' ').replace(TANK, () => { tank = true; return ' '; })
        .replace(PHRASES, take).replace(CODES, take));
      for (const [k, n] of found) {
        if (k === SSO) sso = true;
        if (k < best) { best = k; tag = n || null; } else if (k === best && n && !tag) tag = n;
      }
      if (rest && !/^(?:[Nn][Oo]\.? ?|#)?\d+[A-Za-z]?$/.test(rest)) places.push([rest, j]);
    }
    if (best === WORKS && sso) tank = true;
    if ((best === NONE && !tank) || !places.length || /^x+$/i.test(places[0][0])) return nameCase(s);
    const cased = p => shouty ? titleCase(p) : nameCase(p);
    let place = cased(places[0][0]);
    for (const [p, j] of places.slice(1)) {
      const mine = place.split(/[^A-Za-z]+/).filter(Boolean), stems = new Set(mine.filter(w => w.length >= 4).map(stem));
      const had = w => w.length >= 4 ? stems.has(stem(w)) : mine.some(x => x.toLowerCase().startsWith(w.toLowerCase()));
      const words = p.split(/[^A-Za-z0-9]+/).filter(Boolean), extra = words.filter(w => !/^\d+$/.test(w) && !had(w));
      // A part that only repeats the place ("IVYBRIDGE STW_SSO_IVYBRIDGE 1") may still number it.
      if (!extra.length) { const n = words.find(w => /^\d+$/.test(w)); if (n && !tag) tag = n; continue; }
      place += j + cased(p);
    }
    if ((place.match(/\(/g) || []).length !== (place.match(/\)/g) || []).length) place = place.replace(/[()]/g, '').replace(/\s+/g, ' ').trim();
    place = place.charAt(0).toUpperCase() + place.slice(1);
    const words = best === NONE ? 'storm tank overflow' : !tank ? KINDS[best][0]
      : best <= PUMP ? KINDS[best][0].replace(/ overflow$/, ' storm tank overflow') : 'storm tank overflow';
    return `${place.replace(/∕/g, '/')} ${words}${tag ? ' ' + tag : ''}`;
  };
})();
// An overflow's two names for a page: the plain one, and the company's (in normal case) where it says
// something more. An overflow with no name is its id, alone.
const overflowNames = c => {
  if (!c.site_name) return { plain: String(c.site_id ?? ''), own: '' };
  const plain = plainName(c.site_name), own = nameCase(String(c.site_name).replace(/\s+/g, ' ').trim());
  return { plain, own: plain === own ? '' : own };
};
// A water company's name as a page writes it. The EA's annual returns spell Dŵr Cymru without its
// circumflex ("Dwr Cymru Welsh Water"), and the data keeps that spelling, which the build matches on;
// a page writes it through companyName, with the circumflex.
const companyName = name => String(name ?? '').replace(/\bDwr Cymru\b/g, 'Dŵr Cymru');
// Where an overflow is from the spot, along the water, in words: "6.0 km upstream". One that drains
// into the same lake is "across the lake": Glebe Road PS, in Bowness, would read "2.6 km upstream" of
// Millerground and "7.0 km upstream" of Waterhead, though Windermere drains south and Bowness is down
// the lake from both. The trace carries lake water at one slow speed whichever way it
// goes (config.LAKE_VELOCITY_MS), so the words say how far, not which way. One placed where its stream
// meets the river by a checked join (data/raw/overflow_joins.csv) says so, and one that joins at the
// spot says it is there to within the map's precision: Culham STW would read "0.0 km upstream" with 100%
// reach at Clifton Hampden, with nothing to say why. Any other under 0.1 km is "at the spot", not
// "0.0 km upstream". Plain text, its spaces before "km" unbroken.
const atSpot = c => (Number(c.distance_km) || 0) + (Number(c.lake_distance_km) || 0) < 0.1;
function overflowWhere(c) {
  const r = Number(c.distance_km) || 0, l = Number(c.lake_distance_km) || 0, k = `${(r + l).toFixed(1)} km`;
  const join = c.position_source === 'join';
  if (atSpot(c)) return join ? "at the spot: its stream joins the river here, to within the map's precision (checked on a map)" : 'at the spot';
  const where = l > 0 && r < 0.05 ? `${k} across the lake` : l > 0 ? `${k} upstream by river and lake` : `${k} upstream`;
  return join ? `${where}, where its stream joins the river (checked on a map)` : where;
}
// How long its water takes to get here, said after overflowWhere's words: ", about 5 hours away", with
// a longer time in its page's own words (`hours`). Under half an hour says so: Rivadale View CSO is
// 0.3 h above Ilkley, which "under an hour" overstates. One at the spot says nothing: its travel is 0.0 h.
const travelSaid = (c, hours) => atSpot(c) ? ''
  : `, ${c.travel_h < 0.5 ? 'under half an hour' : c.travel_h < 1 ? 'under an hour' : hours(c.travel_h)} away`;
// An overflow discharging without a break for longer than this is named as possibly a fault. YWS02298,
// with no name, no receiving water ("#N/A") and no annual return, reported discharging without a break
// from 6 Oct 2026 10:46 UTC to at least 11 Oct and set Greenholme's "Very high risk right now", the
// site's top alarm. A storm overflow spills while its sewer is overloaded; days on end in drying
// weather is more often a stuck sensor. It is not left out of the risk: the page cannot tell which it
// is, so it says both.
const SPILL_LONG_H = 48;
// The start of the spill an overflow is in now, as a time in ms, or null: its latest event has started
// and not ended.
const spillStart = c => { if (!c || c.status !== 1 || !c.latest_event_start) return null;
  const a = Date.parse(c.latest_event_start), b = c.latest_event_end ? Date.parse(c.latest_event_end) : NaN;
  return Number.isNaN(a) || b >= a ? null : a; };
const longSpill = (c, nowMs) => { const a = spillStart(c); return a !== null && (nowMs - a) / 36e5 > SPILL_LONG_H; };
const LONG_SPILL = 'A spill this long is unusual and may be a monitor fault. It still counts in the risk.';

if (typeof module === 'object' && module.exports) {
  module.exports = { nameCase, plainName, overflowNames, ORDER, NOT_COVERED, NO_FORECAST, NO_OVERFLOWS, NO_RIVER, OTHER_RISKS, SPILL_CUTS, ECOLI_CUTS, spillLevel, shownRisk, tooFar, allUpstream, tooFarSaid, WEIGHT_SAID, setToday, today, dayWord, readerDay, fromDay, rank, risk, nowUnknown, nowUnknownWhy, nowWatched, NOW_WATCHED_SHARE, LIVE_NONE, liveCover, liveHead, liveLine, liveParts, MODELLED_FROM, level, dayLevel, headParts, headline, levelScope, nowBecause, dayBecause, dayHeadline, tileLine, weekNext, laterWords, coverage, COVER, FOUND_NONE, ISOLATED_WHY, plainLevel, inBathingSeason, poorReason, poorAdvice, daily, ecoliBand, ecoliLevel, ecoliUntested, bestDay, weekendWords, yoursLevelled, lowAnswerDay, lowAnswerWords, mostWords, clockWords, clearWords, RAIN_OLD_H, rainAgeLine, backToLow,
    ACTION, POOR_ACTION, ALGAE_ACTION, PLAIN_ACTION, actionFor, levelAction, dayAction, HEAD_SCOPE, spillSet, worstNear,
    SAMPLE_LINE, SAMPLE_DAYS, sampleLevel, standingLevel, eaUnchecked, EA_UNCHECKED, walesShare, walesWords, ecoliNotes,
    ECOLI_OFF, ECOLI_EXPERIMENTAL, ECOLI_FOLD, ECOLI_OFF_SAID,
    companyName, atSpot, overflowWhere, travelSaid, SPILL_LONG_H, spillStart, longSpill, LONG_SPILL, isolated };
}
