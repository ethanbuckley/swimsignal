// Ask SwimSignal: a question in plain words ("somewhere within 40 minutes of Leeds, calm for paddleboarding,
// Saturday morning") answered from SwimSignal's own published data. The page posts the question to
// POST /ask; this Worker gives it to Claude with tools that read only the site's published files
// (tools.js), checks the answer (answer.js) and returns it with every fact's source and date (facts.js).
//
// Off until ASK_ON is "on" and the two secrets are set (README.md). It keeps no question and no answer:
// D1 (binding DB) holds only a keyed hash of each connection's count for the day, deleted the day after,
// and each day's total spend, which the daily cap needs.

import { SYSTEM, firstMessage } from './prompt.js';
import { TOOLS, newSeen, readSite, runTool } from './tools.js';
import { checkAnswer, fallbackAnswer } from './answer.js';
import { dayWords, forecastDays } from './facts.js';
import levels from '../../src/dipcast/site/levels.js';

export const MAX_QUESTION = 300;      // characters
export const MAX_TURNS = 8;           // calls to the model for one question
export const MAX_TOKENS = 4000;       // per call, thinking included
export const MAX_ANSWER_TRIES = 3;    // give_answer turned back this many times: the fallback answer instead
// Prices in US dollars per million tokens (Anthropic's price list, read 31 Oct 2026 via the claude-api
// reference, cached 6 Oct 2026; check https://www.anthropic.com/pricing before deploying). A cache write is
// 1.25 times the input price and a read a tenth, the 5-minute cache. A model not listed here is refused, since
// the daily cap could not be counted for it.
export const PRICES = {
  'claude-haiku-5-5': { input: 0.10, output: 0.50 },
  'claude-sonnet-5-5': { input: 2.00, output: 10.00 },
  'claude-opus-5-5': { input: 4.00, output: 20.00 },
};
// The most one call can cost, for the reservation against the cap: the input is bounded by the tools'
// sizes (at most 12 spots a search, 5 places, and a spot's lines), well under this many tokens.
const MAX_INPUT_TOKENS = 40000;
const DEFAULTS = { ASK_MODEL: 'claude-haiku-5-5', ASK_EFFORT: 'medium', ASK_DAILY_CAP_USD: '1', ASK_PER_CONNECTION: '10', ASK_QUESTIONS_PER_DAY: '300' };

export default {
  fetch: (request, env) => handleRequest(request, env),
  scheduled: (controller, env) => forgetOldHits(env),
};

const SAFE = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' };
const json = (status, body, headers = {}) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...SAFE, ...headers } });
const reply = (status, message, headers = {}) => json(status, { error: message }, headers);
const setting = (env, name) => String(env[name] ?? DEFAULTS[name] ?? '').trim();

export function isOn(env) {
  return setting(env, 'ASK_ON') === 'on' && !!env.ANTHROPIC_API_KEY && !!env.ASK_HASH_KEY && !!PRICES[setting(env, 'ASK_MODEL')];
}

