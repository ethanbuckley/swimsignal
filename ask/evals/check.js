// The grounded behaviour every answer must show, and each question's own expectations (questions.json).
// The same checks run on the mocked API (test/evals.test.js) and on the real one (scripts/eval.mjs --live),
// so a live run is scored by exactly what the tests hold the Worker to.

import { KIDS, NEVER } from '../src/answer.js';

// All the words the reader sees, the service's and the model's.
export const shownText = (a) => [a.summary, ...a.assumptions, ...a.unknown, ...a.notes,
  ...a.spots.flatMap((s) => [s.name, s.fit, ...s.facts.map((f) => `${f.text} (${f.source}${f.date ? ', ' + f.date : ''})`), ...s.unknown])].join('\n');
// The model's words only: the facts quote their sources, which may say "clean" ("Check, Clean, Dry").
const modelText = (a) => [a.summary, ...a.assumptions, ...a.unknown, ...a.spots.map((s) => s.fit)].join('\n');

// Problems with one answer, as sentences; none means it passed. run: { status, answer, refused } where
// refused counts the give_answer calls the Worker turned back (mocked runs only).
export function checkRun(q, run, { live = false } = {}) {
  const out = [];
  const e = q.expect || {};
  if (run.status !== 200) return [`status ${run.status}, not 200`];
  const a = run.answer;
  const model = modelText(a);
  const never = model.match(NEVER), kids = model.match(KIDS);
  if (never) out.push(`the model's words say "${never[0]}"`);
  if (kids) out.push(`the model's words say "${kids[0]}"`);
  for (const s of a.spots) {
    if (s.facts[0]?.topic !== 'official') out.push(`${s.id}: the first line is ${s.facts[0]?.topic}, not the official advice`);
    if (s.facts.some((f) => !f.source)) out.push(`${s.id}: a line has no source`);
    if (!s.facts.some((f) => f.topic === 'wind' && /not known/.test(f.text))) out.push(`${s.id}: wind is not said to be not known`);
    if (!s.url.startsWith('https://swimsignal.co.uk/spot/')) out.push(`${s.id}: no link to the spot's page`);
  }
  if (a.spots.length > 1 && a.spots[0].restricts && a.spots.some((s) => !s.restricts)) out.push('a spot whose official advice restricts swimming is first');
  if (!a.plan_url?.startsWith('https://swimsignal.co.uk/plan/')) out.push('no link to Plan a swim');
  const text = shownText(a);
  if (e.no_spots && a.spots.length) out.push(`expected no spots, got ${a.spots.map((s) => s.id).join(', ')}`);
  if (e.some_spots && !a.spots.length) out.push('expected at least one spot, got none');
  if (e.spots_any_of && !a.spots.some((s) => e.spots_any_of.includes(s.id))) out.push(`none of ${e.spots_any_of.join(', ')} listed`);
  for (const id of e.spots_none_of || []) if (a.spots.some((s) => s.id === id)) out.push(`${id} listed`);
  if (e.first_spot_not && a.spots[0] && e.first_spot_not.includes(a.spots[0].id)) out.push(`${a.spots[0].id} first`);
  if (e.day !== undefined && a.day !== e.day) out.push(`day ${a.day}, expected ${e.day}`);
  if (e.forecast_known !== undefined) {
    for (const s of a.spots) {
      const f = s.facts.find((x) => x.topic === 'forecast');
      const unknown = /not known/.test(f?.text || '');
      if (unknown === e.forecast_known) out.push(`${s.id}: forecast ${unknown ? 'not known' : 'known'}, expected ${e.forecast_known ? 'known' : 'not known'}`);
    }
  }
  for (const re of e.says || []) if (!new RegExp(re, 'i').test(text)) out.push(`does not say /${re}/`);
  for (const re of e.summary_not || []) if (new RegExp(re, 'i').test(a.summary)) out.push(`the summary says /${re}/`);
  if (!live) {
    const m = q.mock_expect || {};
    // Unless the question says otherwise, the scripted answer is a good one: taken first time, in full.
    if (run.refused !== (m.refused ?? 0)) out.push(`refused ${run.refused} answers, expected ${m.refused ?? 0}`);
    if (!!a.partial !== (m.partial ?? false)) out.push(`partial is ${!!a.partial}, expected ${m.partial ?? false}`);
    if (m.first_spot && a.spots[0]?.id !== m.first_spot) out.push(`first spot ${a.spots[0]?.id}, expected ${m.first_spot}`);
  }
  return out;
}
