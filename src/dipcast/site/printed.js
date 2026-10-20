// What the two pages made to be printed carry, the decision record (record.js) and the sites view (sites.js):
// an issue id, and the credits for the data their spots use (docs/ORGANISER-PIVOT-2026-10.md, OP2 and OP3).
//
// The issue id is the build's commit and the forecast's issue time in UTC, to the minute: 3ed1b5a-20261020T1216Z.
// Every page from one build carries the same id, and the next build a new one, so a printed copy can be
// matched to the forecast log (forecast_log: build_runs.built_at is the same generated_at, and every logged
// forecast's version holds the same commit).
//
// The credits are the build's own (scripts/build_site.py, data_credits: `sources`, `companies`, `licences`),
// one source a line, each with its licence and what SwimSignal changed, for the sources these spots use.
// Licences are written out, since a printed link cannot be followed.
//
// A plain script: the pages load levels.js first and this file finds its names there; Node requires it for
// the tests (tests/site_record.test.cjs, tests/site_sites.test.cjs).
const Printed = (() => {
  const node = typeof module === 'object' && module.exports;
  const R = node ? require('./levels.js') : { daily };   // levels.js's globals
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nil = v => v === null || v === undefined;
  const and = xs => xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`;
  const bare = u => String(u).replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');

  // The build's commit: spots.json's `commit`, else the code part of a spot's model version
  // ("code=0.1.0+3ed1b5a"), from files written before `commit` was.
  function commit(data) {
    if (data.commit) return String(data.commit);
    for (const s of data.spots || []) {
      const m = /code=[^;+]*\+([^;]+)/.exec(((s && s.assumptions) || {}).version || '');
      if (m) return m[1];
    }
    return 'nogit';
  }
  function issueId(data) {
    const t = new Date(data.generated_at);
    if (Number.isNaN(t.getTime())) return commit(data);
    const p = n => String(n).padStart(2, '0');
    return `${commit(data)}-${t.getUTCFullYear()}${p(t.getUTCMonth() + 1)}${p(t.getUTCDate())}T${p(t.getUTCHours())}${p(t.getUTCMinutes())}Z`;
  }

  // What the spots draw on: each spot's own sources, and `extra` for what a page shows beyond them
  // (the record's river level and flood alerts are "gauge").
  function uses(spots, extra = []) {
    const u = new Set(['always', ...extra]), companies = new Set();
    let unnamed = false;   // overflows upstream, but a file from before upstream_summary.companies, and no contributors
    for (const s of spots) {
      const up = s.upstream_summary || {};
      const cs = up.companies || (s.contributors ? s.contributors.map(c => c.company) : null);
      if (cs) { for (const c of cs) if (c) companies.add(String(c)); }
      else if (up.overflows) unnamed = true;
      if (up.overflows) u.add('model');
      if ((s.days || []).some(d => !nil(d.rain_48h_mm)) || R.daily(s)) u.add('rain');
      if (up.through_lake || (s.contributors || []).some(c => c.lake_distance_km > 0)) u.add('lake');
      if (s.source === 'openstreetmap') u.add('osm');
    }
    return { u, companies, unnamed };
  }

  // The credits as a heading, one source a line, then the licences written out, that no provider endorses
  // SwimSignal, and where the full notices are. base: the site's address, for that last line.
  function credits(data, spots, base, extra = []) {
    const C = data.credits || {}, full = C.full || `${base}terms.html#data`;
    // Printed, the heading runs into the text (credits-run), which saves a line on a full second page.
    const head = '<h3 class="credits-h">Data credits</h3>', run = '<span class="credits-run">Data credits. </span>';
    if (!Array.isArray(C.sources)) {   // a file from before the sources were written: the one line every data file carries
      return head + `<div class="credits"><p>${run}${C.attribution ? `${esc(C.attribution)} ${esc(C.modified || '')} ` : ''}Full credits: ${esc(bare(full))}.</p></div>`;
    }
    const { u, companies, unnamed } = uses(spots, extra);
    // Where a spot's companies are not known, every company is credited: a credit too many, never one too few.
    const named = [...new Set([...(unnamed ? Object.keys(C.companies || {}) : []), ...companies])].map(c => (C.companies || {})[c])
      .filter(Boolean).sort((a, b) => a.localeCompare(b, 'en-GB'));
    if (named.length) u.add('overflows');
    const shown = C.sources.filter(x => u.has(x.use));
    const lic = [...new Set(shown.map(x => x.licence).filter(Boolean))];
    const line = x => `<li>${esc(x.credit.replace('{companies}', and(named)))}${x.licence ? `, ${esc(x.licence)}` : ''}. ${esc(x.changed)}</li>`;
    return head + `<div class="credits">${run}<ul>${shown.map(line).join(' ')}</ul>`
      + `<p>Licences: ${lic.map(l => `${esc(l)}, ${esc(bare((C.licences || {})[l] || ''))}`).join('; ')}. `
      + `${esc(C.endorsement || C.modified || '')} Full credits: ${esc(bare(full))}.</p></div>`;
  }

  return { issueId, commit, uses, credits };
})();

if (typeof module === 'object' && module.exports) module.exports = Printed;
