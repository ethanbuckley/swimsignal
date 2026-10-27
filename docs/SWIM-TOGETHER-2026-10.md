# Swim Together and river days: a plan (27 October 2026)

Three outside proposals (all pasted by Ethan on 27 Oct 2026) ask for social features: shared outings, "I'm here" check-ins, a map of other swimmers, paddling and SUP, a shared "river day" with lift sharing, an access-point atlas and club pages. The third adds a business model: a paid personal tier and a paid club tier. Section 5 takes that one.

**The plan in one line:** build shared outings as links first, with no server, no accounts and no user words on the site; add a stored outing with a list of who is coming only for a pilot, after an Online Safety Act check and a DPIA; grow the access atlas from the guides and visit notes that already exist; leave check-ins, public discovery, messaging and lift matching until a pilot shows clubs use the rest.

Each claim below says whether it was checked in the code or a source on 27 Oct, or is inferred.

## 1. What already exists

Most of both proposals is half built. Checked in the code on 27 Oct 2026:

| Proposal item | What is there now | Where |
|---|---|---|
| Outing with time, spot and backup | The plan page holds a day, a time (`when`), a spot and a backup, side by side with official advice, kept in the address (`#…&when=&spot=&backup=`) | `src/dipcast/site/outing.js`, `plan.js` (`planHash`) |
| Sharing an outing | "Share this plan" sends a list (name, day, spot ids) to the Saved page. It does not carry `when`, `spot` or `backup`, so the friend gets a list, not the outing | `index.html` around line 3760 |
| Alert when conditions change | Alerts for a date: a push when a day enters the forecast and each time its level changes | `push/src/dates.js` |
| "Participants acknowledge the change" | A leader's "I have read version X" tick, kept only in that browser. A later forecast version asks for a fresh read | `brief.js` (on `record.html`) |
| "What changed since you looked" | "Was low risk when you looked on Friday at 18:20; now moderate risk", device-only | `since.js` |
| "Has anything changed here?" | Visit notes: ticks for damaged steps, closed access, new sign, closed car park, rough water, suspected pollution or algae; each expires (1 to 30 days); others can reconfirm; words and photos wait for moderation | `reviews/src/rules.js` (`VISIT_KINDS`), `visits.js` |
| Access-point atlas | Practical guides: 49 spots, 403 sourced and dated facts. Topics: rules 119, parking 84, toilets 54, path 50, entry 42, fees 21, hours 18, changing 14, exit 1. No real photos | `guides/*.toml` |
| River levels | Shown on spot pages (PR #36) | `scripts/build_site.py` |
| Paddlers, sailors, ghyll groups | The clubs page already speaks to them, with the same level for every activity | `src/dipcast/pages/clubs.html` |
| Calendar file for a day | The organisers' page makes one | `spotdate.js` |
| Wind and gusts | **Not on the site.** No wind variable is fetched or shown | grep of `src/dipcast` and `scripts` |
| Accounts | **None.** The privacy page says "No accounts, no cookies and no advertising"; the support page says "no accounts" | `pages/privacy.html` line 22, `pages/support.html` line 15 |

One gap matters for "an official advisory appears, the organiser gets a prompt". Alerts for a date fire only when the day's **level** changes (`dates.js` line 91: `if (d && d.level !== before)`). New official advice on a day whose level stays the same sends nothing. The wording does switch to the advice when an alert does go out (line 113).

## 2. What shapes the design

**Online Safety Act.** Checked 27 Oct against legislation.gov.uk, Schedule 1 paragraph 4: a user-to-user service is exempt when users can only post comments or reviews on the provider's own content, like or dislike, use emojis, vote yes/no, rate, and show identifying content with those. Reviews and visit notes on spot pages fit that. Inferred, not legal advice: a meetup page with an organiser's words, a list of names others can see, messages after joining, or lift-share chat is user content that is not a comment on provider content, so the exemption would no longer cover the service. Being in scope brings Ofcom's duties for every user-to-user service: an illegal content risk assessment, a children's access assessment, reporting and complaints, and records. Ofcom's online checker would settle whether a given stage is in scope. Run it before stage 2.

**Personal data and safety.** A named person's planned place and time is personal data. A check-in is location data about a person. A lone swimmer's "Saturday 6am at this pool, open to company" on a public map tells anyone where they will be. Inferred: stage 2 needs a short DPIA (the ICO's advice for anything likely high risk, as the illness reports README already records), and public individual plans should not be built at all.

**The empty room.** At the last count (24 Oct, not rechecked today): about 420 visits from 1 to 24 Oct (Cloudflare's sampled estimate), one push subscription, no reviews or visit notes. A "swimmers nearby" map would be empty. Clubs already talk in WhatsApp and Facebook groups. What they lack is the conditions attached to the plan and a nudge when those change. That is SwimSignal's part. Messaging is theirs already.

**One operator.** Every moderated thing lands on Ethan. Visit notes and reviews already wait for him.

**Public code.** Club names, contacts and pilot lists stay out of this repo (decision of 24 Oct).

**Activity advice needs evidence.** Both proposals say so. The site gives one pollution level for every activity and says nothing is safe. A wind line for SUP would be a reading, not a verdict on a route.

## 3. Stages

### Stage 0: ask first (no build)

The interviews are already planned (centres first, 10 by 31 Jan 2027). Add five questions:

1. How does your group agree where and when to swim or paddle now? Which app?
2. When the forecast or an advisory changes after you have planned, how do people find out?
3. Would you send members a link that shows the plan with today's conditions, and tells them if they change?
4. Would you want a list of who is coming kept anywhere but your chat?
5. For one-way paddles: how do you sort the shuttle now? Is it a problem?

**Gate to stage 2:** at least two groups say yes to 3 and 4, and at least one uses stage 1 for real outings.

### Stage 1: "Send this outing" (page only)

A link that opens as an invitation: the day, a time, the spot, the backup, the meeting point, and each spot's level and official advice **now**. Nothing is stored on a server.

- **Carries only fixed choices.** Spot, backup, day, time, activity (swim, paddle, SUP), meeting point picked from that spot's guide facts (`entry`, `parking`) or a tapped map point, and the level each spot had when the link was made. **No free text.** A message in a link drawn under the SwimSignal name would likely count as user content on the site (section 2, inferred), and could be used for phishing. The group's own chat carries the words.
- **"Changed since this was sent."** The link holds the forecast version it was made with (the issue id and check from `brief.js`). The page compares, as `since.js` does: "Moderate risk when this link was made on Thursday; now high risk. Official advice since: …".
- **Alert me about this day.** The existing alerts for a date, offered on the invitation (cap 10 pairs per browser, as now).
- **Official advice is news.** Change `dates.js` so new or lifted official advice on an asked-for day is news even when the level stays. This is worth doing on its own, before anything else here.
- **A river day.** For paddlers, "backup" becomes optional and a "finish" point is added: start and finish both show their level, and the stretch between them lists the overflows upstream of the start (anypoint already traces them).
- **Add to calendar.** The organisers' page's calendar file, with both spots' links.
- **Read tick.** The `brief.js` tick on the invitation, still kept only on that device. It is a reminder for the person, and the page says so.

Fits: the exemption, the privacy page's promises, the public repo, and the free plans. It needs no moderation.

Work, one PR each:

| # | Change | Files | Tests |
|---|---|---|---|
| S1 | Official advice counts as news for alerts for a date | `push/src/dates.js` | `push/test/dates.test.js`, `official.test.js` |
| S2 | Outing link: `when`, `spot`, `backup`, `meet`, `act`, version, level at send | `plan.js`, `outing.js` | `tests/site_outing.test.cjs`, `site_plan.test.cjs` |
| S3 | Invitation view: changed-since line, alert button, calendar file | `outing.js`, `index.html`, `spotdate.js` | `site_outing.test.cjs`, `site_official_outing_since.test.cjs` |
| S4 | Finish point and the stretch between | `outing.js`, `anypoint.js` | new cases in `site_outing.test.cjs` |
| S5 | Privacy notice line: what the link holds | `pages/privacy.html` | a new check in `tests/` that the line is present |

S1 needs a push Worker redeploy, which is Ethan's.

### Stage 2: an outing with a list (server, pilot only)

Only after the stage 0 gate, the Ofcom check and a DPIA. Off by default, behind a variable as reviews were (`DIPCAST_REVIEWS_URL`).

- **No accounts.** The organiser gets an unguessable link and a key, as reviews do now (the Worker keeps a hash of the key). Joining gives each person their own key. Same pattern, same D1 database in the EU.
- **Fixed choices only.** Going, maybe, not now; "I have seen the change". A display name of up to 20 characters is the only typed field. Inferred: still user content, so the Ofcom check applies.
- **Who sees names.** Recommended: the organiser sees names; others see counts ("4 going, 1 maybe"). Ethan decides.
- **Change prompt shared.** When the day's level or official advice changes, the organiser gets a push (stage 1's S1 does the detection) and each person's next visit asks them to tick "I have seen the change". The organiser sees who has ticked. This is the device-only tick made shared.
- **Organiser tools.** Cancel, switch to the backup, remove a person, close the list.
- **Deleted** a week after the outing day by the daily cron. Nothing kept for analysis.
- **Pilot:** one swim club and one paddling club on the same river, as the second proposal says. Adults only, by the clubs' own membership, written into the pilot terms.

Reports and blocking: the organiser removes people; anyone can report an outing to Ethan, as visit notes are reported now.

### Stage 3: grow the access atlas (alongside stages 1 and 2)

Built on guides and visit notes, so it stays within the exemption.

- New guide topics: `launch` (for boards and boats), `carry` (distance from parking), `exit`. Same rule: each fact sourced and dated, "Verified" or a swimmer's suggestion.
- New visit-note ticks for paddlers: launch under water, tree or debris across the river, portage path blocked. Each with an expiry, as now (`VISIT_KINDS`).
- Reviewed photos of access points, through the reviews photo pipeline, which already strips location data.
- The pilot river's spots get guides first.

### Not now

| Item | Why not yet | What would change it |
|---|---|---|
| "Planning to swim here" by individuals, public | Tells strangers where a named person will be; empty with current numbers | Never public for individuals. Club-run events only, in stage 4 |
| "I'm here" check-in and live location | Location data about people, safety risk, needs accounts | Pilot clubs ask for it after stage 2 |
| Public meetup discovery map | Full OSA duties, age assurance, moderation load, empty map | Stage 2 used by several clubs for a season |
| Messaging | Clubs already have chats; full OSA duties | No sign it is wanted |
| Lift and shuttle matching | Names, cars and seats between strangers; insurance and payment questions not checked | A page-only seat counter (3 paddlers, 2 cars, 1 spare seat) is possible with no names, if paddlers ask in stage 0 |
| Club pages with membership links | Needs club consent and content outside the public repo | Two pilot clubs ask for it |
| Wind for SUP | Not fetched now. Open-Meteo's call budget for adding wind not checked (ration rules: PR #243) | A paddling club asks, and the cost is checked |
| Route suitability for paddlers | Needs its own evidence and expert review | Not planned |
| Cleanup and stewardship events | A separate audience; same stage 2 machinery would serve it | After stage 2 |

## 4. Decisions for Ethan

1. Stage 1 links carry fixed choices only, no free text. (Recommended.)
2. Done: S1 (official advice counts as news for date alerts) merged as #411 and the Worker deployed, 27 Oct.
3. Add the five stage 0 questions to the interview script.
4. Which river and which two clubs for the pilot.
5. Stage 2: names visible to the organiser only, or to everyone with the link.
6. Whether stage 2 is worth the Ofcom check and DPIA at all, or stage 1 plus the atlas is enough for 2027.
7. Clubs: keep them free as a channel (the 20 Oct plan), or test a club price in the interviews (section 5).
8. A paid personal tier: recommended no, for 2027 (section 5).

## 5. Money: the third proposal

The proposal: Free (forecasts, notices, basic access, joining outings); Personal Plus at £25–40 a year (advanced planning, offline trip packs, synced plans, custom alerts, trip history); Club at £15–30 a month (recurring outings, attendance, waiting lists, updates, briefings, cancellation); operator tools and booking referrals later. Its strongest bet is the club product, piloted with a swim club, a SUP group and a kayak club in one region.

**In short:** the club bet fits this plan's stage 2 and is worth testing, but it reverses a standing decision. The personal tier conflicts with two others and sells what competitors already sell. No paid feature gets built before a club commits in writing, as the 24 Oct rule already says.

### Where it meets decisions already made

| Proposal | Standing decision | Where |
|---|---|---|
| Club tier at £15–30 a month | "Clubs stay free, as a channel." Centres and event organisers are the ones asked to pay | `docs/ORGANISER-PIVOT-2026-10.md` §2 |
| Personal Plus | "Swimmers stay free. Nothing a swimmer sees today goes behind a payment." Plus would add new features, not lock old ones, so it may not break the letter of this. It breaks its intent | `docs/MARKETS-2026-10.md` §2; ORGANISER-PIVOT, revision item 4 |
| Synced plans, trip history | "No accounts, no cookies and no advertising" on the privacy page. Syncing needs accounts | `pages/privacy.html` line 22 |
| Asking clubs to pay for a pilot | "No pre-invoice spending until someone commits" in writing | ORGANISER-PIVOT, revision item 2 |
| Paid placement for lessons and hire | Open-Meteo's free API excludes sites with advertising; ask Open-Meteo first, as for a sponsor | ORGANISER-PIVOT, revision item 3 |

**The cost floor.** Taking any money brings in Open-Meteo Professional (€99 a month), insurance, the ICO fee and CARTO's commercial terms: about £100–130 a month before a solicitor or a company (ORGANISER-PIVOT §3, inferred there). At £15–30 a month per club, that is 4 to 9 paying clubs to cover running costs alone (arithmetic). River Truth, the nearest UK price, sells clubs a live dashboard at £15 a month (checked 3 Oct 2026).

### What competitors sell (checked 27 Oct 2026 in the browser)

- **PaddleWays** (paddleways.com, its pricing page). Free: water access, rapids and hazards, live weather and streamflow, trip tracking, private waypoints and routes, public comments and images. Plus, $49.99 a year: offline and 3D maps, unlimited "My Waters" conditions monitoring, geofenced alerts, private property parcels. It lists English rivers (the Thames, Lea, Mole and others showed as "Waters near you").
- **PaddlePoints** (gopaddling.info, Paddle UK's site). Free without an account: launch points, routes, hazards, comments and images, river and canal pages with licence information. Its page says "Many waterways in England and Wales require a licence to paddle".
- **Windfinder** (windfinder.com/apps). Has a paid tier, Windfinder Plus. The page lists wind alerts under the Plus upgrade, but the wind alerts section itself is not marked Plus, and no prices are shown. Not settled.

What follows, inferred:
- **Personal Plus would sell what PaddleWays sells**, against a free tier that already covers the basics. SwimSignal already gives its offline copy (`sw.js`) and its alerts free. What nobody else has is the sewage forecast and official notices tied to a plan. That belongs in the club product and the free site, not a personal paywall.
- **The paddlers' launch atlas exists, free, from the governing body.** Rebuilding PaddlePoints would be slow and second-best. Link to it from paddling spots, and ask Paddle UK whether the two can link both ways. Keep atlas work (stage 3) on swim spots, where SwimSignal's 49 guides are ahead.
- **Licences.** A SUP or kayak plan on a navigation should say a licence may be needed and link PaddlePoints' river page. The site says nothing about licences now (grep of `src/dipcast`, 27 Oct).

### The proposal's other ideas, against what exists

| Idea | Exists now | Gap |
|---|---|---|
| "Find a window": Sunday afternoon, a board, 45 minutes' travel | Plan a swim: a day, a place and a straight-line radius of 5, 10, 20, 30 or 50 miles, and the kind of water (`plan.js`, `RADII`) | Activity: cheap. Travel time: needs a routing service, not checked. Afternoon: the forecast gives one level a day (`outing.js` says so) |
| Access journey: parking, carry, launch, exit | Guide facts by topic: parking 84, path 50, entry 42, exit 1. No photos | Order them as a journey on the spot page; `carry` and `launch` topics (stage 3) |
| Trip organiser with seats and checklists | Stages 1 and 2 | Seats and checklists wait (section 3, "Not now") |
| Conditions notebook | Visit notes, with expiry and reconfirmation | Paddlers' ticks (stage 3) |
| Club-maintained guides | Guides keep "Verified" apart from a swimmer's suggestion, each fact sourced and dated | A club as a named source, reviewed by Ethan. A cheap pilot perk |
| Lessons and hire beside a plan | Nothing | Advertising question to Open-Meteo first; later |

### What to do

1. Add three questions to the stage 0 interviews: what the club uses to organise now and whether it pays for it; what an organiser's time on it costs them each week; and whether the club would pay £15, £30 or nothing for stage 2's list and change prompts. Record the answers as they come; quote no price before the question.
2. Widen the stage 2 pilot to a swim club, a SUP group and a kayak club in one region, as proposed, if the interviews find them. Free during the pilot.
3. Ask for money only when one club says in writing it will pay a named price for a named scope (the 24 Oct rule). Then the costs in ORGANISER-PIVOT §3 start.
4. No personal tier in 2027.

## 6. Sources and checks

- Online Safety Act 2023, Schedule 1 paragraph 4, legislation.gov.uk, read 27 Oct 2026.
- Code on main at c8eac36, read 27 Oct 2026: files named in section 1.
- Usage figures: Cloudflare Web Analytics and the push KV, 24 Oct 2026, not rechecked.
- PaddleWays home and pricing pages, PaddlePoints' UK page and Windfinder's apps page, read in the browser pane on 27 Oct 2026.
- Not checked: Strava Beacon (cited in the first proposal); Ofcom's checker; Open-Meteo's cost for wind; car-share insurance; the cost of a routing service for travel time.
