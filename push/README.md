# SwimSignal push alerts

This is a Cloudflare Worker that sends Web Push notifications for SwimSignal. A visitor turns on alerts on the Saved page, and their browser registers with the Worker along with the ids of their saved spots. Every 2 minutes the Worker reads the site's `data/alerts.json` and either revalidates a pending batch or identifies newly high spots. When a saved spot has just become high or very high, it queues one notification for each visitor who saved it, and at most one for each spot in 20 hours: the site is rebuilt several times a day, and a spot near the line can cross it more than once. It has no npm dependencies. The encryption (RFC 8291) and sender signature (RFC 8292) use the Web Crypto API built into Workers. The same Worker can send these alerts by email too; that part is off until it is set up ([Email alerts](#email-alerts)).

## What it stores

One Workers KV entry per browser, holding:

- the push subscription: the push service endpoint URL, its expiry time if the browser gave one, and the two public keys the browser supplied (`p256dh` and `auth`);
- the list of saved spot ids;
- the time of the last change.

No personal names, email addresses or IP addresses. (Email alerts, below, keep an address once its owner confirms it.) Cloudflare sees each request's IP address, as any host does, but the Worker does not store it. A second entry, `state`, holds the rank of every spot at the last run, so the next run can tell what has changed. While alerts are pending, `queue` holds subscription key hashes, the affected spots' public forecast details, the comparison state needed to recover an interrupted run, and bounded retry counters/times.

The endpoint and keys are enough to send that browser a notification, so treat the KV contents as private. Logs name a subscription by part of its hash, never by endpoint.

## Free-tier limits that matter

