// Your outing, on a plan (the plan/ page): when on the plan's day you mean to swim, the spot, and a backup
// spot, the two side by side for that day with what each level rests on. Drawn from what the page already
// has (spots.json): it asks for nothing more. Kept as the plan is, in the plan's address and its copy in
// this browser (plan.js, readPlan and planHash: when=, spot=, backup=; index.html, PLAN_KEY), so a reload,
// Back and a copied link keep it, and nothing reaches a server. The page calls drawOuting from drawPlan;
// the words and the markup are here, where Node can test them.
//
// The forecast gives one level a day. A time on the day is the swimmer's own plan, not a finer forecast:
// the tile says so, and it says when the time has already passed today.
//
// A plain script, as plan.js: globals in the page, exports in Node.
const outingRules = () => typeof dayLevel === 'function' ? { dayWord, today } : require('./levels.js');
// eatoday.js's compact official-advice line (eaTodayTag, #379), the one every list, card and row uses.
const outingTag = () => typeof eaTodayTag === 'function' ? eaTodayTag : require('./eatoday.js').eaTodayTag;
// spotdate.js: the calendar file and the alerts for a date, as the organisers' page makes and sends them.
const outingDates = () => typeof SpotDate === 'object' ? SpotDate : require('./spotdate.js');
const outDay = iso => outingRules().dayWord(iso).replace(/^on /, '');   // "today", "tomorrow", "Monday" (levels.js, dayName)
const outEsc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

// ------------------------------------------------------------------------------ when
// The parts of a day in local UK/Ireland time [from, to), and the hours offered one by one.
const OUTING_PARTS = { morning: [6, 12], afternoon: [12, 17], evening: [17, 21] };
const OUTING_HOURS = Array.from({ length: 17 }, (_, i) => String(i + 5).padStart(2, '0'));   // 05:00 to 21:00
const outingSpan = when => OUTING_PARTS[when] || (/^\d\d$/.test(when || '') ? [Number(when), Number(when) + 1] : null);
// All currently listed swim spots use UK/Ireland civil time. Read the offset for the date,
// including summer time, rather than the viewer's device time zone. Offered hours are 05:00
// onwards, outside the clock-change gap and repeated hour.
function outingUtc(day, hour) {
  const local = Date.parse(day + 'T00:00:00Z') + hour * 3600000;
  const part = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', timeZoneName: 'shortOffset' })
    .formatToParts(new Date(local)).find(p => p.type === 'timeZoneName').value;
  const match = /^GMT([+-])(\d{1,2})(?::(\d{2}))?$/.exec(part);
  const offset = match ? (match[1] === '-' ? -1 : 1) * (Number(match[2]) * 60 + Number(match[3] || 0)) : 0;
  return local - offset * 60000;
}
// "Saturday morning", "this evening", "tomorrow at 07:00"; the day alone with no time.
function outingWhen(day, when) {
  const d = outDay(day);
  if (!when) return d;
  if (OUTING_PARTS[when]) return d === 'today' ? `this ${when}` : `${d} ${when}`;
  return `${d} at ${when}:00`;
}
// The line on Explore's "Your outing" (index.html, outingResume; plan.js, planOuting): when and what for, in
// the plan's own words, then the backup by name. With an activity other than swimming, the plan's own note
// that the level is the water's, whatever you do on it; and, on the day, the plan's own note when its time has
// passed (outingTimeNote). Plain text: the page escapes it. nowMs: the device's clock.
function outingResumeSaid(o, backupName = null, nowMs = Date.now()) {
  const ing = o.act && o.act !== 'swim' && OUTING_ACT_WORDS[o.act] ? `, ${OUTING_ACT_WORDS[o.act][1]}` : '';
  const when = outingWhen(o.day, o.when).replace(/^./, c => c.toUpperCase()) + ing;
  return [`${when}${backupName ? `, with ${backupName} as a backup` : ''}.`, ...outingTimeNote(o.day, o.when, nowMs).slice(1),
    ...(ing ? ['The level is for the water, the same whatever you do on it.'] : [])];
}
// What the time does and does not mean, as sentences: the level is for the whole day; and on today, a
// time already past. nowMs: the device's clock.
function outingTimeNote(day, when, nowMs = Date.now()) {
  // The daily caveat always, with or without a time picked, so a time never reads as an hourly forecast.
  const span = outingSpan(when);
  const out = [`The forecast gives one level for the whole of ${outDay(day)}; it does not change between morning and evening.`];
  const localDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(nowMs));
  if (span && day === localDay && nowMs >= outingUtc(day, span[1])) out.push('That time has already passed today.');
  return out;
}

// The plan after its day has changed (the day strip, a better day, the next visit): a time was for the day it
// was picked on, so it goes; the spot and the backup stay. lastDay: the day the outing was last shown for
// (null on the page's first draw, which changes nothing).
// A shared outing's stamp (plan.js: sent=, lv=, blv=) goes too: its levels were that day's.
function outingForDay(plan, lastDay) {
  if (!(plan.when || plan.sent) || lastDay === null || lastDay === plan.day) return plan;
  const { when, sent, lv, blv, flv, ...rest } = plan;
  return rest;
}
// After the swimmer changes the outing: a shared stamp no longer says what was sent, and a meeting place was
// at the spot it was picked for. k: the field changed ('when', 'spot', 'backup', 'act', 'meet').
function outingChanged(plan, k) {
  const { sent, lv, blv, flv, ...rest } = plan;
  if (k === 'spot' || !rest.spot) { delete rest.meet; delete rest.finish; }   // a finish is downstream of its own start
  return rest;
}

// ------------------------------------------------------------------------------ what for, and where to meet
// Fixed choices (plan.js, OUTING_ACTS and OUTING_MEETS), said in words here. The level is for the water,
// whatever is done on it (the clubs page says the same), so an activity changes only the words.
const OUTING_ACT_WORDS = { swim: ['Swim', 'swimming'], paddle: ['Paddle', 'paddling'], sup: ['Paddleboard', 'paddleboarding'] };
const OUTING_MEET_WORDS = { parking: 'at the parking', entry: 'where you get in' };
// For a paddle or a board: some waters need a licence and some do not, and SwimSignal does not know which this is.
// Paddle UK's own pages say which bodies' waterways need one and list launches and licences river by river
// (gopaddling.info, read 29 Oct 2026: Canal & River Trust and Environment Agency waterways need one; some Lake
// District lakes do not). docs/SWIM-TOGETHER-2026-10.md, section 5, "Licences".
const OUTING_LICENCE = '<p class="small">Paddling some rivers, canals and lakes in England and Wales needs a licence, including '
  + 'Canal &amp; River Trust and Environment Agency waterways; others need none. SwimSignal does not know which this is: see '
  + '<a href="https://gopaddling.info/blog/tips-and-advice/general-paddling/the-river-licence-explained/" rel="noopener">Paddle UK\'s guide to licences</a> '
  + 'and its <a href="https://gopaddling.info/rivers/" rel="noopener">river pages</a>.</p>';
