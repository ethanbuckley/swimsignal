# SwimSignal reviews

Swimmers can review a spot: say whether they would swim there again, when they swam, what it was like, and add up to three photos. A spot's page shows the share who would swim there again (from three reviews), the reviews themselves and a form to write one. This folder is the Cloudflare Worker that takes reviews in and holds them until you publish them. It has no npm dependencies.

Deployed on 3 October 2026 at https://swimsignal-reviews.swimsignal-push.workers.dev/. The database is restricted to the EU, the photo store is configured in `wrangler.toml`, and the site uses the repository variable `DIPCAST_REVIEWS_URL` to enable reviews. Nothing is published until you approve it.

The moderation password is in your Mac's Keychain, under **swimsignal-reviews-admin**, for your Mac user account. Open Keychain Access, search for that name and choose Show password when you need to sign in at [/moderate](https://swimsignal-reviews.swimsignal-push.workers.dev/moderate). The password is not in the repository or this document.

## How a review travels

1. The page shrinks each photo on the swimmer's phone (1280 px on the long side, and a 240 px thumbnail) and saves it again from a canvas, which leaves out the GPS position and everything else the camera recorded. It then sends the review to this Worker (`POST /reviews`).
2. The Worker checks it, strips camera metadata and untrusted colour profiles a different client left in the photos (`src/jpeg.js`), and stores it as waiting: the text in D1, the photos in Workers KV. It hands the swimmer's browser the review's id and a random key, and keeps only a hash of the key. The browser keeps both, so the swimmer sees their review while it waits and can delete it at any time.
3. You open `/moderate`, read it, and press Publish or Delete. Nothing is published without you.
4. The next site build (`src/dipcast/reviews.py`) fetches the published reviews (`GET /published`) and their photos and writes them into the site, `reviews/index.json` and `reviews/photos/`. So a visitor reading reviews gets them from GitHub Pages with the rest of the site and never contacts the Worker. The site's rule that nothing is fetched from another site but the map's tiles still holds (docs/DESIGN.md, rule 8). The cost is a delay: a review appears at the next build after you publish it, usually within a few hours.

The build keeps the photos in its cache between runs, so each photo is downloaded once. If the Worker does not answer, the build publishes the last list it had and the page says the newest may be missing.

## Quick notes on a visit

Beside reviews, a swimmer can leave a short, dated note on what a spot was like today or yesterday: ticks from a fixed list (`src/rules.js`, `VISIT_KINDS`), up to 280 characters and one photo. A review describes the place; a note describes a day. The page's tile is "Recent visits", above the reviews (`src/dipcast/site/visits.js`).

- **Every tick ends.** How busy it was, parking that day and what the water looked like show for the day of the visit and the next; rough water for two days; suspected pollution three; algae a week; a closed way in or car park two weeks; damaged steps and a new warning sign a month. The Worker stores each note's last day (`until`); the build leaves out notes past it, and the page drops each tick on its own day, so a page that is not rebuilt still stops showing them. The daily cron deletes a note, with its photo, once it has ended.
- **Reconfirmation.** Damage, closures and signs can be confirmed by another swimmer ("Still like this", `POST /visits/confirm`), once a day from one connection, which starts their days again. Nothing a swimmer sends can end a warning early: "It is not like this any more" is a report reason, and you decide.
- **Suspected pollution and algae** read "Suspected pollution" or "Suspected algae", with "Not verified: what one swimmer saw, not a water test", until you verify them on `/moderate` by naming an official source. The page then shows "Verified:" and that source. The form gives the Environment Agency's and Natural Resources Wales's incident lines when either is ticked.
- **A good note never overrides a warning.** Notes are listed worst first (suspected pollution or algae, then hazards, then the rest, good news last), and a muted line above the first good note says it does not cancel the warnings above, or the forecast's, when the spot's level is above low or it is rated poor. Notes never change the forecast or the level.
- **Moderation.** A note of ticks alone is published as it arrives, because its words are the site's own and it names no one, and a note about today is worth little two days later. A note with words or a photo waits for you, as a review does. To make every note wait, set `PUBLISH_TICKS_AT_ONCE` to `false` in `src/rules.js` and deploy.
- **Limits.** Ten notes and 30 confirmations a day from one connection; 300 notes waiting; photos count towards the same daily cap and storage budget as reviews' photos.

