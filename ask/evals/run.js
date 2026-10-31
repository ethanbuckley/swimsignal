// Runs the eval set (questions.json) through the Worker's own loop (src/index.js, ask), against the
// fixtures, with the scripted model (mocked) or a real client (live). Returns one result a question.

import { readFileSync } from 'node:fs';
import { ask } from '../src/index.js';
import { clearCache } from '../src/tools.js';
import { checkRun } from './check.js';
import { env as testEnv, fixtureFetcher, scriptedClient } from '../test/helpers.js';

export const EVALS = JSON.parse(readFileSync(new URL('./questions.json', import.meta.url), 'utf8'));

export async function runEvals({ live = false, client = null, only = null, envOverrides = {} } = {}) {
  const now = Date.parse(EVALS.now);
  const out = [];
  for (const q of EVALS.questions) {
    if (only && !only.includes(q.id)) continue;
    clearCache();
    const env = testEnv(envOverrides);
    let run;
    try {
      const r = await ask(q.question, env, { now, fetcher: fixtureFetcher(), client: live ? client : scriptedClient(q.mock) });
      run = { status: 200, answer: r.answer, refused: r.refused, cost: r.cost, turns: r.turns };
    } catch (err) {
      run = { status: 500, error: String(err && err.stack || err) };
    }
    out.push({ id: q.id, question: q.question, run, problems: checkRun(q, run, { live }) });
  }
  return out;
}
