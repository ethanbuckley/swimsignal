// Brief versions and a leader's "read" tick (a local prototype, on the decision record, record.html). A club's
// brief for a spot and a day changes each time the forecast is issued, so a leader who read it at 07:00 may
// be holding a different brief at 15:00. Each record says which version it is: the issue id (printed.js, the
// build and the forecast's issue time) and a short check of the spot's own forecast data (a 32-bit FNV-1a
// hash of it: enough to tell two versions apart, not a security seal). The leader can tick "I have read
// version X"; the tick is kept in this browser's local storage (ACK_KEY) and sent nowhere, so it is a
// reminder for that leader, not a record anyone else can see. A later version shows the tick as for an
// earlier one, and asks for a fresh read. No accounts, no notifications.
//
// A plain script, as record.js: everything inside `BriefAck`; Node requires it for the tests
// (tests/site_brief.test.cjs). record.js calls BriefAck.draw where it is loaded, and draws as before where not.
const BriefAck = (() => {
  const ACK_KEY = 'dipcast.briefacks', MAX = 30;
  const ISO = /^\d{4}-\d{2}-\d{2}$/, HASH = /^[0-9a-f]{8}$/;
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

  // ------------------------------------------------------------------ the version
  // JSON with its keys in order, so the same data always gives the same text, whatever order it came in.
  const canon = v => Array.isArray(v) ? `[${v.map(canon).join(',')}]`
    : v && typeof v === 'object' ? `{${Object.keys(v).sort().filter(k => v[k] !== undefined).map(k => `${JSON.stringify(k)}:${canon(v[k])}`).join(',')}}`
    : JSON.stringify(v ?? null);
  // FNV-1a, 32 bits, over the text's UTF-16 code units: eight hex digits.
  function fnv(text) {
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h.toString(16).padStart(8, '0');
  }
  // The version of the brief for spot s on day iso: the issue id and the check of what the record rests on
  // (the spot's whole entry in spots.json, the day and the forecast's issue time).
  const version = (s, iso, generatedAt, issue) => ({ issue: String(issue), hash: fnv(canon({ spot: s, day: iso, generated_at: generatedAt })) });
  const label = v => `${v.issue} · ${v.hash}`;

  // ------------------------------------------------------------------ the ticks kept
  // What is stored: [{spot, day, issue, hash, at}], newest last, at most MAX. Anything else reads as no
  // tick, rather than stop the page.
  const ok = x => !!x && typeof x === 'object' && typeof x.spot === 'string' && x.spot.length > 0 && x.spot.length <= 100
    && typeof x.day === 'string' && ISO.test(x.day) && typeof x.issue === 'string' && x.issue.length > 0 && x.issue.length <= 80
    && typeof x.hash === 'string' && HASH.test(x.hash) && Number.isFinite(x.at);
  function readAcks(text) {
    let v; try { v = JSON.parse(text); } catch (e) { return []; }
    return Array.isArray(v) ? v.filter(ok).slice(-MAX) : [];
  }
  // Tick (on) or untick this version for this spot and day. One tick a spot and day: a new one replaces any
  // for an earlier version.
  function setAck(acks, spot, day, v, on, at) {
    const rest = acks.filter(a => !(a.spot === spot && a.day === day));
    return (on ? [...rest, { spot, day, issue: v.issue, hash: v.hash, at }] : rest).slice(-MAX);
  }
  // Where this leader stands with this version: 'read' (ticked for it), 'older' (ticked for another
  // version of the same spot and day: the brief has changed since), or 'none'; with the tick, if any.
  function ackState(acks, spot, day, v) {
    const a = [...acks].reverse().find(x => x.spot === spot && x.day === day);
    if (!a) return { state: 'none', ack: null };
    return { state: a.issue === v.issue && a.hash === v.hash ? 'read' : 'older', ack: a };
  }

  // ------------------------------------------------------------------ the box
  const when = at => { const d = new Date(at);
    return `${d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })} at ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`; };
  // The box under the record, on screen only (never in the printed copy). st: ackState's; stored: whether
  // the browser keeps the tick (false: storage blocked, so it lasts for this page only).
  function section(v, st, stored = true) {
    const said = st.state === 'read' ? `You ticked this version as read on ${esc(when(st.ack.at))}.`
      : st.state === 'older' ? `You ticked an earlier version (${esc(label(st.ack))}) as read on ${esc(when(st.ack.at))}. The brief has changed since: read this version before you tick it.`
      : 'Not ticked as read on this device.';
    return `<section class="screen-only brief-ack" aria-labelledby="brief-ack-h"><h2 id="brief-ack-h">Version of this brief</h2>`
      + `<p>Version <b>${esc(label(v))}</b>: the issue id, then a check of the forecast data this record rests on. A new forecast makes a new version.</p>`
      + `<p class="brief-ack-tick"><label><input type="checkbox" id="brief-ack"${st.state === 'read' ? ' checked' : ''}> I have read version ${esc(v.hash)}</label></p>`
      + `<p class="r-note" id="brief-ack-said" role="status">${said}</p>`
      + `<p class="r-note">A prototype. The tick is kept only in this browser${stored ? '' : ', and here only until the page closes, as this browser does not let the page keep it'}. `
      + 'Nothing is sent to SwimSignal, your club or anyone else, so nobody else can see it: it is a reminder for you, not a record of who read what.</p></section>';
  }

  // ------------------------------------------------------------------ in the page
  let MEM = null;   // the ticks while storage is blocked
  function load() { try { return readAcks(localStorage.getItem(ACK_KEY)); } catch (e) { return MEM || []; } }
  function save(acks) { try { localStorage.setItem(ACK_KEY, JSON.stringify(acks)); return true; } catch (e) { MEM = acks; return false; } }
  function canStore() { try { localStorage.getItem(ACK_KEY); return true; } catch (e) { return false; } }
  // Under the record in `out`, for spot s on day iso (record.js, draw).
  function draw(out, s, iso, data, issue) {
    const v = version(s, iso, data.generated_at, issue), stored = canStore();
    const put = () => { const old = out.querySelector('.brief-ack'); if (old) old.remove();
      out.insertAdjacentHTML('beforeend', section(v, ackState(load(), s.id, iso, v), stored));
      out.querySelector('#brief-ack').addEventListener('change', e => { save(setAck(load(), s.id, iso, v, e.target.checked, Date.now())); put();
        const b = out.querySelector('#brief-ack'); if (b) b.focus(); }); };
    put();
  }

  return { ACK_KEY, MAX, canon, fnv, version, label, readAcks, setAck, ackState, section, draw };
})();

if (typeof module === 'object' && module.exports) module.exports = BriefAck;