The build writes the notes still showing into `reviews/index.json`, under `visits`, and their photos beside the reviews'.

### Deploying notes

Notes need the third migration. From this folder, in this order:

```
npx wrangler d1 migrations apply swimsignal-reviews --remote
```
```
npx wrangler deploy
```

You will know it worked when `curl https://swimsignal-reviews.swimsignal-push.workers.dev/published` ends with `"visits":[]` and, after the next site build, a spot's page shows "Recent visits" above the reviews. The likely mistake is deploying before applying the migration: the Worker then answers `/published`, every published photo and every note with an error ("no such table: visits"), and the site build keeps publishing its last list of reviews, with the photos it already has, until you apply it. Reviews still arrive meanwhile. It happens because `wrangler deploy` does not apply migrations.

## What it stores

- A review: the spot's id, yes or no, the day they swam, the text (at most 1,500 characters), the name to show (at most 40, may be empty), each photo's size, when it arrived and when it was published, and a SHA-256 hash of its key.
- The photos, in KV, under keys made from the review's id. A deleted review takes its photos with it.
- A note on a visit: the spot's id, the day (today or yesterday), the ticks, the text (at most 280 characters), one photo's size, when it arrived and was published, the day it was last confirmed and how many times, your verification source if any, its last day, and a SHA-256 hash of its key. No name. Deleted, with its photo, by the daily cron after its last day.
- A report: the review's or note's id, the reason picked from a list, and the time. Cleared when you keep or delete the review.
- Rate-limit counts: requests a day from one connection, under an HMAC of the IP address, the kind of request and the day, keyed with `ADMIN_TOKEN`. Never the address itself. The daily cron deletes days before yesterday. Ten reviews, 20 reports, 30 deletions and 60 status checks a day from one connection (an IPv6 /64 or an IPv4 address). The service also caps photos at 300 a day and pending reviews at 300, including simultaneous submissions. Published photos accumulate, so monitor total storage.

A review waiting for you is never public: `/published` lists only published ones, and a waiting review's photos answer only to the admin token.

## Free-tier limits that matter

Read from Cloudflare's pages on 3 Oct 2026:

- Workers: 100,000 requests a day, and 10 ms of CPU per request. Reading reviews costs the Worker nothing; only sending, deleting, reporting, moderating and the builds do.
- D1: 5 million rows read and 100,000 written a day, 500 MB a database. A review is a few rows; the text of 100,000 reviews would fit.
- KV: 1,000 writes a day and 1 GB stored. Each photo is two writes (it and its thumbnail), so at most about 160 reviews with three photos each a day. A photo is usually 150 to 400 KB, so 1 GB holds a few thousand.
- GitHub Pages: the published site may be up to 1 GB, and the photos are part of it.

R2 would be the natural home for photos at scale (10 GB free, no egress fees), but enabling it asks for a payment method, so KV is used to keep the setup card-free. Moving the photos to R2 later changes only `src/index.js`.

## Recreating the setup

The live service is already set up. These steps are for a new installation; do not recreate its database, photo store or admin password when deploying an update. For an update, apply any new migrations, run the tests below and deploy from this folder.

You need a terminal in this folder: `cd reviews`. Wrangler is already logged in on your Mac (you set up alerts with it). Each command takes a few seconds.

1. Create the database:
   ```
   npx wrangler d1 create swimsignal-reviews --jurisdiction=eu
   ```
   It prints a `database_id`. Paste it into `wrangler.toml` in place of `REPLACE_WITH_D1_DATABASE_ID`. `--jurisdiction=eu` keeps the reviews in the EU; it can only be set now, at creation.
2. Create the tables:
   ```
   npx wrangler d1 migrations apply swimsignal-reviews --remote
   ```
   If it asks whether to go ahead, answer yes. It applies `0001_reviews.sql`, which makes the three tables.