const outingVerb = act => (OUTING_ACT_WORDS[act] || OUTING_ACT_WORDS.swim)[0];   // the calendar's and the share's "Swim: …"
// The forecast's issue time as a shared link carries it (plan.js, PLAN_SENT): "20261029T1216Z"; null if unreadable.
function outingSent(generatedAt) {
  const t = new Date(generatedAt);
  return Number.isNaN(t.getTime()) ? null : t.toISOString().slice(0, 16).replace(/[-:]/g, '') + 'Z';
}

// ------------------------------------------------------------------------------ which spots
// The spots offered for the outing and its backup, as [[heading, spots]]: your saved spots first, then the
// plan's own (shown, in the page's order) that are not saved, each once. except: an id left out (the
// outing's spot from the backup's choices, and the backup from the spot's). Saved spots no longer listed are skipped.
function outingOptions(shown, savedIds, byId, except = null) {
  const saved = [...(savedIds || [])].map(id => byId.get(id)).filter(s => s && s.id !== except);
  const ids = new Set(saved.map(s => s.id)), plan = shown.filter(s => s.id !== except && !ids.has(s.id));
  return [['Your saved spots', saved], ['In this plan', plan]].filter(([, g]) => g.length);
}
// The plan's spot and backup as spots, and the ids asked for that are no longer listed (a link from an
// older forecast, or a spot taken off the site), so the tile can say so rather than drop them silently.
function outingPair(plan, byId) {
  const missing = [plan.spot, plan.backup].filter(id => id && !byId.has(id));
  return { main: byId.get(plan.spot) || null, backup: plan.backup !== plan.spot ? byId.get(plan.backup) || null : null, missing };
}

// Official advice at the spot (spots.json and spots-lite.json `official`, #379), in eatoday.js's compact
// form, a line of its own under the column's level, never in it: the level is the forecast's alone. The same
// helper as the list, Saved and the plan's rows, so the outing says what they say. '' without advice.
const outingOfficial = s => outingTag()(s, 'p');
const outingBriefOf = () => typeof eaTodayBrief === 'function' ? eaTodayBrief : require('./eatoday.js').eaTodayBrief;
const outingBrief = s => outingBriefOf()(s);

// When the spot and the backup both have an official notice: one line over the columns that says so, naming
// each with its own notice in its reviewed words (eatoday.js, eaTodayBrief), so the pair is not read as the
// levels alone. It says what each notice is, never more: no notice is called a restriction here, since only its
// own words say what it is. A column's `notice` is that brief. '' unless both have one.
function outingBoth(o) {
  if (!o.main || !o.alt || !o.main.notice || !o.alt.notice) return '';
  return '<div class="outing-notices"><p><b>Your spot and your backup both have an official notice.</b> Read each before you go; neither is part of the levels below.</p>'
    + `<ul><li>Your spot, ${outEsc(o.main.name)}: ${outEsc(o.main.notice)}</li><li>Backup, ${outEsc(o.alt.name)}: ${outEsc(o.alt.notice)}</li></ul></div>`;
}

// When neither choice looks good on the day: each chosen spot has an official notice or is at High risk or
// above. Where both have a notice, outingBoth says so instead, naming each notice. On the phone, 27 Oct 2026,
// an outing to an advised pond with a Very high risk backup said nothing of it. A column's `level` is the day's (levels.js, dayLevel) and `advised` its advice. '' otherwise.
const OUTING_POOR = { high: 'High risk', 'very high': 'Very high risk' };
const outingPoor = c => !!c && (!!c.advised || c.level in OUTING_POOR);
function outingNeither(o) {
  if (!o.main || !outingPoor(o.main) || (o.alt && !outingPoor(o.alt)) || outingBoth(o)) return '';
  const why = c => `${outEsc(c.name)} ${c.advised ? 'has an official notice' : `is at ${OUTING_POOR[c.level]}`}`;
  const cols = o.alt ? [o.main, o.alt] : [o.main], day = outDay(o.day);
  return `<p class="outing-poor"><b>${o.alt ? 'Neither spot looks good' : 'Your spot does not look good'} ${day === 'today' || day === 'tomorrow' ? day : `on ${day}`}.</b> `
    + `${cols.map(why).join(', and ')}. Look at the other spots in this plan, or another day.</p>`;
}

// "Share this outing": a link to the plan with this outing in it, for someone going with you. It is the plan
// as it is, except where it starts from, which may be your own location or your home town: the link's plan
// starts from the outing's spot instead, so whoever opens it sees the outing and the spots around it. It is
// stamped with the forecast it was sent from and each spot's level then (stamp: { sent, lv, blv, flv }), so the
// page can tell whoever opens it what has changed since; a stamp that is not whole is left off.
const outingShared = (plan, main, stamp = {}) => {
  const { compare, sent, lv, blv, flv, ...rest } = plan;
  const ok = stamp.sent && stamp.lv && (!rest.backup || stamp.blv) && (!rest.finish || stamp.flv);
  return { ...rest, from: { name: main.name, lat: main.lat, lon: main.lon },
    ...(ok ? { sent: stamp.sent, lv: stamp.lv, ...(rest.backup ? { blv: stamp.blv } : {}), ...(rest.finish ? { flv: stamp.flv } : {}) } : {}) };
};

// ------------------------------------------------------------------------------ how the two are joined
// How the backup's water is joined to the spot's, in the spot page's Nearby words (index.html, joined and
// nearWhy), from the build (src/dipcast/spot_links.py): each spot's `catchment` (spots-lite.json) and the
// spots it is `linked` to (data/spot/<id>.json): "s" at least one monitored overflow counts at both, "d"
// downstream and "u" upstream with none counted at both. The build writes `linked` both ways, so either
// spot's file says it: the backup's, read the other way round, while the spot's is still on its way.
// Same catchment and linked to neither: another branch, said only once one of the two files is in (until
// then a shared overflow cannot be ruled out). A different catchment is known from the lite file alone.
// Null where either has no place on the network (an isolated lake) or the forecast is older than these fields.
const OUTING_FLIP = { s: 's', d: 'u', u: 'd' };
const outingLinksIn = s => !!s.linked || (!s.detail_file || !!s.detail_loaded) && !s.detail_missing;
function outingJoined(m, b) {
  if (!m || !b || !m.catchment || !b.catchment) return null;
  if (m.catchment !== b.catchment) return 'apart';
  const j = (m.linked || {})[b.id] || OUTING_FLIP[(b.linked || {})[m.id]];
  return j || (outingLinksIn(m) || outingLinksIn(b) ? 'branch' : null);
}
// The line over the pair: under it, each column runs on through its access guide, so a line below both would be
// two screens from the names on a phone. As on the Nearby card, a different catchment or branch gets a plain fact, never a
// reassuring word: it has overflows and runoff of its own (runoff alone where none is upstream). "Same river" where both
// are river spots on a river of one name; the forecast's counting is said only where both have overflows upstream.
const outingOver = s => (s.upstream_summary || {}).overflows || 0;
function outingJoin(m, b) {
  const j = outingJoined(m, b);
  if (!j) return '';
  const river = m.kind === 'river' && b.kind === 'river' && !!m.river && m.river === b.river, out = [];
  if (j === 's') out.push(river ? 'same river, shares overflows with your spot' : 'shares overflows with your spot',
    'At least one overflow upstream counts in both levels');
  else if (j === 'd' || j === 'u') { const way = j === 'd' ? 'downstream' : 'upstream';
    out.push(river ? `same river, further ${way}` : `${way} of your spot`);
    if (outingOver(m) && outingOver(b)) out.push('The forecast counts none of the same overflows'); }
  else out.push(j === 'branch' ? 'same catchment, another branch' : 'different catchment', `It has ${outingOver(b) ? 'overflows and runoff' : 'runoff'} of its own`);
  return `Backup: ${out.map(t => t + '.').join(' ')}`;
}
// In the backup's list: the spots in another catchment than the spot's, from the lite file (outingJoined's 'apart').
const outingApart = (m, s) => !!(m && m.catchment && s.catchment && m.catchment !== s.catchment);

