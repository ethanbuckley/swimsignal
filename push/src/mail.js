// The email service, behind one function so that it can be swapped: email.js calls sendEmail and
// reads only the outcome it returns. This one is Resend's HTTP API (https://resend.com/docs/api-reference/emails/send-email,
// read 4 Oct 2026): one POST per email, the key as a bearer token, and an Idempotency-Key that
// Resend remembers for 24 hours, so a batch repeated after a lost checkpoint is not sent twice.
// To use another service, write the same function for its API and keep the outcomes; README.md
// ("Choosing the email service") has what was compared.
//
// Outcomes:
//   { outcome: 'sent' }                        accepted for delivery
//   { outcome: 'retry', after, why }            try again later: network, timeout, 5xx, rate limit
//   { outcome: 'quota', why }                   the service's daily or monthly allowance is used up
//   { outcome: 'config', why }                  the key or sender is wrong: nothing can go out
//   { outcome: 'rejected', why }                this email will never be accepted (bad address, say)

import { retryAfter } from './shared.js';

// MAIL_API_URL is only for trying the Worker on this computer against a stand-in (README.md).
const API = 'https://api.resend.com/emails';

// Resend's error names (https://resend.com/docs/api-reference/errors, read 4 Oct 2026).
const QUOTA = new Set(['daily_quota_exceeded', 'monthly_quota_exceeded']);

export async function sendEmail(env, msg, { fetch = globalThis.fetch, now = Date.now } = {}) {
  const body = {
    from: env.EMAIL_FROM,
    to: [msg.to],
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
    ...(env.EMAIL_REPLY_TO ? { reply_to: env.EMAIL_REPLY_TO } : {}),
    ...(msg.headers ? { headers: msg.headers } : {}),
  };
  let res;
  try {
    res = await fetch(env.MAIL_API_URL || API, {
      method: 'POST',
      signal: AbortSignal.timeout(15000),
      headers: {
        Authorization: `Bearer ${env.MAIL_API_KEY}`,
        'Content-Type': 'application/json',
        ...(msg.idempotencyKey ? { 'Idempotency-Key': msg.idempotencyKey } : {}),
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    return { outcome: 'retry', after: 0, why: `network: ${err?.message || 'failed'}` };
  }
  if (res.ok) { await res.body?.cancel(); return { outcome: 'sent' }; }
  let name = '', message = '';
  try { ({ name = '', message = '' } = await res.json()); } catch { /* not JSON */ }
  const why = `HTTP ${res.status}${name ? ` ${name}` : ''}${message ? `: ${String(message).slice(0, 160)}` : ''}`;
  // 409: the same Idempotency-Key is already in use or was used for a different email. Either
  // way an email for this key has gone or is going, so it counts as sent and is not repeated.
  if (res.status === 409) return { outcome: 'sent', why };
  if (res.status === 429 && QUOTA.has(name)) return { outcome: 'quota', why };
  if (res.status === 408 || res.status === 429 || res.status >= 500) {
    return { outcome: 'retry', after: retryAfter(res.headers.get('Retry-After'), now()), why };
  }
  if (res.status === 401 || res.status === 403) return { outcome: 'config', why };
  return { outcome: 'rejected', why };
}