3. Create the photo store:
   ```
   npx wrangler kv namespace create PHOTOS
   ```
   It prints an `id`. Paste it into `wrangler.toml` in place of `REPLACE_WITH_KV_NAMESPACE_ID`.
4. Make the admin token and store it as a secret:
   ```
   node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
   ```
   ```
   npx wrangler secret put ADMIN_TOKEN
   ```
   Paste the 43 characters the first command printed. If wrangler says the Worker does not exist yet and offers to create it, answer yes. Keep a copy in your Keychain, which asks for it twice:
   ```
   security add-generic-password -s swimsignal-reviews-admin -a "$USER" -w
   ```
5. Deploy:
   ```
   npx wrangler deploy
   ```
   It prints the Worker's address. On your account it should be `https://swimsignal-reviews.swimsignal-push.workers.dev`, since wrangler named the account's workers.dev subdomain `swimsignal-push` when you deployed alerts.
6. Open that address with `/moderate` on the end, paste the token, and press Open the queue. It says "Nothing waiting."
7. Turn reviews on for the site. In the repository's root folder:
   ```
   gh variable set DIPCAST_REVIEWS_URL --body https://swimsignal-reviews.swimsignal-push.workers.dev/
   ```
   Use the address step 5 printed, with a slash on the end. The site reads it at its next build.

### How you will know it worked

After the next site build (Actions, "Build and publish site"), open any spot. Below the other tiles is "Swimmers' reviews: No reviews yet" with a Write a review button, and the privacy notice and the terms each have a Reviews section. Write a review of a spot you know. It shows on that spot as "waiting to be checked", and in `/moderate` under Waiting. Publish it; after the next build it is on the spot's page for everyone, and the score line appears under the spot's name once three reviews are up.

### The mistake to avoid

The most likely one is skipping step 2. Everything deploys, but every review then fails with "no such table: reviews", and the page tells the swimmer the service did not answer. It happens because `d1 create` makes an empty database and nothing else complains until the first review. Run step 2 and send the review again.

The second is pasting the KV id into the database's slot, or the other way round: both are long hex strings. Check each id against what its command printed before step 5.

To turn reviews off, delete the variable (`gh variable delete DIPCAST_REVIEWS_URL`). The next build removes them from the site; the Worker and what it holds stay until you delete them (`npx wrangler delete`, and the database and namespace in the dashboard).

## Moderating

`/moderate` lists what is waiting, what has been reported and the latest published, with the photos. It keeps the token in that browser until you press Forget. Add it to your Home Screen to check it from your phone. Nothing notifies you of a new review yet, so look every few days.

- Publish a review that says what it was like to swim at the spot, good or bad.
- Delete one about something else, or one that is abusive, advertises, or names or identifies another person.
- Delete one that accuses a named person or business of something, a crime or a pollution incident say: once you publish a review you are its publisher.
- Delete one with a photo in which someone can be recognised, unless it is plainly the sender, and any in which a child can be.
- A reported review stays up until you look. Keep it clears the reports; Delete removes it and its photos.
- Notes have their own three lists below the reviews: waiting, reported and published. The "Notes on a visit" fold on the page has the rules. Verify a note of pollution or algae only against an official source, and name it.

A review is published or deleted whole: there is no editing.

## Legal notes

Inferred, not legal advice. Reviews make SwimSignal a user-to-user service under the Online Safety Act 2023, but Schedule 1, paragraph 4, exempts a service whose users can only post comments or reviews on the provider's own content, and rate them. Reviews of SwimSignal's spot pages appear to fit; Ofcom's online checker would settle it. Reading every review before it is published is the strongest safeguard against unlawful content either way. Under UK GDPR the basis is consent, which deleting the review withdraws; the privacy notice's Reviews section, which the build adds only when reviews are on (`src/dipcast/reviews.py`), says what is kept and for how long. The terms gain the review rules the same way.

## Try it on this computer

No Cloudflare account needed: `scripts/dev-server.mjs` runs the Worker in Node with an in-memory SQLite database and photo store, so everything goes when it stops.

1. From the repository root, download the live forecast for a local copy of the site:
   ```
   mkdir -p site/data && for f in spots.json verification.json overflows.geojson alerts.json; do curl -so site/data/$f https://swimsignal.co.uk/data/$f; done
   ```
