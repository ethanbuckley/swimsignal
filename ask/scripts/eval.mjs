// The eval set (evals/questions.json), from the command line.
//   node scripts/eval.mjs           the scripted model: free, the same as the tests
//   node scripts/eval.mjs --live    the real API with ANTHROPIC_API_KEY: costs money (README, "Model and cost")
// --model claude-sonnet-5-5 tries another model; --only id,id runs some questions. Data is test/fixtures either way.

import { runEvals } from '../evals/run.js';

const args = process.argv.slice(2);
const live = args.includes('--live');
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };
const only = opt('--only')?.split(',') ?? null;
const model = opt('--model');
let client = null;
if (live) {
  if (!process.env.ANTHROPIC_API_KEY) { console.error('--live needs ANTHROPIC_API_KEY'); process.exit(2); }
  const { default: Anthropic } = await import('@anthropic-ai/sdk');
  client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
}
const results = await runEvals({ live, client, only, envOverrides: model ? { ASK_MODEL: model } : {} });
let failed = 0, cost = 0;
for (const r of results) {
  cost += r.run.cost || 0;
  if (r.problems.length) failed++;
  console.log(`${r.problems.length ? 'FAIL' : 'pass'}  ${r.id}${r.run.turns ? `  (${r.run.turns} calls, $${(r.run.cost || 0).toFixed(4)})` : ''}`);
  for (const p of r.problems) console.log(`      ${p}`);
  if (live && args.includes('--show')) console.log(JSON.stringify(r.run.answer, null, 1));
}
console.log(`\n${results.length - failed} of ${results.length} passed${live ? `; cost $${cost.toFixed(4)} (from the usage the API reported)` : ' (scripted model)'}`);
process.exit(failed ? 1 : 0);