// ------------------------------------------------------------------------------ alerts for the outing
// "Alert me about this outing": the outing's spot and its backup, each on the plan's day, asked for through
// the push Worker's alerts for a date (push/README.md, "Alerts for a date"), exactly as the organisers' page
// asks (spotdate.js: the same list in this browser, the same request, the same cap of 10 pairs shared with
// the organisers' page). The plan's day is always one of the forecast's five, so the Worker tells of each
// change in that day's level from then on; it forgets each pair after its date. Only where the build says
// the Worker takes dates (push.dates), and only in a browser with alerts on already: turning them on, and
// its consent, stays the Saved page's.
//
// The pairs this tile asked for are noted in this browser too (OUTING_ASKED_KEY), so that after the spot,
// the backup or the day changes, the tile can say that the earlier pairs are still on and stop them.
const OUTING_ASKED_KEY = 'dipcast.outingdates';
const outLong = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' });
const outNames = ps => { const n = [...new Set(ps.map(p => outEsc(p.name || p.spot)))]; return n.length > 1 ? `${n.slice(0, -1).join(', ')} and ${n[n.length - 1]}` : n[0] || ''; };
// The outing's pairs: its spot, then its backup, on its day. byId: names, and only spots still listed.
function outingPairs(plan, byId = null) {
  const ids = [plan.spot, plan.finish, plan.backup !== plan.spot ? plan.backup : null].filter((id, i, all) => id && all.indexOf(id) === i && (!byId || byId.has(id)));
  return plan.day ? ids.map(id => ({ spot: id, date: plan.day, ...(byId ? { name: byId.get(id).name } : {}) })) : [];
}
// Against the list this browser asked for: the pairs already on, those that fit under the cap (the spot, then a
// paddle's finish, then the backup), and those left out by it.
function outingAsk(list, pairs, max = outingDates().MAX_DATES) {
  const D = outingDates(), on = pairs.filter(p => D.hasDate(list, p.spot, p.date)), want = pairs.filter(p => !D.hasDate(list, p.spot, p.date));
  const room = Math.max(0, max - list.length);
  return { on, add: want.slice(0, room), left: want.slice(room) };
}
// The whole list to send: these pairs added, or taken out. Only the two fields go, as the organisers' page sends them.
const outingList = (list, pairs, on) => pairs.reduce((l, p) => outingDates().withDate(l, p.spot, p.date, on), list);
// The pairs this tile asked for earlier that are still on and are not this outing's now.
const outingEarlier = (asked, list, pairs) => asked.filter(a => outingDates().hasDate(list, a.spot, a.date) && !pairs.some(p => p.spot === a.spot && p.date === a.date));

// What the alerts part of the tile says, as HTML. a = { state, pairs, list, earlier, saved (the Saved page's
// address), app (an in-app browser's name) }. state: 'none' (the site's date alerts are off: nothing said),
// 'cannot', 'ios', 'inapp', 'blocked' (no notifications here: the calendar file instead), 'off' (alerts not
// on in this browser), 'on'.
function outingAlert(a) {
  const instead = 'Add it to your calendar instead.';
  switch (a.state) {
    case 'cannot': return `<p class="small">This browser cannot show notifications from websites, so SwimSignal cannot alert you about this outing. ${instead}</p>`;
    case 'ios': return `<p class="small">On iPhone and iPad, notifications work only in the Home Screen app, so SwimSignal cannot alert you about this outing here. ${instead}</p>`;
    case 'inapp': return `<p class="small">Alerts cannot be turned on in the ${outEsc(a.app)} app's browser, so SwimSignal cannot alert you about this outing here. ${instead}</p>`;
    case 'blocked': return `<p class="small">Notifications are blocked for this site in your browser settings, so SwimSignal cannot alert you about this outing. ${instead}</p>`;
    case 'off': return `<p class="small">To be alerted about this outing, first turn on alerts in this browser, on the <a href="${outEsc(a.saved)}" id="outing-to-alerts">Saved page</a>.</p>`;
    case 'on': break;
    default: return '';
  }
  const D = outingDates(), { pairs, list, earlier = [] } = a, k = outingAsk(list, pairs);
  if (!pairs.length) return '';
  const day = pairs[0].date, whose = `${outDay(day)}'s`;   // "today's", "Saturday's"
  let h = '';
  if (k.on.length) h += `<p class="outing-alert-on"><b>Alerts are on for ${k.on.length === pairs.length ? 'this outing' : outNames(k.on)}.</b> A notification each time ${whose} level or official notice changes at ${outNames(k.on)}.</p>`
    + `<p class="small">Stored by SwimSignal's alert service: this browser's push address, with ${outNames(k.on)} on ${outLong(day)}. ${k.on.length > 1 ? 'Each is' : 'It is'} forgotten after that day.</p>`;
  if (k.add.length) {
    if (!k.on.length) h += `<p>A notification each time ${whose} level or official notice changes at ${outNames(k.add)}.</p>`;
    h += '<details class="fold"><summary>What asking sends</summary><p class="small">Asking sends the spot'
      + `${pairs.length > 1 ? 's' : ''} and the day of this outing, with your browser's push address, to SwimSignal's alert service, and nothing else about you: `
      + `not the time, where you start from or the rest of the plan. It keeps them with any dates you asked about on the organisers' page, up to ${D.MAX_DATES} in all, `
      + 'and forgets each one after its date. You can stop them here at any time; turning alerts off on the Saved page deletes them all. '
      + 'A notification opens the organisers\' page for that spot and day. An alert can be late or not come at all, so no alert does not mean the water is clean. '
      + '<a href="privacy.html">Privacy notice</a>.</p></details>';
  }
  if (k.left.length) h += `<p class="small">${k.add.length || k.on.length ? `Alerts can cover ${D.MAX_DATES} dates at most, so ${outNames(k.left)} is left out.`
    : `You have alerts for ${D.MAX_DATES} dates, the most there can be. Stop one of them to add this outing.`}</p>`;
  const buttons = (k.add.length ? `<button type="button" class="btn" data-outing-alert="add">${k.on.length || k.left.length ? `Alert me about ${outNames(k.add)}` : 'Alert me about this outing'}</button>` : '')
    + (k.on.length ? '<button type="button" class="btn" data-outing-alert="stop">Stop alerts for this outing</button>' : '');
  if (buttons) h += `<p class="outing-acts">${buttons}</p>`;
  if (earlier.length) h += `<p class="small">Alerts are still on from an earlier choice for this outing: ${earlier.map(p => `${outNames([p])} on ${outLong(p.date)}`).join('; ')}. `
    + '<button type="button" class="linkbtn small" data-outing-alert="earlier">Stop those</button></p>';
  return h;
}

