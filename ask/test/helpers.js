import { readFileSync, readdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

// D1, as far as this Worker uses it, over a real SQLite database made by the same migrations.
export class FakeD1 {
  constructor() {
    this.db = new DatabaseSync(':memory:');
    const folder = new URL('../migrations/', import.meta.url);
    for (const name of readdirSync(folder).filter((n) => n.endsWith('.sql')).sort()) this.db.exec(readFileSync(new URL(name, folder), 'utf8'));
  }
  prepare(sql) { return new Statement(this.db, sql, []); }
  rows(sql, ...args) { return this.db.prepare(sql).all(...args).map((r) => ({ ...r })); }
}
class Statement {
  constructor(db, sql, args) { this.db = db; this.sql = sql; this.args = args; }
  bind(...args) {
    if (args.some((a) => a === undefined)) throw new TypeError('D1_TYPE_ERROR: undefined cannot be bound');
    return new Statement(this.db, this.sql, args);
  }
  async first() { const r = this.db.prepare(this.sql).get(...this.args); return r ? { ...r } : null; }
  async run() { const r = this.db.prepare(this.sql).run(...this.args); return { success: true, meta: { changes: Number(r.changes) } }; }
}

export const SITE = 'https://swimsignal.co.uk/';
export const ORIGIN = 'https://swimsignal.co.uk';
// The fixtures were cut from the live site's files of 31 Oct 2026 (issued 18:13 UTC): twelve spots, their
// guides, and fourteen places. An hour after that update.
export const NOW = Date.parse('2026-10-31T19:00:00Z');

// The site, from test/fixtures/. Counts what was fetched.
export function fixtureFetcher() {
  const calls = [];
  const fetcher = async (url) => {
    const path = new URL(url).pathname.replace(/^\/data\//, '');
    calls.push(path);
    try {
      const body = readFileSync(new URL(`fixtures/${path}`, import.meta.url), 'utf8');
      return new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } });
    } catch {
      return new Response('not found', { status: 404 });
    }
  };
  fetcher.calls = calls;
  return fetcher;
}

export function env(overrides = {}) {
  return { DB: new FakeD1(), SITE_URL: SITE, ALLOWED_ORIGIN: ORIGIN, ASK_ON: 'on', ASK_MODEL: 'claude-haiku-5-5',
    ANTHROPIC_API_KEY: 'test-key-not-real', ASK_HASH_KEY: 'test-hash-key', ...overrides };
}

export const USAGE = { input_tokens: 2500, output_tokens: 350, cache_creation_input_tokens: 0, cache_read_input_tokens: 2200 };

// The Claude API, as a script: one entry a call. An entry is a list of tool calls ({ name, input }), or
// { text } for a reply in words, or { stop } for a stop reason with nothing else. Records each request.
export function scriptedClient(script) {
  const requests = [];
  let turn = 0, n = 0;
  const client = {
    messages: {
      async create(params) {
        requests.push(JSON.parse(JSON.stringify(params)));
        const step = script[turn++];
        if (!step) return { content: [{ type: 'text', text: 'Done.' }], stop_reason: 'end_turn', usage: USAGE };
        if (step.stop) return { content: [], stop_reason: step.stop, usage: USAGE };
        if (step.text) return { content: [{ type: 'text', text: step.text }], stop_reason: 'end_turn', usage: USAGE };
        return { content: step.map((c) => ({ type: 'tool_use', id: `toolu_${++n}`, name: c.name, input: c.input })), stop_reason: 'tool_use', usage: USAGE };
      },
    },
  };
  client.requests = requests;
  return client;
}

export const post = (body, { origin = ORIGIN, ip = '203.0.113.7' } = {}) => new Request('https://ask.example/ask', {
  method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json', 'CF-Connecting-IP': ip }, body: JSON.stringify(body),
});