2. Start the Worker for a site on port 8771:
   ```
   SITE_URL=http://localhost:8771/ node reviews/scripts/dev-server.mjs
   ```
   It prints the moderation address and its token, `local-admin-token`.
3. In a second terminal, write the pages with reviews on, then serve them:
   ```
   DIPCAST_REVIEWS_URL=http://localhost:8787/ uv run python -c "import json, sys; sys.path.insert(0, 'scripts'); import build_site as b; from pathlib import Path; from dipcast.reviews import write_reviews; s = json.load(open('site/data/spots.json'))['spots']; b.write_pages(Path('site'), s, root='http://localhost:8771/'); print(write_reviews(Path('site')))"
   ```
   ```
   python3 -m http.server 8771 --directory site
   ```
4. Open `http://localhost:8771/spot/wharfe-burnsall/`, write a review, publish it at `http://localhost:8787/moderate`, run step 3's first command again, and reload.

Locally the moderation page shows spot ids rather than names and falls back to other fonts: Python's server sends no cross-origin header, while GitHub Pages does.

## Tests

`node --test test/*.test.js` (or `npm test`) runs the Worker against real SQLite (Node's `node:sqlite`, Node 24 or later) with the migration in `migrations/`. CI runs them on every change to this folder (`.github/workflows/reviews-tests.yml`). The page's parts are in `tests/site_reviews.test.cjs` and the build's in `tests/test_reviews.py`.

Before deploying a change, run it once in Cloudflare's own runtime as well: `npx wrangler d1 migrations apply swimsignal-reviews --local`, then `npx wrangler dev --local --var ALLOWED_ORIGIN:http://localhost:8771 --var SITE_URL:http://localhost:8771/ --var ADMIN_TOKEN:local-admin-token`. Node does not catch everything: on 3 Oct 2026 workerd refused to start a version whose `src/index.js` exported a number, which every Node test had passed (`src/rules.js` explains; a test now guards it).

Hosted D1 and KV were checked on 3 October 2026: a temporary camera JPEG was submitted, kept private while waiting, fetched by the admin with Exif removed, published, fetched through the site's build, and deleted with the sender's key. The resulting JPEG decoded successfully. The test review and its photos were removed; the queue was empty afterwards. A missing admin token was refused.

Still untested: a photo from a physical iPhone (HEIC turned into JPEG by Safari). The desktop tests do not establish that this device-specific flow works.

Photos from the page are converted to sRGB. The Worker drops ICC profiles from other clients because they can contain arbitrary identifying text; such uploads may have different colours. It retains only a plain JFIF header and a rebuilt Adobe colour transform, scans the whole JPEG, drops metadata between scans, and discards data after the image ends.

The browser checks the status of its own unpublished reviews when the spot is opened, and forgets reviews the operator has declined or removed. The moderation page searches the newest 500 published reviews; use the deletion endpoint by id for older ones.
# Storage and operator alerts

Apply both migrations before deploying this version. `photo_storage` reserves the stripped
JPEG and thumbnail bytes before upload, atomically across concurrent requests. The photo
budget is 800 MB, with warnings at 640 MB and 760 MB; reviews without photos still work at
the limit. Legacy photos reserve their maximum permitted size until deleted. This ledger
counts photo payloads, not total account usage or provider overhead.

Failed photo deletions retain their reservation and are retried by the daily cleanup job.
At most five abandoned batches are cleaned per run; a growing cleanup count needs attention.
The moderation page displays storage use. The authenticated `/admin/summary` route returns
only aggregate queue/report counts, latest arrival times and storage accounting.

`scripts/check_reviews.py` reads the existing operator credential from Mac Keychain and
keeps an atomic, private checkpoint under ignored `state/`. The Codex hourly heartbeat
announces new arrivals, worsening storage thresholds, cleanup failures and service recovery.
Unchanged checks stay quiet. The credential is restricted to the configured review-service
host, and is never saved in monitor output. The heartbeat needs this Mac awake and Codex
available; it is not an always-on external monitoring service.
