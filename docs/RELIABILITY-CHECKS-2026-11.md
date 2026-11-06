# Reliability checks, 2 November 2026

Pillar 1 of 6: bugs and reliability. The checks were run on main at 88f75e54 (after PR #600). Two checks failed and
are fixed in PR #607. Everything else passed as it stands.

## How it was run

- **Build.** main's own `build_site.write_pages`, into a scratch folder, from the live site's `data/spots.json`
  (issued 2 Nov 2026 00:20 UTC, commit f77a834). It was run with `DIPCAST_ROOT` set to this worktree and a scratch
  `DIPCAST_STATE`, and with push on and dates on, as the live build has them. A small local server served it. A data
  file not in the build (a spot's own file, its trace, its plume) was fetched once from swimsignal.co.uk and kept in
  the scratch folder. Shared caches were not touched.
- **Clock.** Fixed in each page with a `Date` that is offset from the real one. This does not reach the service
  worker, which keeps the real clock.
- **Day change.** A second server served the same files with every date moved back a day and `generated_at` set to
  23:20 the evening before. For the summer cases, dates were moved back 93 or 94 days and `generated_at` was set to
  `+01:00`. The time zone was fixed to Europe/London.
- **Alerts.** The push service was stubbed in the page (`PushManager.getSubscription`/`subscribe`). Every request to
  the Worker was answered locally through the DevTools protocol, with 204, 500 or 503. Nothing reached the deployed
  Worker from a page, and no notification was sent to anyone. The only requests to the deployed Worker were three
  read-only ones:
  - `OPTIONS /subscribe` from the site's origin: 204, CORS for `https://swimsignal.co.uk`;
  - `GET /subscribe`: 405;
  - `OPTIONS` from another origin: 403.
- **Offline.** The local server was switched to drop every connection, which also stops the service worker's own
  fetches. DevTools' offline switch was used only on an open page, to fire `offline`/`online`. With DevTools offline
  during a navigation, Chrome sent a second document request for the previous page and landed there. That is the
  harness, not the site: the same navigation with the server down and no emulation opened the right page each time.
  Real airplane mode was not tried.
- **Slow network.** DevTools throttling at 400 ms latency and about 400 kbit/s, plus a 2.5 s delay on every `data/`
  file at the server.
- **Back.** `history.back()` in the page, never WebDriver's own `/back`.

**Browsers and widths actually used.**
- Headless Chrome 156 (DevTools protocol) at 1,440 x 900 desktop and at 390 x 844 phone. The phone emulation was
  touch with an Android user agent; an iPhone user agent was used for the Home Screen notes.
- Real Safari 26.6.2 on this Mac (safaridriver), at 1,440 px and with the window at 390 px. Used for back navigation,
  the home map and the spill map. The Safari session was ended after the run.

**Not checked.** A real iPhone, the iOS simulator, a real push delivery, Firefox, a screen reader, and real airplane
mode.

## Findings

| Check | How it was run | Result | Fix |
| --- | --- | --- | --- |
| Save and unsave a spot | Spot page Save, at phone and desktop. `aria-pressed`, the button's words and both stores read back. Two spots, then Saved. | Pass | |
| Header count badge | `#saved-n` and `#nav-saved-n` after each change and after a reload. | Pass: 0 (hidden), 1, 2, back to 1 on unsave. `aria-label` "Saved spots: 1". | |
| Shared list's link | Share this list (link copied), opened on a cleared profile, Add to my lists. Then one of its spots, and back. | Pass: read-only list, Add, Saved shows it. Back from its spot returns to the shared list. A spot no longer in the forecast is left out of the link. | |
| Home Screen app note | iPhone user agent, as a Safari tab and as a Home Screen app (`navigator.standalone`), on an empty and a non-empty Saved. | Pass: the app says its spots are kept apart from Safari's. A Safari tab gets the journal note only. | |
| Alerts: on, off, weekly note, blocked | Saved page with stubbed push. The states: prompt, denied, granted with no subscription, on, reload, weekly on, weekly refused (503), off, reload. | Pass, each with its own words. Requests carry only the subscription, the spot ids and `weekly`. | |
| Alerts: refused sign-up | Turn on alerts while the Worker answers 500, then reload. | **Fail on main.** "Could not change alerts: the alert service answered 500" was shown, but the new push address stayed in the browser. A reload then showed **Turn off alerts**, and the outing tile treated alerts as on, though the Worker held nothing. | `alertsOn` drops a push address it made in the same call when the alert service refuses it. One the browser already had is kept, for a retry. Tests in `site_push_setup.test.cjs`; the first fails on main. Re-run in Chrome: the reload now shows Turn on alerts. |
| Date alerts (`PUSH_DATES`) | A plan's outing on Wednesday: alerts off, blocked, granted with no subscription, on. Then Alert me, reload, change the day (the earlier pair offered to stop), stop those, and a 503. | Pass. The body is the subscription and `dates` only. The kept list is right after each step. | |
| Offline, no copy kept | Service worker installed, the forecast deleted from its cache, server down. | Pass: the failed-load tile says "You are offline, and this device has no saved copy yet", with Try again and the EA's pages. | |
| Offline, the worker's copy | Server down after one online visit. Home, a spot opened before, a spot never opened, Saved, Plan, and a `#day=` link. | Pass. Every page opens from the stored copy. A spot never opened gets the home page standing in, with its forecast from the stored file. With `offline` fired: "Offline. This is the forecast issued ...". | |
| Offline, the kept outing (`OutingPack`) | Keep this outing, then the build's own cache deleted and the server down. Plan, its spot, another spot, home. Then the outing's own day, with the forecast 56 h old. | Pass: "Showing the copy kept on this device ...". On its own day the copy shows Wednesday as Today under the Stale notice (after this PR's day fix). The pack is dropped after its day by the page's tidy. The worker's own expiry was not checked, since the worker keeps the real clock. | |
| Stale feeds: `freshness()` | Home and a spot at 03:00 and at 10:00 (stale), and offline. | Pass: one Stale notice per page. | |
| Partial feeds: `gaps()` | The forecast file edited in flight: `today_rain_unavailable` 3, one spot's day "rain unavailable", one spot "forecast failed". Home, Saved, Plan and both spots, fresh and stale. | Pass: each gap said once, where it belongs. | |
| Repeated warnings | Every one of the 112 spot pages at 03:00, 15 of them stale at 10:00, and home. Duplicate notice-like lines counted. | Pass: none repeated. Each spot's guide has a "Verified: ..." line per fact, which is correct. | |
| "Today's update is due" | The build at 23:20; the page at 23:50, at 00:30 and at 07:15, in GMT and in BST. | Pass: one line on the list and one at the spot's issue time, from midnight until the forecast turns stale. | |
| Midnight: `today()`, `fiveDays`, day strip | GMT and BST. The build at 23:20 (BST: 22:20 UTC) viewed at 00:10 and 00:30. The build at 00:20 BST (23:20 UTC the day before) viewed at 00:40 and 00:50 BST. | Pass while fresh. `generated_at` is stamped in London time, so its date is the UK date in both seasons. | |
| Midnight: a stale forecast | The same build viewed at 07:45 GMT (8 h 25 min old), at 08:30 BST, 3 days and 6 days later. | **Fail on main.** Once over 8 hours old the page went back to the build's day. At 07:45 on Monday it called **Sunday "Today"**, opened Sunday's level as today's answer, and showed five days from Sunday, under the Stale notice. A kept outing opened on its day said the same. A code comment called this deliberate. It is fixed anyway: a forecast seen after midnight must not call the day before Today. | `readerDay` takes the device's date whenever it is later than the build's, however old the forecast. Each row keeps its own date and level. The day before is greyed as Yesterday, or under its own name when it was earlier (6 days old: "Thu"). The Stale notice stays. The spot's issue line gives the date and age ("Issued Sun 23:20, 8 h 25 min ago"), not "yesterday ...; today's update is due". Tests in `site_next_day.test.cjs`; two fail on main. Re-run in Chrome for every case in this row. |
| Midnight: a tab left open | Loaded at 23:58, the clock moved 5 minutes, the minute check run. Fresh and stale, on a spot with `#day=` and on home, and with typing in the search box. | Pass: the page reloads on the new day, and the opened day, now past, gives way to the summary. While typing, it offers "Update the page" instead. Stale: the same after this PR (on main a stale page never reloaded, as its day did not move). | |
| `#day=` to a past day | `spot/<id>/#day=` set to the day before, at 00:30, and to a day after the forecast. | Pass: the summary opens and the address drops the day. | |
| Map: home | 1,440 desktop and 390 phone (after Map), fast and throttled. Chrome and Safari. | Pass: 112 markers and every tile drawn. The phone's map is 0 x 0 until Map is pressed, as intended. | |
| Map: spot and spill map (`mountPlume`) | The spot's map at the top. `#plume-host` before and after it is scrolled into view, fast and throttled. Chrome and Safari 26.6.2 at both widths. | Pass: the host is 1 px and empty until near the screen (#599's `min-height`), then the spill map mounts with its tiles. | |
| Back: list → spot → back | The largest area's list, row 9 scrolled to the middle, opened, then `history.back()`, and the spot's own Back link. Chrome and Safari, both widths. | Pass: same scroll position to the pixel, and focus back on the row's link. | |
| Back: plan → spot → back | Plan from Oxford, Wednesday, kayak or canoe, 50 miles, two spots ticked, one opened, back. Chrome and Safari, both widths. | Pass: the spot opens on Wednesday. Back keeps the day, the activity, the place and both ticks (`PLAN_PICKS`). | |
| Back: spot → Lab exhibit → back | The spot on a picked day, its link into the Research Lab (lab/pollution/#spot=), back. Chrome and Safari, both widths. | Pass: the spot, the same day picked. | |

## Noted, not changed

- **A forecast six days old.** After this PR it shows no current days and its last row greyed under its own name,
  with the Stale notice. The spot's answer still gives a level from the build's "right now". Builds run hourly, so
  this needs the site to have been down for days. On main the same page showed the build's five days with a week-old
  Sunday as "Today".
- **The Stale notice's issue time** names a weekday only ("issued Sun 23:20"), so a week-old forecast reads like
  this week's Sunday. The words are unchanged here; noted for whoever next works on the notice.
- No change was needed in the planner, comparison, Saved or outing areas.