// ------------------------------------------------------------------------------ the calendar file
// "Add to calendar": one event for the outing, made in this browser and sent nowhere (iCalendar, RFC 5545,
// with spotdate.js's lines, folding and escapes, as the organisers' page's file). Timed events are
// converted from the spot's UK/Ireland local time to UTC; with no time picked, the
// event is the whole day. It carries the spot's name and links back to the spot's page and the plan,
// never a forecast level, which would be out of date by the time the calendar shows it. One UID per day
// and spot, so importing the file again after changing the time updates the event rather than adding one.
// c = { day, when, act, meet, main: {id, name, url, practical}, finish: {name, url} | null, backup: {name, url, practical} | null, plan (the plan's address), host }.
// `practical` (outingPractical): the spot's guide's confirmed parking and getting-in facts, which help at the car park
// with no signal. Only what the guide verified, with its checked date; never a swimmer's suggestion, and never a
// meeting point or a put-in the guide does not give.
const outingPractical = s => {
  const g = s && s.guide, facts = g && Array.isArray(g.facts) ? g.facts.filter(f => f && f.status === 'confirmed') : [];
  const say = (topic, label) => { const t = facts.filter(f => f.topic === topic).map(f => f.text).slice(0, 2);
    return t.length ? `${label}, from its guide (checked ${g.checked}): ${t.join(' ')}` : ''; };
  return [say('parking', 'Parking'), say('entry', 'Getting in')].filter(Boolean);
};
const OUTING_CHECK = 'Check SwimSignal and any official notice before you go.';
function outingIcs(c, now = Date.now()) {
  const D = outingDates(), span = outingSpan(c.when);
  const next = (() => { const d = new Date(c.day + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1); return d.toISOString().slice(0, 10); })();
  const when = span ? [`DTSTART:${D.icsStamp(outingUtc(c.day, span[0]))}`, `DTEND:${D.icsStamp(outingUtc(c.day, span[1]))}`]
    : [`DTSTART;VALUE=DATE:${D.icsDay(c.day)}`, `DTEND;VALUE=DATE:${D.icsDay(next)}`];
  const text = [OUTING_CHECK, `Your spot: ${c.main.name}, ${c.main.url}`, ...(OUTING_MEET_WORDS[c.meet] ? [`Meet ${OUTING_MEET_WORDS[c.meet]}.`] : []), ...(c.main.practical || []),
    ...(c.finish ? [`Finish: ${c.finish.name}, ${c.finish.url}`] : []),
    ...(c.backup ? [`Backup: ${c.backup.name}, ${c.backup.url}`, ...(c.backup.practical || [])] : []), `Your plan: ${c.plan}`].join('\n');
  return D.icsCalendar('-//SwimSignal//Outing//EN', [['BEGIN:VEVENT', `UID:outing-${c.day}-${c.main.id}@${c.host}`, `DTSTAMP:${D.icsStamp(now)}`, ...when,
    `SUMMARY:${D.icsEsc(`${outingVerb(c.act)}: ${c.main.name}`)}`, `LOCATION:${D.icsEsc(c.main.name)}`, `DESCRIPTION:${D.icsEsc(text)}`, `URL:${c.main.url}`,
    ...(span ? [] : ['TRANSP:TRANSPARENT']), 'END:VEVENT']]);
}
// The part of the tile that keeps the outing: the alerts (filled in once this browser's push state is
// known: outingAlert), then the calendar file.
const outingKeep = () => '<div class="outing-keep"><div id="outing-alert"></div>'
  + '<p class="outing-acts"><button type="button" class="btn" id="outing-ics">Add to calendar</button> <button type="button" class="btn" id="outing-share">Share this outing</button></p>'
  + '<p class="small muted">A calendar file made in this browser and sent nowhere: the time, the spots and links back here, without a level, which would go out of date. '
  + 'The shared link holds the day, the time, the spots, what for and where to meet, as you picked them, with the forecast\'s issue time and each spot\'s level when you share it, '
  + 'and the plan around your spot: not where you start from, and no words of yours.</p>'
  + '<p class="small muted msg" id="outing-alert-msg" aria-live="polite"></p></div>';

// ------------------------------------------------------------------------------ access at each spot
// The spot's own practical guide (guide.js, from guides/<id>.toml) for the four topics a trip turns on: parking,
// the path to the water, getting in and getting out. The facts in their own words, each run with who says so
// (guideRuns: the linked source, or a swimmer's suggestion, who and when), under the guide's checked line
// (guideChecked). The four it lacks are named, so a missing topic reads as unknown, not as none, and the rest of
// the guide (toilets, fees, who can swim) is left to the spot's page, which the last line names. Nothing is added
// to a fact. The desk check of permission (access.py, `access`, for the spots from OpenStreetMap and the Peak),
// where there is one, comes first, in its own words, as on the spot's page.
// The guide is in data/spot/<id>.json, not spots-lite.json: until it arrives the block says it is loading, and
// a file that did not arrive says so, never "no guide" (guide.js, guideTile, detail_missing).
const OUTING_ACCESS = ['parking', 'path', 'entry', 'exit'];
// For a boat or a board: carrying it to the water and launching it in place of getting in, where the guides have those
// topics (guide.js, GUIDE_TOPICS, from #446); before then, the swimmer's four.
const OUTING_ACCESS_PADDLE = ['paddle', 'parking', 'path', 'carry', 'launch', 'exit'];   // the rules for boats and boards first (guides' "Paddling here")
const OUTING_BOAT = ['paddle', 'sup'];   // plan.js's OUTING_FINISH_ACTS, here so Node needs no plan.js
const outingAccessTopics = (act, have) => (OUTING_BOAT.includes(act) && have.has('launch') ? OUTING_ACCESS_PADDLE : OUTING_ACCESS).filter(k => have.has(k));
const outingGuide = () => typeof guideRuns === 'function' ? { guideRuns, guideChecked, GUIDE_TOPICS } : require('./guide.js');
function outingAccess(s, today, act = null) {
  if (!s) return '';
  const G = outingGuide(), label = new Map(G.GUIDE_TOPICS), TOPICS = outingAccessTopics(act, new Set(label.keys()));
  const a = s.access && typeof s.access.text === 'string' && s.access.text ? s.access : null;
  const permit = a ? `<p class="g-text">${outEsc(a.text)}</p><p class="g-src">${a.checked_at ? `Desk check ${outEsc(a.checked_at)}; current signs not inspected.` : 'Not known when it was checked.'}</p>` : '';
  if (s.detail_missing) return permit + '<p class="small muted">The access guide could not be loaded here. The spot\'s page has it, if there is one.</p>';
  if (s.detail_file && !s.detail_loaded) return permit + '<p class="small muted">Loading the access guide…</p>';
  const g = s.guide, facts = g && Array.isArray(g.facts) ? g.facts : [];
  if (!facts.length) return permit + '<p class="small muted">No access guide for this spot yet.</p>';
  const by = new Map(TOPICS.map(k => [k, facts.filter(f => f && f.topic === k)]));
  const have = TOPICS.filter(k => by.get(k).length), gaps = TOPICS.filter(k => !by.get(k).length);
  const rest = G.GUIDE_TOPICS.map(([k]) => k).filter(k => !TOPICS.includes(k) && facts.some(f => f && f.topic === k));
  return permit + `<p class="g-src">${G.guideChecked(g, today)}</p>`
    + (have.length ? '<dl class="g-facts">' + have.map(k => `<div class="g-row"><dt>${label.get(k)}</dt>`
      + G.guideRuns(by.get(k)).map(r => `<dd>${r.texts.map(t => `<p class="g-text">${outEsc(t)}</p>`).join('')}<p class="g-src">${r.src}</p></dd>`).join('')
      + '</div>').join('') + '</dl>' : '')
    + (gaps.length ? `<p class="g-gap">Not in this guide yet: ${gaps.map(k => label.get(k).toLowerCase()).join(', ')}.</p>` : '')
    + (rest.length ? `<p class="small muted">Also in the guide on the spot's page: ${rest.map(k => label.get(k).toLowerCase()).join(', ')}.</p>` : '');
}
const outingAccessBox = (id, inner) => `<div class="outing-access" data-outing-access="${outEsc(id)}"><p class="outing-role">Access</p>${inner}</div>`;

