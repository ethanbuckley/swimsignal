// A spot on a date, as the organisers' page (organisers.js) and a plan's outing (outing.js) both use it:
// the calendar file, made in the browser, and the alerts for a date that the push Worker sends
// (push/README.md, "Alerts for a date"). Moved here from organisers.js so both say and send the same;
// the organisers' page's file and requests are unchanged by the move (tests/site_event_week.test.cjs).
//
// A plain script, as levels.js: one global, SpotDate, in the page (so no name here can clash with the
// app's own), and the same object as the export in Node.
const SpotDate = (() => {
  const ISO = /^\d{4}-\d{2}-\d{2}$/;
  const realDate = iso => { if (!ISO.test(String(iso))) return false; const d = new Date(iso + 'T00:00:00Z'); return !isNaN(d) && d.toISOString().slice(0, 10) === iso; };

  // ------------------------------------------------------------------ the calendar file
  // iCalendar (RFC 5545): lines end in CRLF and fold at 75 octets; text escapes \ ; , and new lines.
  const icsEsc = v => String(v).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');
  const octets = ch => { const c = ch.codePointAt(0); return c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4; };
  function icsFold(line) {
    const out = []; let cur = '', n = 0;
    for (const ch of line) { const b = octets(ch); if (n + b > 75) { out.push(cur); cur = ' '; n = 1; } cur += ch; n += b; }
    return [...out, cur].join('\r\n');
  }
  const icsDay = iso => iso.replace(/-/g, '');
  const icsStamp = ms => new Date(ms).toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  // The whole file: events, each its lines from BEGIN:VEVENT to END:VEVENT, unfolded.
  const icsCalendar = (prodid, events) => ['BEGIN:VCALENDAR', 'VERSION:2.0', `PRODID:${prodid}`, 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', ...events.flat(), 'END:VCALENDAR']
    .map(icsFold).join('\r\n') + '\r\n';

  // ------------------------------------------------------------------ alerts for a date
  // Shown only where the site's alerts are on and the build says the Worker takes dates (spots.json's
  // push.dates, set by the repository variable DIPCAST_PUSH_DATES). The page sends the whole list each
  // time, as the app sends its saved spots, and keeps it in this browser to know what is on; the Worker
  // keeps the saved spots and the weekly note as they were.
  const DATES_KEY = 'dipcast.pushdates', MAX_DATES = 10;   // the Worker's cap (push/src/dates.js)
  const dateAlertsOn = data => !!(data && data.push && data.push.url && data.push.dates === true);
  // The list kept for this push address, without dates that have passed.
  const keptDates = (raw, endpoint, t) => { let v = null; try { v = JSON.parse(raw || 'null'); } catch (e) { /* none */ }
    return v && v.endpoint === endpoint && Array.isArray(v.dates) ? v.dates.filter(d => d && typeof d.spot === 'string' && realDate(d.date) && d.date >= t) : []; };
  const hasDate = (list, spot, date) => list.some(d => d.spot === spot && d.date === date);
  const withDate = (list, spot, date, on) => on ? (hasDate(list, spot, date) ? list : [...list, { spot, date }]) : list.filter(d => !(d.spot === spot && d.date === date));
  // What POST /subscribe gets: the push subscription and the whole list, nothing else (the saved spots and
  // the weekly note, left out, stay as the Worker has them).
  const datesBody = (sub, dates) => JSON.stringify({ subscription: sub.toJSON(), dates });
  // Sends the list; throws with the words the page shows after "Could not change alerts ...: ".
  async function sendDates(url, sub, dates, fetcher = fetch) {
    const res = await fetcher(url + 'subscribe', { method: 'POST', signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json' },
      body: datesBody(sub, dates) }).catch(() => { throw new Error('the alert service could not be reached. Check your connection and try again'); });
    if (!res.ok) { const why = (await res.text().catch(() => '')).slice(0, 120); throw new Error(res.status === 400 && why ? why : `the alert service answered ${res.status}`); }
  }
  const storeDates = (sub, dates) => { try { localStorage.setItem(DATES_KEY, JSON.stringify({ endpoint: sub.endpoint, dates })); } catch (e) { /* kept in memory for the page */ } };

  return { realDate, icsEsc, icsFold, icsDay, icsStamp, icsCalendar, DATES_KEY, MAX_DATES, dateAlertsOn, keptDates, hasDate, withDate, datesBody, sendDates, storeDates };
})();

if (typeof module === 'object' && module.exports) module.exports = SpotDate;
