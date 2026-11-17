// A course briefing (a prototype, not built into the site): one event's route, cut into sections where the
// water-quality evidence changes, replayed on a few past dates. It draws course.json, which
// scripts/course_briefing.py makes with the site's own route tool, upstream trace and exposure index, and the
// organiser briefing's limits wording (docs/COURSE-BRIEFING-HENLEY-2026-11.md).
//
// What the page never gives: an E. coli reading or range, a level for a section, or a verdict. A level is shown
// only where one was issued, at the listed spot, with its issue id. Everything else is laid out now from records
// and is labelled a reconstruction.
//
// A plain script, as organisers.js: everything inside `CourseBrief`; Node requires it for the tests
// (tests/site_course_briefing.test.cjs). Overflow names are levels.js's plain names, so they match the site's.
const CourseBrief = (() => {
  const L = typeof plainName === 'function' ? { plainName, HEAD_SCOPE, WEIGHT_SAID } : require('../../src/dipcast/site/levels.js');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const RECON = 'Reconstruction';
  const LEVEL = { low: 'Low', moderate: 'Moderate', high: 'High', 'very high': 'Very high' };

  // ------------------------------------------------------------------ words
  // The stamps in course.json are UK local times with their offset ("2024-07-06T11:45+01:00"): the day and the
  // clock are read from the text, so the page says the same on a device in any time zone.
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const parts = iso => { const [y, m, d] = iso.slice(0, 10).split('-').map(Number); return { y, m, d, wd: new Date(Date.UTC(y, m - 1, d)).getUTCDay() }; };
  const longDay = iso => { const p = parts(iso); return `${DAYS[p.wd]} ${p.d} ${MONTHS[p.m - 1]} ${p.y}`; };
  const shortDay = iso => { const p = parts(iso); return `${p.d} ${MONTHS[p.m - 1]}`; };
  const clock = iso => iso.slice(11, 16);
  // A time on the replayed day is its clock; on another day, the day too.
  const at = (iso, day) => iso.slice(0, 10) === day ? clock(iso) : `${clock(iso)} on ${shortDay(iso)}`;
  // A spill's two times: the day said once where both are on it.
  const ran2 = (a, b, day) => a.slice(0, 10) === b.slice(0, 10) && a.slice(0, 10) !== day ? `${clock(a)} to ${clock(b)} on ${shortDay(a)}` : `${at(a, day)} to ${at(b, day)}`;
  const km = v => `${Number(v).toFixed(2)} km`;
  const pct = w => w < 0.005 ? 'under 1%' : `${Math.round(w * 100)}%`;
  const count = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const name = n => L.plainName(n);
  // A section's place on the course, as a swimmer meets it: from the start, upstream to the finish.
  const span = (s, total) => s.from_km === 0 ? `Start to ${km(s.to_km)}` : s.to_km >= total ? `${km(s.from_km)} to the finish` : `${km(s.from_km)} to ${km(s.to_km)}`;
  const metres = s => { const m = Math.round((s.to_km - s.from_km) * 100) * 10; return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${m} m`; };
  const kind = s => s.adds.length ? 'adds' : s.unresolved.length ? 'unresolved' : 'same';
  const KIND_SAID = { adds: 'One more overflow upstream', unresolved: 'Unresolved', same: 'Nothing added' };

  // ------------------------------------------------------------------ the answer
  // Where the evidence changes, in sentences, from the sections alone.
  function answer(doc) {
    const flow = new Map(doc.inflows.map(f => [f.site_id, f]));
    const out = [];
    for (const s of doc.sections) {
      const k = kind(s);
      if (k === 'adds') out.push(`The maps place ${s.adds.map(i => name(flow.get(i).site_name)).join(' and ')} upstream of the first ${metres(s)} of the swim.`);
      else if (k === 'unresolved') out.push(`Whether it also reaches the next ${metres(s)} is not known.`);
      else out.push(`The last ${km(s.to_km - s.from_km)} to the finish is above it.`);
    }
    const n = doc.sections.filter(s => kind(s) !== 'same').length;
    return `${n ? 'The evidence changes near the start.' : 'The evidence is the same along the whole course.'} ${out.join(' ')}`;
  }

  // ------------------------------------------------------------------ what was issued
  function issued(doc, d, walkthrough = false) {
    const head = `<h2${walkthrough ? ' id="replay-step" tabindex="-1"' : ''}>${walkthrough ? '' : '<span class="c-n">2</span>'}What the Henley page showed</h2>`;
    if (!d.issued) {
      return `${head}<div class="c-live"><p class="c-none"><b>Nothing was issued.</b> ${esc(d.no_issue_why)}</p>`
        + '<p class="small muted">There is no SwimSignal forecast or live status from that day.</p></div>';
    }
    const r = d.issued, day = (r.days || []).find(x => x.date === d.day) || {};
    const cls = String(r.level).replace(/\s/g, '');
    const lv = LEVEL[r.level] ? `${LEVEL[r.level]} ${L.HEAD_SCOPE}` : esc(r.level);
    return `${head}<div class="c-live"><p class="c-level ${esc(cls)}">${lv}</p>`
      + `<p>As issued at ${esc(clock(r.issued_at))} on ${esc(longDay(r.issued_at))}, for the one pin near Henley Bridge, ${esc(String(doc.pin_above_finish_m))} m upstream of the finish.</p>`
      + '<dl class="fields">'
      + `<dt>Exposure index for the day</dt><dd>${esc(day.score ?? 'Not kept')} of 100, as issued. A score, not a probability.</dd>`
      + `<dt>Live status</dt><dd>${esc(r.reporting)} of ${esc(r.upstream)} overflows upstream gave a status at the last poll. ${r.discharging ? `${esc(r.discharging)} spilling.` : 'None spilling.'}${r.recent ? ` ${count(r.recent, 'recent spill', 'recent spills')} counted.` : ''}</dd>`
      + `<dt>Issue</dt><dd><code>${esc(r.issue)}</code></dd></dl>`
      + '<p class="small muted">These figures describe the Henley Bridge pin.</p></div>';
  }

  // ------------------------------------------------------------------ along the whole course
  const spillLine = (s, d, names, where) => {
    const ran = s.end ? esc(ran2(s.start, s.end, d.day)) : `from ${esc(at(s.start, d.day))}, still running at ${esc(clock(d.as_of))}`;
    return `<li><b>${esc(name(names[s.site_id]))}</b>${where ? `, ${esc(where)}` : ''}: ${ran}. Model weight ${esc(pct(s.weight))}. <span class="c-src">${esc(s.source)}.</span></li>`;
  };
  // Upstream of every section: the spills recorded in the 48 hours before, and the monitors with no reading.
  function whole(doc, d) {
    const by = new Map(doc.upstream.map(r => [r.site_id, r]));
    const where = id => by.has(id) ? `${by.get(id).km} km above the finish` : '';
    const main = d.spills.filter(s => !s.side), shown = main.filter(s => s.weight >= 0.02), rest = main.length - shown.length;
    let spills;
    if (!main.length) spills = `<p>No spill recorded at any of the ${doc.upstream.length} in the ${doc.recent_h} hours before ${esc(clock(d.as_of))}.</p>`;
    else {
      spills = `<p>${count(main.length, 'spill', 'spills')} recorded in the ${doc.recent_h} hours before ${esc(clock(d.as_of))}${shown.length < main.length ? `, ${shown.length ? `${shown.length} at overflows with 2% weight or more` : 'none at an overflow with 2% weight or more'}` : ''}.</p>`
        + (shown.length ? `<ul class="c-list">${shown.map(s => spillLine(s, d, d.names, where(s.site_id))).join('')}</ul>` : '')
        + (rest ? `<p class="small muted">${count(rest, 'more', 'more')} further up, each under 2% weight.</p>` : '');
    }
    let mon;
    if (!d.monitors) mon = '<p><b>Which monitors were reporting: not known.</b> SwimSignal was not polling the live feed on this date.</p>';
    else {
      const off = Object.entries(d.monitors.not_reporting).filter(([, v]) => !v.side);
      mon = off.length ? `<p><b>${count(off.length, 'monitor', 'monitors')} without a full day of readings</b>, over ${d.monitors.polls} polls:</p><ul class="c-list">${off.map(([id, v]) => {
        const r = by.get(id) || {};
        return `<li><b>${esc(name(r.site_name || id))}</b>, ${esc(where(id))}: ${v.state === 'none' ? `no reading at any of ${v.unknown} polls` : `no reading at ${v.unknown} of ${v.known + v.unknown} polls`}. Model weight ${esc(pct(r.weight || 0))}${r.weight === Math.max(...doc.upstream.map(x => x.weight)) ? `, the largest of the ${doc.upstream.length}` : ''}. Missing data never means low risk.</li>`;
      }).join('')}</ul>`
        : `<p>Every one of them gave a status at every poll that day (${d.monitors.polls} polls).</p>`;
    }
    return `<h4>Upstream of every section</h4><p>${doc.upstream.length} monitored storm overflows, all ${esc(doc.companies.join(' and '))}'s. The nearest is ${esc(name(doc.upstream.slice().sort((a, b) => a.km - b.km)[0].site_name))}, ${esc(String(doc.upstream.slice().sort((a, b) => a.km - b.km)[0].km))} km above the finish.</p>${spills}${mon}`;
  }

  // ------------------------------------------------------------------ one section
  function section(doc, s, i, d) {
    const k = kind(s), flow = new Map(doc.inflows.map(f => [f.site_id, f]));
    const ids = k === 'adds' ? s.adds : s.unresolved;
    const lines = ids.map(id => {
      const f = flow.get(id), sp = d.spills.filter(x => x.site_id === id), m = d.monitors && d.monitors.not_reporting[id];
      const state = sp.length ? `recorded spilling ${sp.map(x => x.end ? esc(ran2(x.start, x.end, d.day)) : `from ${esc(at(x.start, d.day))}`).join(' and ')}. <span class="c-src">${esc(sp[0].source)}.</span>`
        : !d.monitors ? 'no spill in the record for the 48 hours before. Whether its monitor was reporting is not known.'
        : m ? `no reading at ${m.state === 'none' ? 'any' : m.unknown} of the day's polls. Missing data never means low risk.`
        : `a status at every poll that day, none of them spilling. Its last recorded spill began on ${esc(shortDay(f.last_event))} ${esc(f.last_event.slice(0, 4))}.`;
      return `<p><b>${esc(name(f.site_name))}</b> on this date: ${state}</p>`;
    }).join('');
    const body = k === 'adds'
      ? `<p>Upstream of this section: the ${doc.upstream.length} above, and ${s.adds.map(id => `<b>${esc(name(flow.get(id).site_name))}</b>`).join(' and ')}. Its stream meets the river here, ${esc(String(flow.get(s.adds[0]).km))} km below the works. Model weight at the start: ${esc(pct(flow.get(s.adds[0]).weight))}.</p>${lines}`
      : k === 'unresolved'
        ? `<p><b>Not resolved.</b> A ditch on the map may carry ${s.unresolved.map(id => esc(name(flow.get(id).site_name))).join(' and ')} water to the river as far up as here. The link is not shown either way, so this section is not counted as above the works or below it.</p>${lines}`
        : `<p>Upstream of this section: the ${doc.upstream.length} above, and nothing more. Every mapped mouth of the works' stream is below here.</p>`;
    return `<li class="c-sec ${k}"><h4><span class="c-n">${i + 1}</span>${esc(span(s, doc.km))}</h4><p class="c-kind">${esc(KIND_SAID[k])} · ${esc(metres(s))}</p>${body}</li>`;
  }

  function course(doc, d) {
    return `<h3>The course, section by section</h3>`
      + `<p class="c-tag">${RECON}. Prepared on ${esc(shortDay(doc.made))} ${esc(doc.made.slice(0, 4))}. Spill times are shown up to ${esc(clock(d.as_of))} on ${esc(longDay(d.day))}. ${d.monitors ? 'Monitor coverage uses the full day of polls, including any after that time.' : 'The Environment Agency spill records were published after this date.'} SwimSignal issued no course briefing that day.</p>`
      + `<div class="c-live">${whole(doc, d)}<ol class="c-secs">${doc.sections.map((s, i) => section(doc, s, i, d)).join('')}</ol>`
      + `<p class="c-not"><b>Not covered in any section:</b> treated effluent from the works, a discharge that runs all the time, which this feed does not monitor and whose outfall was not checked; outfalls no one monitors; runoff from farms and roads; and how far a stream's water spreads across the river before it mixes.</p></div>`;
  }

  // ------------------------------------------------------------------ the figures behind it
  function figures(doc, d) {
    const beyond = doc.beyond_start.length;
    return '<details class="fold"><summary>The figures behind it</summary>'
      + `<p class="c-tag">${RECON}. Not issued on the day.</p>`
      + `<p>The exposure index for ${esc(longDay(d.day))}, rebuilt using spill records for the whole day and the days before: <b>${d.rebuilt.finish} of 100 at the finish end, ${d.rebuilt.start} of 100 at the start end.</b> A score, not a probability.</p>`
      + '<p class="small muted">It is the site\'s own index with the same weights and travel times. It counts water the model has arriving on that day, so a spill far upstream counts on a later day. Where travel time is a few hours, the model moves part of a spill onto the next day, so the two ends can differ a little from one spill.</p>'
      + `<p class="small muted">${esc(L.WEIGHT_SAID)}</p>`
      + `<p class="small muted">Counts: ${doc.upstream.length} overflows are within the forecast's 60 km of the finish. ${beyond ? `${count(beyond, 'of them is', 'of them are')} past 60 km from the start, 2.1 km further down, so the start's own count is ${doc.start_counts}.` : ''}</p></details>`;
  }

  // ------------------------------------------------------------------ the drawing
  function plate(doc) {
    const p = doc.plate;
    if (!p) return '';
    const secs = p.sections.map((s, i) => `<path class="c-course ${kind(doc.sections[i])}" d="${s.d}"/>`).join('');
    const dot = m => {
      const [x, y] = m.at;
      if (m.kind === 'mouth') return `<circle class="c-mouth ${m.link}" cx="${x}" cy="${y}" r="16"><title>${esc(m.label)} (${m.link === 'mapped' ? 'joined on the map' : 'possible link'})</title></circle>`;
      if (m.kind === 'cut') return `<circle class="c-cut" cx="${x}" cy="${y}" r="20"/><text class="c-lab" x="${x + 44}" y="${y + 16}">${esc(m.label)}</text>`;
      if (m.kind === 'works') return `<rect class="c-works" x="${x - 20}" y="${y - 20}" width="40" height="40"/><text class="c-lab" x="${x + 44}" y="${y + 16}">${esc(name(m.label))}</text>`;
      return `<circle class="c-end" cx="${x}" cy="${y}" r="30"/><text class="c-lab strong" x="${x + 56}" y="${y + 18}">${esc(m.label)}</text>`;
    };
    return `<figure class="c-plate"><svg viewBox="0 0 ${p.w} ${p.h}" role="img" aria-label="The course on the Thames at Henley, from the start by Temple Island up to the finish below Henley Bridge, with the stream from Henley sewage works and its mouths."><path class="c-water" fill-rule="evenodd" d="${p.water}"/><path class="c-ditch" d="${p.ditches}"/><path class="c-traced" d="${p.traced}"/>${secs}${p.marks.map(dot).join('')}</svg>`
      + `<figcaption><b>The course and the works' stream.</b> North is up. The heavy line is the course: solid where the works' overflow is upstream, dashed where that is unresolved, thin where it is not. Filled dots are mouths joined to the works' stream on the map. The open dot is the possible link. Thin dashed lines are the river lines SwimSignal traces. ${esc(p.credit)}</figcaption></figure>`;
  }

  // ------------------------------------------------------------------ the rest
  function upstream(doc) {
    const top = doc.upstream.slice(0, 8);
    return '<h2><span class="c-n">3</span>The overflows upstream of the whole course</h2>'
      + `<p>The eight with the most weight at the finish, of ${doc.upstream.length}. Weight does not change with the weather.</p>`
      + '<div class="tw"><table><thead><tr><th>Overflow</th><th>Above the finish</th><th>Weight</th></tr></thead><tbody>'
      + top.map(r => `<tr><td>${esc(name(r.site_name))}<span class="c-own">${esc(r.site_name)}${r.water ? `, to ${esc(r.water)}` : ''}</span></td><td>${esc(String(r.km))} km</td><td>${esc(pct(r.weight))}</td></tr>`).join('')
      + `</tbody></table></div><p class="small muted">${esc(L.WEIGHT_SAID)}</p>`;
  }

  function observed(doc) {
    const bw = doc.bathing_waters.map(b => `${esc(b.name)}${b.km_above_finish === null ? '' : `, ${esc(String(b.km_above_finish))} km above the finish`}`).join('; ');
    const polls = doc.polls ? `<p class="small muted">Polls: in the 30 days to ${esc(shortDay(doc.polls.to))}, the build read ${esc(doc.polls.company)}'s feed ${doc.polls.polls} times. Half the gaps between polls were under ${esc(String(doc.polls.median_gap_h))} hours. ${doc.polls.gaps_over_6h} gaps were over 6 hours, the longest ${esc(String(doc.polls.longest_gap_h))} hours.</p>` : '';
    return '<h2><span class="c-n">4</span>What can be observed here</h2><dl class="fields">'
      + doc.observations.map(o => `<dt>${esc(o.what)}</dt><dd>${esc(o.where.replace(/\.$/, ''))}. ${esc(o.source.replace(/\.$/, ''))}. <span class="muted">${esc(o.limit)}</span></dd>`).join('')
      + `</dl><p class="small muted">Bathing waters upstream, by river: ${bw}.</p>${polls}`;
  }

  function limits(doc) {
    return '<h2>What this is, and who decides</h2>'
      + `<p>${esc(doc.limits)}</p><p>${esc(doc.decides)}</p>`
      + '<p>This page gives no E. coli reading and no range. The Thames is a large river, where SwimSignal\'s range test was weakest.</p>';
  }

  function facts(doc) {
    const c = doc.course, w = doc.inflows[0];
    const ret = w && w.returns ? w.returns.map(r => `${r.year}: ${r.spills === null ? 'no figure' : `${count(r.spills, 'spill', 'spills')}, ${count(r.hours, 'hour', 'hours')}`}`).join('; ') : '';
    return '<details class="fold"><summary>How the course was placed</summary><dl class="fields">'
      + `<dt>The organiser's words</dt><dd>"${esc(c.said)}". <a href="${esc(c.source_url)}">${esc(c.organiser)}</a>, read ${esc(shortDay(c.source_read))} ${esc(c.source_read.slice(0, 4))}. The page gives no coordinates.</dd>`
      + `<dt>Start</dt><dd>${esc(doc.ends.start.how)} <span class="muted">${esc(doc.ends.start.sure)}</span></dd>`
      + `<dt>Finish</dt><dd>${esc(doc.ends.finish.how)} <span class="muted">${esc(doc.ends.finish.sure)}</span></dd>`
      + (w ? `<dt>${esc(name(w.site_name))}</dt><dd>${esc(w.company)} gives its receiving water as ${esc(w.water)}. Annual returns: ${esc(ret)}.</dd>` : '')
      + `<dt>The stream's mouths</dt><dd>${doc.mouths.map(m => `${esc(m.name)}: ${m.on_course ? `${esc(km(m.km))} from the start` : 'below the start'}, ${m.link === 'mapped' ? 'joined on the map' : 'possible link'}`).join('. ')}.</dd>`
      + '</dl></details>';
  }

  // ------------------------------------------------------------------ the page
  const pick = (doc, id) => doc.dates.find(d => d.id === id) || doc.dates[0];
  function dateButtons(doc, d, walkthrough = false) {
    return `<div class="c-dates" role="group" aria-label="Date">${doc.dates.map(x => `<button type="button" class="btn${x.id === d.id ? ' on' : ''}" data-date="${esc(x.id)}" aria-pressed="${x.id === d.id}">${walkthrough ? `<b>${esc(longDay(x.day))}</b>` : `<b>${esc(x.title)}</b><span>${esc(longDay(x.day))}</span>`}</button>`).join('')}</div>`;
  }

  function picker(doc, d) {
    return '<h2><span class="c-n">1</span>Pick a date</h2><p class="small muted">Three past dates. Not today, and not a forecast for the event.</p>'
      + dateButtons(doc, d)
      + `<p class="c-asof" role="status">Shown as at <b>${esc(clock(d.as_of))} on ${esc(longDay(d.day))}</b>.</p>`;
  }

  // ------------------------------------------------------------------ the reveal: three questions
  // Every line says what kind of thing it is: something a monitor reported and SwimSignal had received
  // (Observation), a connection worked out from the river network and maps (Modelled connection), a place fixed
  // by reading (Inferred), a record published afterwards (Later record), or nothing (Unknown).
  const tag = (k, html) => `<li><span class="c-what">${k}.</span> ${html}</li>`;
  const stamp = (iso, d) => iso ? esc(at(iso, d.day)) : 'no poll';
  const mouthSpan = doc => { const on = doc.mouths.filter(m => m.on_course && m.link === 'mapped').map(m => m.km); return on.length ? `${km(Math.min(...on))} to ${km(Math.max(...on))} from the start` : 'by the start'; };
  const modelled = doc => tag('Modelled connection', `${esc(answer(doc))} <span class="c-src">SwimSignal's river network and OS OpenMap Local.</span>`)
    + tag('Inferred', `The start and the finish. ${esc(doc.ends.start.sure)} ${esc(doc.ends.finish.sure)}`);
  const unknownAlways = doc => {
    const un = doc.sections.find(x => kind(x) === 'unresolved');
    return (un ? tag('Unknown', `Whether the works' water reaches ${esc(span(un, doc.km).toLowerCase())}. The Fawley Court link is unresolved.`) : '')
      + tag('Unknown', 'Where exactly the start and finish are: both are inferred from the organiser\'s words.')
      + tag('Unknown', 'Treated effluent from the works, outfalls no one monitors, runoff, and how far a stream\'s water spreads across the river.');
  };

  // The course as SwimSignal had received it by the decision time (course.json's `replay`: scripts/course_briefing.py,
  // replay_at). Nothing received later is in it.
  function sameTime(doc, d) {
    const r = d.replay, t = esc(clock(d.as_of));
    const lost = r.unknown.map(u => tag('Observation', `<b>${esc(name(u.site_name))}</b>, ${esc(String(u.km))} km above the finish: no status at the ${stamp(r.last_poll, d)} poll. ${u.last_known_at ? `A status was last received at ${esc(at(u.last_known_at, d.day))}, ${count(u.unknown_polls, 'poll', 'polls')} earlier.` : `No status received in the ${r.window_h} hours before.`} Model weight ${esc(pct(u.weight || 0))}. Upstream of the whole course.`)).join('');
    const spilling = r.spilling.map(u => tag('Observation', `<b>${esc(name(u.site_name))}</b>, ${esc(String(u.km))} km above the finish: spilling at the ${stamp(r.last_poll, d)} poll. Model weight ${esc(pct(u.weight || 0))}.`)).join('');
    const got = r.events.map(e => tag('Observation', `<b>${esc(name(e.site_name))}</b>${e.side ? '' : `, ${esc(String(e.km))} km above the finish`}: spilled ${e.end ? esc(ran2(e.start, e.end, d.day)) : `from ${esc(at(e.start, d.day))}`}. SwimSignal had it by ${esc(at(e.received_by, d.day))}.`)).join('');
    const side = r.side.map(u => tag('Observation', `<b>${esc(name(u.site_name))}</b>, upstream of the first section only: ${u.state === 'not spilling' ? `not spilling at the ${stamp(u.last_known_at, d)} poll` : u.state === 'spilling' ? `spilling at the ${stamp(u.last_known_at, d)} poll` : u.state === 'unproven' ? `a status arrived at the ${stamp(r.last_poll, d)} poll, but the archive cannot show what it was` : `no status at the ${stamp(r.last_poll, d)} poll. Missing data never means low risk`}.`)).join('');
    const hazy = [...(r.unproven_state || []), ...r.side.filter(u => u.state === 'unproven')];
    const quiet = !hazy.length && !r.unknown.length && !r.spilling.length && !r.events.length && r.side.every(u => u.state === 'not spilling');
    const all = tag('Observation', `${r.known} of ${r.counted} overflows upstream of the whole course gave a status at the ${stamp(r.last_poll, d)} poll${r.spilling.length ? '' : ', none spilling'}. <span class="c-src">${esc(doc.companies.join(', '))}'s live feed, as SwimSignal polled it.</span>`);
    const where = `<h3>Where does the evidence change?</h3>${quiet ? `<p><b>Nothing received by ${t} differs along the course.</b> The map still does.</p>` : ''}<ul class="c-ans">${modelled(doc)}${all}${lost}${spilling}${got}${side}</ul>`;
    const places = [...r.unknown, ...r.spilling].map(u => `<li><b>${esc(name(u.site_name))}</b>, ${esc(String(u.km))} km above the finish. Its outfall on the bank, and its status on ${esc(doc.companies[0])}'s own storm discharge map.</li>`).join('')
      + doc.inflows.map(f => `<li><b>The mouths of the works' stream</b>, ${esc(mouthSpan(doc))}, on the Buckinghamshire bank. And ${esc(name(f.site_name))} on ${esc(f.company)}'s map.</li>`).join('');
    const check = `<h3>What could I check there?</h3><p class="small muted">Places and sources, not instructions.</p><ul class="c-ans">${places}</ul>`;
    const gap = r.prev_poll ? tag('Unknown', `What happened between polls. The one before ${stamp(r.last_poll, d)} was at ${esc(at(r.prev_poll, d.day))}.`) : '';
    const unknown = `<h3>What is still unknown?</h3><ul class="c-ans">`
      + r.unknown.map(u => tag('Unknown', `Whether <b>${esc(name(u.site_name))}</b> was spilling. Missing data never means low risk.`)).join('')
      + hazy.map(u => tag('Unknown', `Whether <b>${esc(name(u.site_name))}</b> was spilling at the ${stamp(r.last_poll, d)} poll. A status arrived, but the archive keeps only when a state was last seen, and that was after ${t}. Not counted as spilling or as not spilling.`)).join('')
      + gap + (r.unproven ? tag('Unknown', `${count(r.unproven, 'spill', 'spills')} that the archive cannot show SwimSignal had received by ${t}. Left out.`) : '')
      + unknownAlways(doc) + '</ul>';
    return `<h2 id="replay-step" tabindex="-1">The course at the same time</h2>`
      + `<p class="c-tag">Only what SwimSignal had received by <b>${t} on ${esc(longDay(d.day))}</b>. ${count(r.polls, 'poll', 'polls')} of the live feed in the ${r.window_h} hours before, the last at ${stamp(r.last_poll, d)}. SwimSignal issued no course briefing that day: this is laid out now from its archive.</p>`
      + where + check + unknown + plate(doc)
      + `<details class="fold"><summary>Later records, not available at ${t}</summary>${course(doc, d)}${figures(doc, d)}</details>`;
  }

  // A date before SwimSignal's archive: later records only, never a same-time comparison.
  function historical(doc, d) {
    const flow = new Map(doc.inflows.map(f => [f.site_id, f]));
    const side = d.spills.filter(x => x.side);
    const spilled = side.map(x => tag('Later record', `<b>${esc(name(flow.get(x.site_id).site_name))}</b>, upstream of the first section only: recorded spilling ${x.end ? esc(ran2(x.start, x.end, d.day)) : `from ${esc(at(x.start, d.day))}`}. <span class="c-src">${esc(x.source)}, published after the year ended.</span>`)).join('');
    const rest = d.spills.length - side.length;
    return `<h2 id="replay-step" tabindex="-1">Historical view: later records</h2>`
      + `<p class="c-tag"><b>Not a same-time comparison.</b> SwimSignal kept no archive in ${esc(d.day.slice(0, 4))}, so it cannot show what was known at ${esc(clock(d.as_of))}. These are records published afterwards. Use this date to see how evidence can differ along a course.</p>`
      + `<h3>Where does the evidence change?</h3><ul class="c-ans">${modelled(doc)}${spilled || tag('Later record', 'No spill recorded at the works in the 48 hours before.')}`
      + tag('Later record', `${count(rest, 'other spill', 'other spills')} recorded upstream of the whole course in the ${doc.recent_h} hours before, all further up.`) + '</ul>'
      + `<h3>What could I check there?</h3><p class="small muted">Places and sources, not instructions.</p><ul class="c-ans">${doc.inflows.map(f => `<li><b>The mouths of the works' stream</b>, ${esc(mouthSpan(doc))}, on the Buckinghamshire bank. And ${esc(name(f.site_name))} on ${esc(f.company)}'s map.</li>`).join('')}</ul>`
      + `<h3>What is still unknown?</h3><ul class="c-ans">${tag('Unknown', 'What anyone could have seen at the time. The live feed existed, but SwimSignal was not polling it, so which monitors were reporting is not known.')}${unknownAlways(doc)}</ul>`
      + plate(doc)
      + `<details class="fold"><summary>The later records in full</summary>${course(doc, d)}${figures(doc, d)}</details>`;
  }
  const reveal = (doc, d) => d.replay ? sameTime(doc, d) : historical(doc, d);

  // What a click does to the walkthrough: a new date, or going back, always returns to the archived pin.
  const step = (state, action) => action.type === 'reveal' ? { ...state, revealed: true }
    : action.type === 'date' ? { date: action.date, revealed: false } : { ...state, revealed: false };

  function renderWalkthrough(doc, d, revealed) {
    const cutoff = `${esc(clock(d.as_of))} on ${esc(longDay(d.day))}`;
    const controls = `<p class="c-actions"><a href="#date=${esc(d.id)}">Open full briefing</a></p>`;
    const intro = `<h1 tabindex="-1">${esc(doc.course.name)}: organiser walkthrough</h1>`
      + '<p class="dateline">A prototype, not published. Past dates on one course on the Thames.</p>'
      + '<p class="c-caveat"><b>A forecast and an evidence map, not a water test.</b> The organiser decides.</p>'
      + dateButtons(doc, d, true)
      + `<p class="c-asof">Decision time <b>${cutoff} (UK)</b></p>`;
    if (!revealed) {
      return intro + issued(doc, d, true)
        + '<p>What would you have checked, decided or told people at the time?</p>'
        + '<p class="c-actions"><button type="button" class="btn primary" data-reveal>Show the course evidence</button></p>'
        + controls;
    }
    return intro + reveal(doc, d)
      + '<p><b>Would this change what you check, decide or tell people?</b> Where on the course, and what evidence led you there?</p>'
      + '<p class="c-actions"><button type="button" class="btn" data-reset>Back to the Henley pin</button></p>'
      + limits(doc) + controls;
  }

  function render(doc, id) {
    const d = pick(doc, id), c = doc.course;
    return `<h1 tabindex="-1">${esc(c.name)}: course briefing</h1>`
      + `<p class="dateline">A prototype, not published. For the ${esc((c.length_m / 1000).toFixed(1))} km ${esc(c.river)} course of ${esc(c.organiser)}'s ${esc(c.name)}, next held ${esc(longDay(c.next_event))}.</p>`
      + `<p class="c-actions"><a href="#mode=walkthrough&amp;date=${esc(d.id)}">Run an organiser walkthrough</a></p>`
      + `<p class="lead">${esc(answer(doc))}</p>`
      + '<p class="c-caveat"><b>A forecast and an evidence map, not a water test.</b> The organiser decides.</p>'
      + plate(doc) + facts(doc) + picker(doc, d) + issued(doc, d) + reveal(doc, d).replace(plate(doc), '') + upstream(doc) + observed(doc) + limits(doc)
      + `<p class="note">Made ${esc(shortDay(doc.made))} ${esc(doc.made.slice(0, 4))} by <code>scripts/course_briefing.py</code>. Overflow status and locations: ${esc(doc.companies.join(', '))} (CC BY 4.0), changed by SwimSignal. Spill start and stop records and annual returns: Environment Agency, Open Government Licence v3.0. River lines and water: OS Open Rivers and OS OpenMap Local, contains OS data © Crown copyright and database right 2026. Landmarks: Historic England, National Heritage List for England, Open Government Licence v3.0.</p>`;
  }

  // In the page: draw, and redraw on a picked date, kept after the # so a walkthrough can be linked.
  function draw(root, doc) {
    const read = () => new URLSearchParams(location.hash.slice(1));
    let state = { date: null, revealed: false };
    const put = () => {
      const args = read(), date = pick(doc, args.get('date'));
      root.innerHTML = args.get('mode') === 'walkthrough' ? renderWalkthrough(doc, date, state.revealed) : render(doc, date.id);
    };
    root.addEventListener('click', e => {
      const b = e.target.closest('[data-date], [data-reveal], [data-reset]');
      if (!b) return;
      if (b.dataset.date) {
        const args = read();
        args.set('date', b.dataset.date);
        history.replaceState(null, '', `#${args}`);
      }
      state = step(state, b.dataset.date ? { type: 'date', date: b.dataset.date } : { type: b.hasAttribute('data-reveal') ? 'reveal' : 'reset' });
      put();
      root.querySelector(b.dataset.date ? '.c-dates .on' : '#replay-step')?.focus();
    });
    addEventListener('hashchange', () => {
      state = step(state, { type: 'reset' });
      put();
      root.querySelector('h1')?.focus();
    });
    put();
  }

  return { RECON, longDay, shortDay, clock, at, km, pct, span, kind, answer, issued, whole, section, course, figures, plate, upstream, observed, limits, facts, picker, sameTime, historical, reveal, step, renderWalkthrough, render, draw };
})();

if (typeof module === 'object' && module.exports) module.exports = CourseBrief;