// ------------------------------------------------------------------------------ a paddle's finish
// For a paddle or a board, a finish: another listed river spot downstream (Swim Together S4). The build finds the route
// down the river between the two and which monitored overflows are on it (src/dipcast/stretches.py): the start's
// lite `downstream` ([[id, km]]) offers the finishes, and its data/spot/<id>.json `stretches` holds, for each, the
// overflows on the route ([site_id, km below the start]), those on a side stream or another arm of the river that the
// finish's forecast counts ([site_id, km below the start where it joins, or null where it reaches the finish another
// way]) and how many are above the start. The names come from the finish's data/upstream/<id>.json. Neither spot's
// level is one for the water between, and the block says so.
const OUTING_STRETCH_SHOWN = 8;
// The finishes a start offers: [{ id, name, km }], listed spots only, nearest first (byId: the listed spots).
const outingFinishes = (s, byId) => (s && Array.isArray(s.downstream) ? s.downstream : [])
  .filter(([id, km]) => byId.has(id) && Number.isFinite(km)).map(([id, km]) => ({ id, name: byId.get(id).name, km }));
const outingKm = km => `${km < 10 ? Math.round(km * 10) / 10 : Math.round(km)} km`;
// The block, as HTML. o = { start, finish (names), st (the start's stretch to the finish, or null), rows (the
// finish's upstream file's overflows, by site_id: a Map), state ('loading', 'ok', 'missing') }.
function outingStretch(o) {
  const head = `<h3 class="outing-watch-h">Between ${outEsc(o.start)} and ${outEsc(o.finish)}</h3>`;
  if (o.state === 'loading') return `<div class="outing-watch outing-stretch">${head}<p class="small muted">Loading what drains into the water between…</p></div>`;
  if (o.state !== 'ok' || !o.st) return `<div class="outing-watch outing-stretch">${head}<p class="small muted">What drains into the water between could not be loaded here. Each spot's page has its own overflows.</p></div>`;
  const st = o.st;
  const named = id => { const r = o.rows && o.rows.get(id); return r ? { name: r.site_name || id, company: r.company, water: r.receiving_watercourse, live: r.has_live } : { name: id }; };
  const list = (items, line) => {
    if (!items.length) return '';
    const shown = items.slice(0, OUTING_STRETCH_SHOWN).map(line), more = items.length - shown.length;
    return `<ul class="outing-watch-list">${shown.map(t => `<li>${t}</li>`).join('')}${more > 0 ? `<li>and ${more} more.</li>` : ''}</ul>`;
  };
  const feed = r => r.live === false ? ', no live feed' : '';
  const route = st.route || [], side = st.side || [], n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const onRoute = list(route, ([id, km]) => { const r = named(id);
    return `${outEsc(r.name)}${r.company ? ` (${outEsc(r.company)})` : ''}, ${km === null ? 'on the route' : `${outingKm(km)} below the start`}${feed(r)}`; });
  const fromSide = list(side, ([id, km]) => { const r = named(id);
    return `${outEsc(r.name)}${r.water ? `, on ${outEsc(r.water)}` : ''}, ${km === null ? 'reaching the finish another way' : `joining ${outingKm(km)} below the start`}${feed(r)}`; });
  return `<div class="outing-watch outing-stretch">${head}`
    + `<p>About ${outingKm(st.km)} down the river, by the way the water goes.</p>`
    + `<p><b>On the route: ${route.length ? n(route.length, 'monitored overflow', 'monitored overflows') : 'no monitored overflow that SwimSignal knows of'}.</b></p>${onRoute}`
    + (side.length ? `<p><b>From side streams or another arm of the river: ${side.length}.</b> Their water reaches the finish, and the route below where each joins.</p>${fromSide}` : '')
    + (st.above ? `<p>Above the start: ${n(st.above, 'more', 'more')}, counted in both spots' levels.</p>` : '')
    + '<p class="small muted">The finish\'s level counts all of these; the start\'s counts only those above it. Neither is a level for the water between: '
    + 'just below an overflow that is spilling, the water can be worse than at either end. These are the monitored storm overflows SwimSignal has placed on the river, '
    + 'and from side streams only those within 60 km of the finish by water: not unmonitored outfalls, or farm and road runoff. '
    + 'Nothing here is about weirs, flow, or where you can get in and out.</p></div>';
}

// ------------------------------------------------------------------------------ the tile
// A column for a spot: c = { id, name, href, tone, headline, why, ev, meta }, headline/why/ev already
// HTML (the page's own words, escaped where they were made), the rest text.
const outingCol = (c, role) => `<div class="outing-col"><p class="outing-role">${role}</p>`
  + `<h3 class="outing-nm"><a href="${outEsc(c.href)}" data-id="${outEsc(c.id)}">${outEsc(c.name)}</a></h3>`
  + (c.meta ? `<p class="k">${outEsc(c.meta)}</p>` : '')
  + (c.official || '') + `<p class="hl ${outEsc(c.tone)}">${c.headline}</p>` + (c.why ? `<p class="why">${c.why}</p>` : '') + (c.ev || '') + (c.access ? outingAccessBox(c.id, c.access) : '') + '</div>';