export async function handleRequest(request, env, deps = {}) {
  const url = new URL(request.url);
  if (url.pathname !== '/ask') return reply(404, 'Not found');
  if (request.method !== 'POST' && request.method !== 'OPTIONS') return reply(405, 'Method not allowed', { Allow: 'POST, OPTIONS' });
  // Browsers always send Origin on these requests, so a missing one is not the site either.
  if (request.headers.get('Origin') !== env.ALLOWED_ORIGIN) return reply(403, 'Origin not allowed');
  const cors = { 'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN, Vary: 'Origin' };
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: { ...cors, 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Max-Age': '86400' } });
  }
  if (!isOn(env)) return reply(503, 'Ask SwimSignal is not switched on.', cors);
  let question;
  try {
    const body = await readJson(request);
    question = cleanQuestion(body?.question);
  } catch (err) {
    return reply(400, err.message, cors);
  }
  const now = deps.now ? deps.now() : Date.now();
  try {
    if (await overLimit(request, env, now)) {
      return reply(429, `You have asked ${setting(env, 'ASK_PER_CONNECTION')} questions today, the most one connection can. Plan a swim works as always.`, cors);
    }
    const model = setting(env, 'ASK_MODEL');
    const reserve = reservation(model);
    const day = new Date(now).toISOString().slice(0, 10);   // the budget's day is UTC, as the API's bill is
    if (!(await reserveSpend(env, day, reserve))) {
      return reply(503, 'Ask SwimSignal has answered all it can today. Plan a swim works as always.', cors);
    }
    let result;
    try {
      result = await ask(question, env, { ...deps, now });
    } finally {
      await settleSpend(env, day, reserve, result?.cost ?? reserve);
    }
    console.log(JSON.stringify({ ask: 'answered', turns: result.turns, cost_usd: Math.round(result.cost * 1e6) / 1e6, spots: result.answer.spots.length, partial: result.answer.partial || null }));
    return json(200, { answer: result.answer }, cors);
  } catch (err) {
    console.error('ask: unexpected error', err && err.stack ? err.stack : err);
    return reply(500, 'Ask SwimSignal had a problem. Plan a swim works as always.', cors);
  }
}

// ---- the question ----

const MAX_BODY = 4096;
async function readJson(request) {
  if (Number(request.headers.get('Content-Length')) > MAX_BODY) throw new Error('Body too large');
  const text = await request.text();
  if (text.length > MAX_BODY) throw new Error('Body too large');
  try { return JSON.parse(text); } catch { throw new Error('Body is not JSON'); }
}

// Control and direction-changing characters, and the zero-width ones: C0, C1, U+200B-200F, U+2028-202E,
// U+2060-206F and U+FEFF, built from their codes.
const STRIP = new RegExp(`[${[[0x00, 0x1f], [0x7f, 0x9f], [0x200b, 0x200f], [0x2028, 0x202e], [0x2060, 0x206f], [0xfeff, 0xfeff]]
  .map(([a, b]) => String.fromCharCode(a) + '-' + String.fromCharCode(b)).join('')}]`, 'g');
// One line of plain text: no control or direction-changing characters, at most MAX_QUESTION characters.
export function cleanQuestion(value) {
  if (typeof value !== 'string') throw new Error('question must be a string');
  const q = value.normalize('NFC').replace(STRIP, ' ').replace(/\s+/g, ' ').trim();
  if (q.length < 3) throw new Error('Ask a question');
  if (q.length > MAX_QUESTION) throw new Error(`At most ${MAX_QUESTION} characters`);
  return q;
}

// ---- the model ----

export function costOf(model, usage = {}) {
  const p = PRICES[model];
  const m = (n) => (Number(n) || 0) / 1e6;
  return m(usage.input_tokens) * p.input + m(usage.cache_creation_input_tokens) * p.input * 1.25
    + m(usage.cache_read_input_tokens) * p.input * 0.1 + m(usage.output_tokens) * p.output;
}
export const reservation = (model) => MAX_TURNS * (MAX_INPUT_TOKENS * PRICES[model].input + MAX_TOKENS * PRICES[model].output) / 1e6;

async function defaultClient(env) {
  const { default: Anthropic } = await import('@anthropic-ai/sdk');   // loaded here, so the tests never need it
  return new Anthropic({ apiKey: env.ANTHROPIC_API_KEY, maxRetries: 1, timeout: 25000 });
}

const londonDay = (ms) => new Date(ms).toLocaleDateString('en-CA', { timeZone: 'Europe/London' });
const issuedWords = (iso) => new Date(iso).toLocaleString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });

// The tool loop. Returns { answer, cost, turns, refused }; never throws for what the model does, only for a failure
// to reach it or the data, so the reader gets an answer or an error, never a half-checked one.
export async function ask(question, env, deps = {}) {
  const now = deps.now ?? Date.now();
  const model = setting(env, 'ASK_MODEL');
  const client = deps.client ?? await defaultClient(env);
  const today = londonDay(now);
  levels.setToday(today);   // the page's level rules read "today" from here
  const ctx = { env, today, now, question, seen: newSeen(), shown: [], fetcher: deps.fetcher ?? fetch };
  const doc = await readSite(env, 'data/spots-lite.json', ctx);
  ctx.seen.doc = doc;
  const days = forecastDays(doc).map((d) => `${dayWords(d)} (${d})`);
  const messages = [{ role: 'user', content: firstMessage({ question, today, todayWords: dayWords(today), issuedWords: issuedWords(doc.generated_at), days }) }];
  let cost = 0, turns = 0, refused = 0, nudged = false;
  while (turns < MAX_TURNS) {
    turns++;
    const res = await client.messages.create({
      model, max_tokens: MAX_TOKENS,
      system: [{ type: 'text', text: SYSTEM }],
      tools: TOOLS, messages,
      cache_control: { type: 'ephemeral' },
      output_config: { effort: setting(env, 'ASK_EFFORT') },
    });
    cost += costOf(model, res.usage);
    if (res.stop_reason === 'refusal' || res.stop_reason === 'max_tokens') return { answer: fallbackAnswer(ctx, res.stop_reason), cost, turns, refused };
    messages.push({ role: 'assistant', content: res.content });
    const uses = res.content.filter((b) => b.type === 'tool_use');
    if (!uses.length) {
      if (nudged) return { answer: fallbackAnswer(ctx, 'no answer'), cost, turns, refused };
      nudged = true;
      messages.push({ role: 'user', content: 'Call give_answer with your answer.' });
      continue;
    }
    const results = [];
    for (const use of uses) {
      if (use.name === 'give_answer') {
        const { problems, answer } = checkAnswer(use.input, ctx);
        if (!problems.length) return { answer, cost, turns, refused };
        refused++;
        if (refused >= MAX_ANSWER_TRIES) return { answer: fallbackAnswer(ctx, 'answer refused'), cost, turns, refused, problems };
        results.push({ type: 'tool_result', tool_use_id: use.id, is_error: true, content: 'Not given to the person. Fix these and call give_answer again:\n- ' + problems.join('\n- ') });
        continue;
      }
      const out = await runTool(use.name, use.input, ctx);
      const text = JSON.stringify(out);
      ctx.shown.push({ name: use.name, out });
      results.push({ type: 'tool_result', tool_use_id: use.id, content: text, ...(out.error ? { is_error: true } : {}) });
    }
    messages.push({ role: 'user', content: results });
  }
  return { answer: fallbackAnswer(ctx, 'too many steps'), cost, turns, refused };
}