- Workers: 100,000 requests a day. Each subscribe, unsubscribe or CORS preflight is one request.
- KV (Cloudflare's KV limits page, read 29 Sep 2026): 100,000 reads and 1,000 writes a day, and 1,000 operations in one run. Each subscribe or change of saved spots is one write, so about 1,000 subscribes or changes a day. Finding affected subscribers lists metadata; subscriptions too large for metadata also need individual reads. Sending a batch reads its subscription records. Include queue/state writes and retries in the daily budget.
- Cron triggers: free.

## How many alerts go out, and how fast

Cloudflare's limits page (read 29 Sep 2026) gives the free plan 50 outgoing requests and 10 ms of CPU time per run, cron runs included, and 6 open connections at a time. Encrypting one notification took 0.28 ms of CPU in Node on a Mac, and signing once per push service 0.19 ms. So a run sends at most 15 (`SENDS_PER_RUN`) and keeps the rest in a queue for the next runs, 2 minutes apart: an ideal ceiling of about 450 attempts an hour before retries or runtime overhead. Every batch rechecks `alerts.json`, so an alert that waits in the queue still goes out in the latest forecast's words, or not at all if its spot is no longer high.

On the Workers Paid plan (about $5 a month) the limits are higher: set `SENDS_PER_RUN` in `wrangler.toml` to send more per run. `npx wrangler tail` shows each run's count, and a run cut short by a limit.

Finding who to alert needs no reads of the records: each subscription's spots are also kept in its key's metadata (up to 1,024 bytes, about 40 spot ids), so a run lists keys and reads only the records it sends to. KV can take up to a minute to show a write in every location, so a batch can occasionally go out twice; the second copy replaces the first on the device without a sound, because both carry the same tag.

### Queue recovery and changed saved spots

The complete queue is saved before advancing the comparison state. The first batch is sent on the next scheduled run, normally about two minutes later. This avoids writing the same KV key twice in rapid succession: [KV permits one write per second to a key](https://developers.cloudflare.com/kv/platform/limits/). If the state write fails after the queue was stored, a later run restores that checkpoint before sending. An interrupted batch retains its unsent recipients, although already-sent notifications can repeat if its checkpoint fails.

Before sending each queued notification, the Worker rereads the subscription and limits the notification to spots still saved in that record. A combined alert becomes a single-spot alert if only one affected spot remains. Removing all affected spots or deleting the subscription skips that notification. Updates are subject to [KV's eventual consistency](https://developers.cloudflare.com/kv/concepts/how-kv-works/): this is not an immediate-revocation or exactly-once guarantee, and these recovery steps do not serialize overlapping cron runs.

### Retries and expiry

Network errors, timeouts, HTTP 408/429/5xx and temporary subscription-read failures are retried, at most four attempts total. Delays start at two minutes, then four and eight; a later `Retry-After` (seconds or HTTP date) is respected, up to an hour; a longer one gives that alert up, since nothing new is looked for while the queue holds anything. Pending retries go behind unattempted recipients. HTTP 404/410 removes the subscription. Other failures are logged with the push service's reason (a VAPID key mismatch, say) and the endpoint cut out of it. Requests time out after 15 seconds.

Each batch rechecks the latest forecast and uses its current wording. Spots that disappeared or are no longer high are skipped. Failed forecast refreshes leave the queue intact and send nothing. Invalid, future-dated and regressed issue times are refused. A forecast expires after eight hours or at the next UK midnight, whichever is sooner: its wording says "today" and "tomorrow". An expired forecast pauses the queue rather than ending it, and the next fresh one decides which alerts still go out. So a spot that turns high in a late-evening build reaches everyone who saved it: those not reached by midnight get the next build's wording, if the spot is still high.

Push TTL is the forecast's remaining lifetime. Messages include an issue time and expiry; the device shows the UK issue time, or a neutral check-latest notice if delivery was delayed past expiry. It does not silently discard the push, because user-visible subscriptions require a visible result. Already-visible notifications cannot be withdrawn by this implementation. [Web Push TTL](https://www.rfc-editor.org/rfc/rfc8030#section-5.2), [visible push subscriptions](https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe).

Newly rising spots are looked for once the current queue has drained. KV still does not serialize overlapping cron invocations, so duplicate processing remains possible. Real-device push delivery and runtime-limit tests remain necessary before promising dependable paid alerts. Follow [the iPhone test guide](DEVICE_TEST.md); no physical-device test has been claimed yet.

## Setup

Run every command from the `push/` folder: `cd push`.

1. Log in to Cloudflare: `npx wrangler login`. The first run downloads wrangler, then a browser tab asks you to allow access. The terminal then says you are logged in.
2. Create the KV namespace: `npx wrangler kv namespace create PUSH`. It prints an `id`. Paste it into `wrangler.toml` in place of `REPLACE_WITH_KV_NAMESPACE_ID`.
3. Make the key pair: `node scripts/vapid-keys.mjs`. It prints two lines, `VAPID_PUBLIC_KEY=...` and `VAPID_PRIVATE_KEY=...`. It writes nothing to disk. Keep the terminal open.
4. Store the private key as a secret: `npx wrangler secret put VAPID_PRIVATE_KEY`. When asked, paste only the text after `VAPID_PRIVATE_KEY=`. If wrangler says the Worker does not exist yet and offers to create it, answer yes. Never commit this key.
5. Edit `wrangler.toml`. Set `VAPID_PUBLIC_KEY` to the text after `VAPID_PUBLIC_KEY=`. `VAPID_SUBJECT` is already `"mailto:hello@swimsignal.co.uk"`. Push services use it to contact you if the Worker misbehaves, so change it only if that address stops working.
6. Deploy: `npx wrangler deploy`. It prints the Worker's URL, `https://swimsignal-push.<account>.workers.dev`.
7. In the GitHub repository, open Settings → Secrets and variables → Actions → Variables, and add two repository variables:
   - `DIPCAST_PUSH_URL` = the Worker's URL with a trailing slash, `https://swimsignal-push.<account>.workers.dev/`
   - `DIPCAST_VAPID_PUBLIC_KEY` = the public key from step 3

   The site reads these when it builds, so they take effect at the next build.

## How you will know it worked

- Run `npx wrangler tail` and leave it open. Within 2 minutes you see a scheduled run. The first one logs `cron: first run, saved ranks for N spots, sent nothing`. Later runs log `cron: alerts.json unchanged (...)` or a line saying how many spots rose and how many alerts were sent, removed or failed.
- After the next site build, the Saved page shows an alerts button.

A run that fails with `VAPID_SUBJECT must be a mailto: or https: URL` or `public key must be a 65-byte uncompressed P-256 point` means step 5 was not finished.

## The mistake to avoid

The most likely mistake is pasting the private key into `wrangler.toml` or into the GitHub variable instead of the secret. It happens because the two keys are printed together and look alike, and the public key does go in both of those places. `wrangler.toml` is committed and the GitHub variable ends up in the published site, so either one publishes the private key. If it happens, make a new pair and repeat steps 3 to 7. Changing the key pair breaks every existing subscription, so everyone has to turn alerts on again.

## Email alerts

The same alerts by email, for visitors whose browser cannot take push. On an iPhone, push works only after the site is added to the Home Screen, so most iPhone visitors cannot have push alerts at all. Email alerts are built and tested but **off**: every `/email/` address answers 404, and the cron leaves email alone, until the secrets `MAIL_API_KEY` and `MAIL_HASH_KEY` are set and `EMAIL_FROM` and `WORKER_URL` are in `wrangler.toml`. The Saved page offers email only when the repository variable `DIPCAST_EMAIL_URL` is set, and the privacy notice gains its "Email alerts" section only then (`EMAIL_PRIVACY` in `scripts/build_site.py`).

### Why it is in this Worker

Push and email must alert for the same spots at the same builds. The decision lives in one place: each run, `index.js` compares `alerts.json` with the saved ranks in `state`, applies the 20-hour quiet time, and gets one list of spots that have just risen. That one list fills both queues, in the same run, before `state` moves on. When each alert is sent, push and email both recheck the latest `alerts.json` with the same rank (`HIGH`), the same expiry (`forecastExpiry`) and the same retry schedule (`src/shared.js`). A second Worker would need its own `state`, its own fetch and its own clock; if a build replaced another between its run and push's, the two could disagree. `test/email.test.js` runs a day and a half of builds through both and checks that they alert for the same spots each time.

Email has its own queue, `mailq`, because it drains more slowly: the email service allows 100 a day on the free plan, against about 450 pushes an hour. A long email queue must not hold back push, which looks for new rises only once its own queue is empty. Email sends in each run after push, from the same `alerts.json`, but never in the run that queued it (KV allows one write a second to a key).

The costs of sharing: email uses the same run's 50 outgoing requests (1 for `alerts.json`, up to 15 pushes, up to 10 emails), and a run that fails on bad VAPID settings sends no email either.

### Choosing the email service (read 4 October 2026)

| Service | Free | Cheapest paid | Tracking | UK GDPR terms | From a Worker |
|---|---|---|---|---|---|
| **Resend** (chosen) | 100 emails a day and 3,000 a month; the daily count resets at midnight UTC ([pricing](https://resend.com/pricing), [quotas](https://resend.com/docs/knowledge-base/account-quotas-and-limits)) | $20 a month for 50,000 | Open and click tracking "disabled by default for all domains" ([docs](https://resend.com/docs/dashboard/domains/tracking)) | A DPA that binds on accepting the terms, with the UK Addendum to the EU standard contractual clauses (section 6.4); processing mainly in the United States ([DPA](https://resend.com/legal/dpa), updated 31 Dec 2025) | One HTTPS POST with a bearer key; an `Idempotency-Key` kept 24 hours; custom headers allowed |
| Postmark | 100 emails a month | $15 a month for 10,000 ([pricing](https://postmarkapp.com/pricing)) | Not checked | A GDPR page is linked; its DPA was not read | HTTPS API |
| Amazon SES | No lasting free tier: new AWS accounts get up to $200 of credits for 6 months | $0.10 per 1,000 ([pricing](https://aws.amazon.com/ses/pricing/)) | Not checked | AWS's DPA (not read) | HTTPS API with AWS request signing (SigV4), which this Worker would have to implement |
| Brevo | 300 emails a day, once Brevo approves the account ([pricing](https://www.brevo.com/pricing/)) | Starter, from 5,000 a month (price not shown without scripts) | Link tracking in transactional email cannot be turned off; Brevo staff said in its forum (Dec 2023 to May 2024) that this was not planned outside Enterprise plans ([thread](https://community.brevo.com/t/no-way-to-disable-by-option-tracking-in-transactional-e-mail/201)). Removing the "Sent with Brevo" footer is a Standard-plan feature | EU company (not read) | HTTPS API |
| Cloudflare Email Service | On the Workers Free plan it sends only to verified addresses in the account | Sending to anyone needs the Workers Paid plan (about $5 a month): 3,000 emails a month included, then $0.35 per 1,000 ([pricing](https://developers.cloudflare.com/email-service/platform/pricing/), updated 9 Jun 2026). New accounts start with "a conservative daily quota" ([limits](https://developers.cloudflare.com/email-service/platform/limits/), updated 25 Sep 2026) | Not checked | Cloudflare's DPA, which already covers this Worker | A Worker binding, no key |

Resend is the one with a free tier that fits, tracking off by default, UK transfer terms that apply without signing anything, and a plain HTTP API. Its limits: 100 emails a day, and addresses processed in the United States under the UK Addendum. Brevo fails the no-tracking rule. Cloudflare's own service is the natural move once SwimSignal pays for Workers, which would also raise the push limits.

The service sits behind one function, `sendEmail` in `src/mail.js`, which returns one of five outcomes (sent, retry, quota, config, rejected). To swap services, rewrite that function and change the secret; nothing else names Resend except the privacy section (`EMAIL_PRIVACY`).

### What it stores

In the same KV namespace as push, under keys that never contain an address (`src/email.js` has the list):

- `mail:<id>` for each confirmed address: the address, the saved spot ids and the time of confirming (UK GDPR Article 7(1) asks the controller to be able to show consent). Nothing else.
- `pend:<id>` for a sign-up waiting for its confirmation: the address, the spots and a random number for the link. KV deletes it after two days.
- `mailq`: alerts waiting to go, by `<id>` and spot, with no address in them.
- `quota:<day>`: how many emails went out that UTC day.
- `rl:ip:<hash>` and `rl:to:<hash>`: sign-up counts, one per connection per hour and one per address per day. KV deletes them after the hour or the day.

`<id>` and the hashes are HMAC-SHA-256 under the secret `MAIL_HASH_KEY`. The hour or day is part of each count's hash, so counts cannot be matched across hours or days, and raw IP addresses are never stored. An IPv6 address is counted by its first 64 bits, as the reviews Worker does.

### How a sign-up and an alert go

1. The Saved page posts the address and the saved spots' ids to `/email/subscribe` (only from `ALLOWED_ORIGIN`). A hidden field catches bots. The answer is 202 whether or not the address is known, so the form cannot be used to find out who has signed up.
2. Limits: 5 sign-ups an hour from one connection (then 429), and 3 confirmation emails a day to one address (later ones get 202 and no email). Spot names in the email come from `alerts.json`, never from the request.
3. The confirmation email links to `/email/confirm`. Opening the link shows a page with a Confirm button; only pressing it stores `mail:<id>`. Mail scanners open links in emails on their own, and that must not confirm anyone. Signing up again replaces the list of spots once the new list is confirmed.
4. When a saved spot rises, the address is queued. Each run sends at most `EMAILS_PER_RUN` (10), and alerts stop at `EMAIL_DAILY_CAP` (100) minus `EMAIL_CONFIRM_RESERVE` (20), so sign-ups still work on a busy day. Before each email the record is read again: an address that has unsubscribed, a spot no longer saved or no longer high, or an expired forecast sends nothing, as with push.
5. Each alert is plain text with a short HTML version: the spot, its level with "risk", the day and why (the page's own headline), the issue time, a link to the spot, and an unsubscribe link. No images, no web fonts, no redirected links. It carries `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058): a mail program's unsubscribe button POSTs to the link and the record is deleted at once. The link in the email body shows a page with an Unsubscribe button, for the same reason as Confirm.
6. The email service's answers: a network error, timeout, 408, 429 rate limit or 5xx is retried on push's schedule (2, 4, 8 minutes; four attempts). A daily or monthly quota answer pauses the queue until midnight UTC. A 401 or 403 (a wrong key, or a sender domain not verified) pauses it for an hour and logs "check MAIL_API_KEY and EMAIL_FROM". Anything else is dropped and logged. Logs name an address by part of its id, and an address in the service's reason is cut out.

Not built: bounce and complaint handling through Resend's webhooks. An address that bounces keeps its record until it unsubscribes or is removed by hand.

### Free-tier budget

KV writes are the tight one (1,000 a day, shared with push). A sign-up costs 4 writes (two counts, the pending request, the day's email count) and a confirmation 1 write and 1 delete. Each run that sends email writes the queue and the count. So a few hundred sign-ups in a day would reach the limit. The email service's 100 a day is the other: on a day when many spots rise, alerts wait for the next day, and the next build's wording decides what still goes out.

### Setup

Do these in order; the page stays unchanged until the last step. Run commands from the `push/` folder.

1. Create a Resend account at https://resend.com/signup, on the free plan. Accepting its terms accepts its DPA (https://resend.com/legal/dpa); read it first, since it is the processor agreement the privacy notice relies on.
2. In Resend, open Domains, then Add domain, and enter `swimsignal.co.uk`. If it offers a region, pick the one nearest the UK.
3. Add the DNS records Resend lists, at Cloudflare (dash.cloudflare.com, swimsignal.co.uk, DNS, Records), each with proxy status **DNS only**: an MX record named `send` (priority 10), a TXT record named `send` (the SPF value), and a TXT record named `resend._domainkey` (the DKIM value). Resend's "Sign in to Cloudflare" button can add them for you instead. Leave the existing records alone: the root MX and SPF records are iCloud Mail's, for hello@, and `_dmarc` already exists (`p=none`). Then press Verify DNS Records and wait until the domain shows Verified (Resend says up to 72 hours, often minutes).
4. In the domain's Configuration tab, check that open tracking and click tracking are both off. They are off by default, and the privacy notice says the emails carry no tracking.
5. In API Keys, create a key with "Sending access" for swimsignal.co.uk only. It starts `re_`.
6. Store it: `npx wrangler secret put MAIL_API_KEY`, and paste the key.
7. Make and store the hashing key: run `openssl rand -base64 32`, then `npx wrangler secret put MAIL_HASH_KEY`, and paste what it printed. Keep a copy in your password manager.
8. Check `wrangler.toml`: `EMAIL_FROM` is `SwimSignal <alerts@swimsignal.co.uk>`, `EMAIL_REPLY_TO` is `hello@swimsignal.co.uk` (replies go to iCloud), and `WORKER_URL` is this Worker's address with a trailing slash. It is set to `https://swimsignal-push.swimsignal-push.workers.dev/`, the address in the live site's `spots.json`; if `npx wrangler deploy` prints a different one, use that.
9. Deploy: `npx wrangler deploy`.
10. Try it on yourself before the page offers it. Pick a spot id from https://swimsignal.co.uk/data/alerts.json, then:

    ```
    curl -i -X POST https://swimsignal-push.swimsignal-push.workers.dev/email/subscribe \
      -H 'Origin: https://swimsignal.co.uk' -H 'Content-Type: application/json' \
      -d '{"email":"YOUR ADDRESS","spots":["SPOT ID"]}'
    ```

    It answers `HTTP/2 202`, and the confirmation email arrives within a minute. Open its link and press Confirm; the page says "Email alerts are on". In Gmail, "Show original" on the email should say `DKIM: 'PASS' with domain swimsignal.co.uk`.
11. Add the repository variable (Settings, Secrets and variables, Actions, Variables): `DIPCAST_EMAIL_URL` = `https://swimsignal-push.swimsignal-push.workers.dev/`.
12. Pass it to the build: in `.github/workflows/site.yml`, in the "Build forecasts and site" step's `env:`, under the two `DIPCAST_PUSH_URL` lines, add:

    ```yaml
              # Email alerts (push/README.md, "Email alerts"): the Worker's address; unset = no email sign-up.
              DIPCAST_EMAIL_URL: ${{ vars.DIPCAST_EMAIL_URL }}
    ```

### How you will know it worked

- After the next build, the Saved page's Alerts tile has "Or by email" with an address field, and the privacy notice has an "Email alerts" section under Alerts.
- `npx wrangler tail` shows, when a saved spot rises, `cron: ...: N spots rose to high, M alerts to send, K emails queued`, and on the next run `email: sent K, failed 0; 0 still queued`.

### The mistake to avoid

The most likely mistake is setting the repository variable and skipping step 12. Nothing changes, because the workflow hands the build only the variables named in `site.yml`, and a variable it does not name is invisible to it.

The most damaging one is changing `MAIL_HASH_KEY` later. Every record's key and every unsubscribe link already sent are derived from it, so a new key orphans every subscriber and breaks the links in their inboxes. If it must change, delete all email records first (below) and ask people to sign up again.

### Turning it off

- Remove the repository variable `DIPCAST_EMAIL_URL`: the next build hides the form and the privacy section.
- `npx wrangler secret delete MAIL_API_KEY` and deploy: the Worker stops all email at once and answers 404 on `/email/`.
- To delete every stored address: `npx wrangler kv key list --binding PUSH --prefix mail: --remote > mail-keys.json`, then `npx wrangler kv bulk delete mail-keys.json --binding PUSH --remote`, then delete `mail-keys.json`. Repeat with `--prefix pend:`. (Checked on a local copy of the namespace, not on the live one.)

### Trying it on this computer

`npx wrangler dev --local --test-scheduled` with `--var` for `SITE_URL`, `ALLOWED_ORIGIN`, `WORKER_URL`, `MAIL_API_KEY`, `MAIL_HASH_KEY`, the VAPID keys, and `MAIL_API_URL` pointing at a stand-in that accepts `POST` and answers `{"id":"x"}`. `MAIL_API_URL` exists only for this; leave it unset on the real Worker. `curl 'http://127.0.0.1:8787/__scheduled?cron=*/2+*+*+*+*'` runs the cron.

## Tests

`node --test test/*.test.js` (or `npm test`). They need nothing installed. They were run on Node 26.