// The whole tile. o = { day, when, spot, backup, act, meet, shared (a shared link's forecast time in words,
// "Thu 13:27", while the plan still carries its stamp; else ''), groups (outingOptions for the spot), backupGroups,
// main, alt (columns, or null), join (outingJoin's line, text), missing (ids), issued (text: "15:29, 2 h ago"), open, nowMs, dateAlerts (the
// site's alerts for a date are on, so the outing can be sent if asked), preview (opened from a link and not
// kept: index.html, PLAN_PREVIEW; then { mine: what keeping it replaces, outingReplaces's, or ''; off: the link's own
// day where it is no longer one of the five (plan.js, planDayOff), or null; fresh: started here with "Plan an outing
// here" while another outing is kept, not opened from a link }; else null), finishes (for a paddle or a
// board: outingFinishes, or null), finish (its id), fin (its column, or null), stretch (outingStretch's HTML) }.
function outingSection(o) {
  const opt = (groups, sel, note = () => '') => groups.map(([h, g]) => `<optgroup label="${outEsc(h)}">`
    + g.map(s => `<option value="${outEsc(s.id)}"${s.id === sel ? ' selected' : ''}>${outEsc(s.name)}${note(s)}</option>`).join('') + '</optgroup>').join('');
  const apart = s => outingApart(o.main, s) ? ', different catchment' : '';
  const times = `<option value="">Any time</option>` + Object.keys(OUTING_PARTS).map(p => `<option value="${p}"${o.when === p ? ' selected' : ''}>${p.charAt(0).toUpperCase() + p.slice(1)}</option>`).join('')
    + `<optgroup label="An hour">${OUTING_HOURS.map(h => `<option value="${h}"${o.when === h ? ' selected' : ''}>${h}:00</option>`).join('')}</optgroup>`;
  const acts = `<option value="">Swim</option>` + ['paddle', 'sup'].map(a => `<option value="${a}"${o.act === a ? ' selected' : ''}>${OUTING_ACT_WORDS[a][0]}</option>`).join('');
  const meets = `<option value="">Not set</option>` + Object.entries(OUTING_MEET_WORDS).map(([k, w]) => `<option value="${k}"${o.meet === k ? ' selected' : ''}>${w.replace(/^./, c => c.toUpperCase())}</option>`).join('');
  // The names are in the columns' heads: the line says only when, what for, and what is side by side.
  const ing = o.act && o.act !== 'swim' ? `, ${OUTING_ACT_WORDS[o.act][1]}` : '';
  const said = o.main ? `${outingWhen(o.day, o.when).replace(/^./, c => c.toUpperCase())}${ing}: ${o.alt ? 'your spot and a backup, side by side' : 'your spot'}.` : '';
  const meet = o.main && OUTING_MEET_WORDS[o.meet] ? `<p class="small">Meet ${OUTING_MEET_WORDS[o.meet]} at ${outEsc(o.main.name)}: the Access part under it says what its guide knows.</p>` : '';
  const licence = o.main && o.act && o.act !== 'swim' ? OUTING_LICENCE : '';
  const notes = [...(o.when ? ['Times are local to the swim spot (UK and Ireland time).'] : []), ...outingTimeNote(o.day, o.when, o.nowMs), ...(ing ? ['The level is for the water, the same whatever you do on it.'] : [])];
  const gone = o.missing && o.missing.length ? `<p class="small muted">${o.missing.length === 1 ? 'A spot in this outing is' : 'Spots in this outing are'} no longer listed, so ${o.missing.length === 1 ? 'it is' : 'they are'} left out.</p>` : '';
  const body = !o.main ? '<p class="sub">Choose a spot to see it here, with a backup beside it.</p>'
    : `<p class="outing-said">${said}</p>${meet}${licence}${outingBoth(o)}${outingNeither(o)}${o.alt ? `<p class="outing-join" id="outing-join">${outEsc(o.join)}</p>` : ''}`
      + `<div class="outing-pair${o.alt ? '' : ' one'}">${outingCol(o.main, 'Your spot')}${o.alt ? outingCol(o.alt, 'Backup') : ''}</div>`
      + (o.fin ? `<div class="outing-pair one">${outingCol(o.fin, 'Finish')}</div><div id="outing-stretch">${o.stretch || ''}</div>` : '')
      + `<p class="small muted">${[...notes, `Issued ${outEsc(o.issued)}.`, 'A lower forecast level does not mean safe water: check the signs at the water before you swim.'].join(' ')}</p>`
      + outingKeep();
  // Opened from a link someone shared (plan.js, sent=): said so, with what is below for it. Until it is kept
  // (o.preview), it is in this page's link only, and the line says what keeping it replaces.
  const shared = o.shared && o.main ? `Shared with you, from the forecast issued ${outEsc(o.shared)}. Under the two spots: what has changed since. At the end: alerts and a calendar file for it. ` : '';
  const intro = o.preview
    ? `<p class="sub">${shared || (o.preview.fresh ? 'A new outing. ' : 'From a link. ')}${o.preview.off ? `${outingOff(o.preview.off, o.day)} ` : ''}Not kept in this browser until you keep it.</p>`
      + `<p class="outing-acts"><button type="button" class="btn" id="outing-keep-it">Keep this outing</button></p>`
      + `<p class="small muted">${o.preview.mine ? `Until then, ${outEsc(o.preview.mine)} stays as it is. Keeping this one puts it in its place` : 'Keeping it makes it the plan Plan a swim opens on'}, in this browser, sent nowhere.</p>`
    : shared ? `<p class="sub">${shared}Kept in this browser and in this page's link; sent nowhere. Change anything here and it becomes your own plan.</p>`
    : `<p class="sub">When you mean to go, where, and somewhere else to go instead. Kept in this browser and in this plan's link; sent nowhere${o.dateAlerts ? ' unless you ask for alerts about it' : ''}.</p>`;
  const head = o.main && o.preview ? (o.shared ? 'Outing shared with you' : o.preview.fresh ? 'New outing' : 'Outing from a link') : o.shared && o.main ? 'Outing shared with you' : 'Your outing';
  return `<details class="sec tile outing" id="outing"${o.open ? ' open' : ''}><summary><span>${head}${o.main ? `<span class="k">${outEsc(o.main.name)}${o.alt ? `, backup ${outEsc(o.alt.name)}` : ''}</span>` : ''}</span></summary>`
    + intro
    + `<div class="outing-fields"><label>When<select data-outing="when">${times}</select></label>`
    + `<label>Spot<select data-outing="spot"><option value="">Choose a spot</option>${opt(o.groups, o.spot)}</select></label>`
    + `<label>Backup (optional)<select data-outing="backup"><option value="">No backup</option>${opt(o.backupGroups, o.backup, apart)}</select></label>`
    + `<label>What for<select data-outing="act">${acts}</select></label>`
    + (o.main ? `<label>Meet (optional)<select data-outing="meet">${meets}</select></label>` : '')
    + (o.main && o.finishes ? (o.finishes.length
      ? `<label>Finish (optional)<select data-outing="finish"><option value="">Not set</option>${o.finishes.map(f => `<option value="${outEsc(f.id)}"${f.id === o.finish ? ' selected' : ''}>${outEsc(f.name)}, ${outingKm(f.km)} down</option>`).join('')}</select></label>`
      : `<p class="small muted">No listed spot downstream of ${outEsc(o.main.name)} that SwimSignal can trace the route to, so there is no finish to pick.</p>`) : '') + '</div>'
    + gone + body + '</details>';
}