// ---- limits ----

const hex = (bytes) => Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
async function hmac(key, text) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(key), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(text)));
}

// The connection to count: an IPv4 address whole, an IPv6 one by its first 64 bits, the block one
// home or phone is given (as reviews/src/index.js counts them).
export function connectionOf(ip) {
  const a = String(ip || '').trim().toLowerCase();
  if (!a.includes(':')) return a || 'unknown';
  if (a.includes('.')) return a.slice(a.lastIndexOf(':') + 1);
  const [head, tail] = a.split('::'), h = head ? head.split(':') : [], t = tail ? tail.split(':') : [];
  const groups = tail === undefined ? h : [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill('0'), ...t];
  return groups.slice(0, 4).map((g) => g.padStart(4, '0')).join(':') + '::/64';
}

// Questions today from this connection. The key is a keyed hash of the connection and the day, so the
// table never holds an address, and yesterday's counts cannot be matched to today's.
async function overLimit(request, env, now) {
  const day = new Date(now).toISOString().slice(0, 10);
  const key = (await hmac(env.ASK_HASH_KEY, `${day}|${connectionOf(request.headers.get('CF-Connecting-IP'))}`)).slice(0, 32);
  const row = await env.DB.prepare('INSERT INTO hits (key, day, n) VALUES (?, ?, 1) ON CONFLICT (key, day) DO UPDATE SET n = n + 1 RETURNING n')
    .bind(key, day).first();
  return row.n > Number(setting(env, 'ASK_PER_CONNECTION'));
}

export async function forgetOldHits(env, now = Date.now()) {
  const yesterday = new Date(now - 86400 * 1000).toISOString().slice(0, 10);
  await env.DB.prepare('DELETE FROM hits WHERE day < ?').bind(yesterday).run();
}

// The daily cap, in millionths of a dollar so the sums stay whole. A question first reserves the most it
// could cost, in one statement, so two at once cannot both pass a cap only one fits under; when it ends,
// the reservation is swapped for what it cost. A Worker stopped mid-question leaves its reservation
// counted, which errs on the side of spending less.
const micro = (usd) => Math.ceil(usd * 1e6);
async function reserveSpend(env, day, usd) {
  const cap = micro(Number(setting(env, 'ASK_DAILY_CAP_USD')));
  const most = Number(setting(env, 'ASK_QUESTIONS_PER_DAY'));
  await env.DB.prepare('INSERT INTO spend (day) VALUES (?) ON CONFLICT (day) DO NOTHING').bind(day).run();
  const row = await env.DB.prepare(`UPDATE spend SET reserved_micro = reserved_micro + ?1, questions = questions + 1
    WHERE day = ?2 AND spent_micro + reserved_micro + ?1 <= ?3 AND questions < ?4 RETURNING questions`).bind(micro(usd), day, cap, most).first();
  return !!row;
}
async function settleSpend(env, day, reserved, spent) {
  await env.DB.prepare('UPDATE spend SET reserved_micro = MAX(0, reserved_micro - ?), spent_micro = spent_micro + ? WHERE day = ?')
    .bind(micro(reserved), micro(spent), day).run();
}