// A link's own day that is not one of the five, said: the plan shows the outing's spots on the first day instead.
const outingLong = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' });
const outingOff = (off, day) => `It was for ${outingLong(off)}, ${off < day ? 'which has passed' : 'past the days this forecast covers'}, so it is shown for ${outDay(day)}, without its time.`;

// What keeping an outing from a link would replace, in words: the outing kept in this browser while its day is one
// of the five and its spot is listed ("your own outing to Henley on Saturday"), else the plan kept here at all
// ("the plan kept in this browser"), else '' (nothing is kept). kept: plan.js's planKept; byId: the listed spots.
function outingReplaces(kept, byId) {
  if (!kept) return '';
  const s = kept.day && kept.spot && byId.get(kept.spot);
  if (s) return `your own outing to ${s.name} ${outingRules().dayWord(kept.day)}`;
  return kept.from || kept.compare || kept.spot ? 'the plan kept in this browser' : '';
}

// ------------------------------------------------------------------------------ in the page
// Draws the tile at the top of the plan's results (index.html, drawPlan), from the page's own spots and
// sentences (planWhy, planEvidence, dayHeadline), and keeps a change in the plan (planAddress). shown: the
// plan's rows, as {s, miles, level}. Its open state stays as it was across redraws.
let OUTING_OPEN = null, OUTING_DAY = null;
function drawOuting(box, shown) {
  const old = document.getElementById('outing'); if (old) old.remove();
  const kept = outingForDay(PLAN, OUTING_DAY); OUTING_DAY = PLAN.day;
  if (kept !== PLAN) { for (const k of ['when', 'sent', 'lv', 'blv', 'flv']) if (!(k in kept)) delete PLAN[k]; planAddress(); }   // a time, or a shared stamp, for another day
  const byId = new Map(DATA.spots.map(s => [s.id, s])), miles = new Map(shown.map(o => [o.s.id, o.miles])), from = planFrom();
  const away = s => miles.has(s.id) ? miles.get(s.id) : from ? km(from, [s.lat, s.lon]) / MILE_KM : null;
  const col = s => { const m = away(s);
    return { id: s.id, name: s.name, href: spotPath(s.id) + (daily(s) ? '#day=' + PLAN.day : ''), tone: tone(dayLevel(s, PLAN.day)),
      headline: dayHeadline(s, PLAN.day), official: outingOfficial(s), notice: outingBrief(s), why: planWhy(s, PLAN.day), ev: planEvidence(s),
      level: dayLevel(s, PLAN.day), advised: typeof eaTodayRestricts === 'function' && eaTodayRestricts(s),   // a notice that restricts swimming
      access: outingAccess(s, today(), PLAN.act),
      meta: [m === null ? null : cap(milesAway(m)), cap(s.kind)].filter(Boolean).join(' · '), catchment: s.catchment }; };
  const pair = outingPair(PLAN, byId), list = shown.map(o => o.s);
  // A paddle's finish, while the spot still offers it.
  const paddle = OUTING_FINISH_ACTS.includes(PLAN.act), finishes = paddle && pair.main ? outingFinishes(pair.main, byId) : null;
  const fin = finishes && finishes.some(f => f.id === PLAN.finish) ? byId.get(PLAN.finish) : null;
  if (OUTING_OPEN === null) OUTING_OPEN = !!(PLAN.spot || PLAN.when);
  // outingwatch.js reads the stamp (outingWatchShared); since.js says its time.
  const sent = PLAN.sent && typeof outingWatchShared === 'function' && outingWatchShared(PLAN);
  // Opened from a link and not kept (index.html, PLAN_PREVIEW): nothing below writes to this browser until it is.
  const preview = typeof PLAN_PREVIEW === 'boolean' && PLAN_PREVIEW && pair.main
    ? { mine: outingReplaces(keptPlan(), byId), off: PLAN_OFF, fresh: typeof PLAN_FRESH === 'boolean' && PLAN_FRESH } : null;
  box.insertAdjacentHTML('afterbegin', outingSection({ preview, finishes, finish: PLAN.finish, fin: fin && col(fin),
    stretch: fin ? outingStretch({ start: pair.main.name, finish: fin.name, state: 'loading' }) : '', day: PLAN.day, when: PLAN.when, spot: PLAN.spot, backup: PLAN.backup, act: PLAN.act, meet: PLAN.meet,
    shared: sent ? issuedWords(sent.forecast) : '',
    groups: outingOptions(list, SAVED, byId, PLAN.backup), backupGroups: outingOptions(list, SAVED, byId, PLAN.spot),
    main: pair.main && col(pair.main), alt: pair.backup && col(pair.backup), join: outingJoin(pair.main, pair.backup), missing: pair.missing,
    issued: `${issued()}, ${ago(ageMin())} ago`, open: OUTING_OPEN, nowMs: Date.now(), dateAlerts: outingDates().dateAlertsOn(DATA) }));
  const tile = document.getElementById('outing');
  tile.addEventListener('toggle', () => { OUTING_OPEN = tile.open; });
  tile.querySelectorAll('[data-outing]').forEach(el => el.addEventListener('change', () => {
    const k = el.dataset.outing, next = outingChanged(PLAN, k);
    for (const x of Object.keys(PLAN)) if (!(x in next)) delete PLAN[x];
    if (el.value) PLAN[k] = el.value; else delete PLAN[k];
    if (PLAN.backup && PLAN.backup === PLAN.spot) delete PLAN.backup;
    if (!OUTING_FINISH_ACTS.includes(PLAN.act)) delete PLAN.finish;   // a finish is for a paddle or a board
    planAddress(); drawOuting(box, shown);
    const again = document.querySelector(`[data-outing="${k}"]`); if (again) again.focus();
  }));
  tile.querySelectorAll('a[data-id]').forEach(a => a.addEventListener('click', e => { if (!plainClick(e)) return; e.preventDefault(); select(a.dataset.id, true, true, PLAN.day); }));
  if (typeof outingWatchDraw === 'function') outingWatchDraw(tile, PLAN, { ...pair, finish: fin }, DATA.generated_at, Date.now(), !!preview);   // outingwatch.js: what would change this plan, and what has
  if (!pair.main) return;
  const keepIt = document.getElementById('outing-keep-it');
  if (keepIt) keepIt.addEventListener('click', () => {
    keepPlan(); drawOuting(box, shown);
    const msg = document.getElementById('outing-alert-msg'); if (msg) msg.textContent = 'Kept. Plan a swim opens on this outing from now on.';
    const h = document.querySelector('#outing > summary'); if (h) h.focus();
  });
  // The swim passport's Prepared planner badge (passport.js): the first day an outing has a spot and a backup,
  // planned here or kept from a link; never for one only looked at.
  if (pair.backup && !preview && typeof passportPlanned === 'function') passportPlanned(today());
  // Each spot's guide, once its own file is in (index.html, spotDetail), into its column's access block; and the
  // line on how the two are joined, which the spot's or the backup's `linked` settles.
  for (const s of [pair.main, pair.backup, fin].filter(Boolean)) if (typeof spotDetail === 'function' && s.detail_file && !s.detail_loaded)
    spotDetail(s).then(() => { const el = tile.querySelector(`[data-outing-access="${CSS.escape(s.id)}"]`);
      if (el) el.innerHTML = '<p class="outing-role">Access</p>' + outingAccess(s, today(), PLAN.act);
      const j = tile.querySelector('#outing-join'); if (j) j.textContent = outingJoin(pair.main, pair.backup); });
  if (fin) outingStretchDraw(pair.main, fin);
  if (typeof OutingPack === 'object' && !preview) OutingPack.draw({ ...pair, finish: fin });   // outingpack.js: keep this outing for offline use, once it is kept
  // The calendar file, made here when asked (organisers.html's way of handing a file over).
  document.getElementById('outing-ics').addEventListener('click', () => {
    const abs = p => new URL(p, location.href).href, link = s => abs(spotPath(s.id) + (daily(s) ? '#day=' + PLAN.day : ''));
    const text = outingIcs({ day: PLAN.day, when: PLAN.when, act: PLAN.act, meet: PLAN.meet, finish: fin && { name: fin.name, url: link(fin) },
      main: { id: pair.main.id, name: pair.main.name, url: link(pair.main), practical: outingPractical(pair.main) },
      backup: pair.backup && { name: pair.backup.name, url: link(pair.backup), practical: outingPractical(pair.backup) }, plan: abs(planPath() + planHash(PLAN)), host: location.hostname });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/calendar;charset=utf-8' }));
    a.download = `swimsignal-outing-${PLAN.day}.ics`; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  bindShareLink(document.getElementById('outing-share'), document.getElementById('outing-alert-msg'),
    new URL(planPath() + planHash(outingShared(PLAN, pair.main, { sent: outingSent(DATA.generated_at),
      lv: dayLevel(pair.main, PLAN.day), blv: pair.backup && dayLevel(pair.backup, PLAN.day), flv: fin && dayLevel(fin, PLAN.day) })), location.href).href,
    `${outingVerb(PLAN.act)}: ${pair.main.name} · ${BRAND}`, 'Copy link to this outing');
  bindOutingAlert(byId);
}

// The stretch's block, once the start's own file (its `stretches`) and the finish's list of overflows are in.
async function outingStretchDraw(start, fin) {
  let st = null, rows = null, state = 'ok';
  try {
    if (typeof spotDetail === 'function' && start.detail_file && !start.detail_loaded) await spotDetail(start);
    st = (start.stretches || []).find(x => x && x.to === fin.id) || null;
    const r = await fetch(new URL(`data/upstream/${encodeURIComponent(fin.id)}.json`, ROOT).href);
    if (!r.ok) throw new Error(`the finish's overflows answered ${r.status}`);
    rows = new Map(((await r.json()).overflows || []).map(o => [o.site_id, o]));
  } catch (e) { state = 'missing'; }
  const el = document.getElementById('outing-stretch');
  if (el && PLAN.finish === fin.id && PLAN.spot === start.id) el.innerHTML = outingStretch({ start: start.name, finish: fin.name, st, rows, state });
}

// What this browser can do about alerts (index.html's canPush, pushSub, IOS and IN_APP, as the Saved page's
// alerts tile reads them). Nothing is asked of the browser beyond what it already holds: no permission prompt.
async function outingPushState() {
  if (!outingDates().dateAlertsOn(DATA)) return { state: 'none' };
  if (!canPush()) return { state: IN_APP ? 'inapp' : IOS && !navigator.standalone ? 'ios' : 'cannot' };
  if (Notification.permission === 'denied') return { state: 'blocked' };
  const sub = Notification.permission === 'granted' ? await pushSub().catch(() => null) : null;
  return sub ? { state: 'on', sub } : { state: 'off' };
}
// The alerts part of the tile, once the push state is known. Nothing is sent until a button is pressed;
// then the whole list goes, as on the organisers' page.
async function bindOutingAlert(byId) {
  const el = document.getElementById('outing-alert'), msg = document.getElementById('outing-alert-msg');
  const D = outingDates(), st = await outingPushState();
  if (!el || !el.isConnected) return;   // the tile was drawn again meanwhile
  const t = outingRules().today(), pairs = outingPairs(PLAN, byId), endpoint = st.sub && st.sub.endpoint;
  let mem = null;   // the list as last sent, where this browser cannot keep it
  const kept = key => { try { return D.keptDates(localStorage.getItem(key), endpoint, t); } catch (e) { return []; } };
  const read = () => mem || kept(D.DATES_KEY), asked = () => kept(OUTING_ASKED_KEY);
  const named = ps => ps.map(p => ({ ...p, name: byId.has(p.spot) ? byId.get(p.spot).name : p.spot }));
  const paint = () => {
    const list = read();
    el.innerHTML = outingAlert({ state: st.state, pairs, list, earlier: named(outingEarlier(asked(), list, pairs)), saved: savedPath(), app: IN_APP });
    const go = document.getElementById('outing-to-alerts');
    if (go) go.addEventListener('click', e => { if (!plainClick(e)) return; e.preventDefault(); openSaved();
      const h = document.getElementById('alerts-h'); if (h) { h.tabIndex = -1; h.scrollIntoView({ block: 'start' }); h.focus({ preventScroll: true }); } });
    el.querySelectorAll('[data-outing-alert]').forEach(b => b.addEventListener('click', async () => {
      const how = b.dataset.outingAlert, list = read(), k = outingAsk(list, pairs);
      const these = how === 'add' ? k.add : how === 'stop' ? k.on : outingEarlier(asked(), list, pairs), on = how === 'add';
      const next = outingList(list, these, on);
      el.querySelectorAll('button').forEach(x => { x.disabled = true; }); msg.textContent = '';
      try {
        await D.sendDates(DATA.push.url, st.sub, next);
        mem = next; D.storeDates(st.sub, next);
        try { localStorage.setItem(OUTING_ASKED_KEY, JSON.stringify({ endpoint, dates: outingList(asked(), these, on) })); } catch (e) { /* the earlier-choice line needs it only */ }
        paint();
        const names = [...new Set(named(these).map(p => p.name))].join(' and ');
        msg.textContent = on ? `Alerts are on for ${names}.` : how === 'stop' ? 'Alerts for this outing are off.' : `Alerts are off for ${names}.`;
      } catch (e) { el.querySelectorAll('button').forEach(x => { x.disabled = false; }); msg.textContent = `Could not change alerts for this outing: ${e.message}.`; }
    }));
  };
  paint();
}

if (typeof module === 'object' && module.exports) {
  module.exports = { outingJoined, outingJoin, outingApart, OUTING_LICENCE, OUTING_ACCESS_PADDLE, outingAccessTopics, outingResumeSaid, outingReplaces, outingOff, outingFinishes, outingStretch, outingKm, OUTING_PARTS, OUTING_HOURS, OUTING_CHECK, OUTING_ASKED_KEY, OUTING_ACT_WORDS, OUTING_MEET_WORDS, outingChanged, outingSent, outingVerb, outingOfficial, outingAccess, OUTING_ACCESS, outingPractical, outingBoth, outingPoor, outingNeither, outingShared, outingSpan, outingWhen, outingTimeNote, outingForDay, outingOptions, outingPair, outingSection,
    outingPairs, outingAsk, outingList, outingEarlier, outingAlert, outingIcs };
}
