# SwimSignal: a critical review of the site, the product and the way to a business

Written 6 November 2026 from the live site, the repo, the private measurement folder and the strategy
documents. Facts are marked as established (read from a source that day) or inferred (my reading of
them). Where a number came from a sampled analytics query, it says so.

## The verdict in ten lines

1. SwimSignal has a real engine and no audience. About 420 visits a week, 42% of them from Ethan's
   Facebook posts, one push subscription, no reviews, no visit notes, and no spot request ever.
2. The product has been built outward for eight weeks (about 2,100 commits, 246 spot pages, 1,361
   overflow pages, 30 top-level pages, five research exhibits, tools for five markets) without one
   completed loop with a real user. No comprehension session has run. No organiser has been interviewed.
3. The forecast, the thing the site is named for, does not yet beat simple rules. On the live record no
   water company passes the promise rule; same-day persistence beats it. The honest line this winter is
   "shows what the upstream monitors say now; the forecast is still being tested". That is the line the
   product must be built around, not apologised for.
4. The parts that are solid are data, not forecast: every monitored overflow upstream of any inland point,
   its live status, its spill record, plain names, and public scoring. Nobody else does that at any point.
5. The consumer slot is taken. Wild Open Water sells conditions at £29.99 a year with apps, 23,000 spots
   and 40,000 community reports. Surfers Against Sewage gives alerts free to 150,000 users. SwimSignal
   cannot win as a consumer app and should not try.
6. The defensible position is the inland sewage-risk engine behind other people's audiences and behind
   organisations with a duty of care: event organisers, activity centres, councils with inland bathing
   waters, and the apps and charities that already have swimmers.
7. Money will be small for a long time. Ten centres at £79 a month is £790 a month against a cost floor of
   about £130. This is a side business or a grant-backed public good, not a salary. Choose which, because
   the choices conflict (a CIC cannot also be a product company without care).
8. The site looks professional on a desktop. It reads like a research notebook: three names for the level,
   caveats in every tile, "experimental", "provisional", "trial" and "exploratory" above the fold, and
   a Research Lab given the same billing as the forecast. Polish here means cutting, not adding.
9. Growth has one free channel that scales: search. Spot pages are the asset. On 24 October the sitemap was
   "discovered, not indexed". Until spot pages rank for "[place] swimming", traffic is whatever Ethan posts.
10. Every path to money and evidence is blocked on steps only Ethan can take: the employer check, ten
    interviews, eight comprehension sessions, a phone test of push alerts. Agents cannot do them.

## 1. What is true today

### 1.1 Usage (established, private measure folder, Cloudflare Web Analytics with confidence intervals)

| Week | Visits | Page loads | From Facebook | From Google | Direct or none | Spot-page visits | Push subs | Reviews, notes, reports |
|---|---|---|---|---|---|---|---|---|
| 19 to 25 Oct | 164 | 265 | 69 | 9 | 81 | 65 | 1 | 0, 0, 0 |
| 26 Oct to 1 Nov | 417 | 730 | 143 | 12 | 243 | 176 | 1 | 0, 0, 0 |

- Two spots took 108 of the 176 spot visits (Stainforth Force 63, Sheep's Green 45). Both were in group
  posts that week. The Lake District focus area took 14, the same as the week before.
- 115 of 417 visits came from the United States. The weekly note infers crawlers or link previews.
- "Visits" are arrivals, not people. Repeat use cannot be measured with the current setup.
- Google sent 12 visits in the week. On 24 October a `site:` search found only the home page, and the
  sitemap's 225 URLs were "discovered, not indexed".

Inferred: the audience is the people who read a Facebook post that week. Nothing yet shows a swimmer
coming back without being prompted.

### 1.2 What ships (established, inventory of the build, 6 Nov)

- 123 spots live (93 in `spots.csv`, 18 from OpenStreetMap, 12 in the Scotland trial). The README still
  says 105 and 16.
- 246 spot pages (each with a profile and a sign page), 1,361 overflow pages, `/plan/`, `/saved/` (lists,
  compare, journal, passport, alerts), click-anywhere forecasts, and about 30 static or scripted pages:
  accuracy, method, about, terms, privacy, feedback, testing, coverage, data, clubs, partners, research,
  support, organisers, sites, demo, record, quality, lakes, lake-temperatures, durations, samples,
  waterhead, research-catalogue, sampling-planner, models, and a five-exhibit Research Lab.
- A spot page shows, in order: headline level, five-day strip, where it comes from, upstream map, what the
  forecast cannot see, conditions, day tiles, live spills, rain, weather, water temperature (measured at 4
  spots, estimated elsewhere), river level, E. coli estimate (out of season now), past samples, algae, EA
  rating, evidence and history (six sub-sections), practical guide (57 of 123 spots), nearby, visit
  notes, reviews, illness reports, lab exhibits, actions, technical details.
- Hidden prototypes behind URL flags: replay, evidence map, "since you last looked", arrival guide.
- Workers: push alerts (deployed; date alerts switched on 31 October without a real-iPhone test), reviews
  and visit notes (deployed, hand-moderated), Ask (not deployed). Email alerts built, off. Partner
  sample intake not deployed. The API server was removed on 20 October.
- Hosting is still GitHub Pages, whose terms bar running a business. The Cloudflare Pages move waits on a
  token. Builds run about every 4.6 hours (median), not every 30 minutes as the cron asks.
- Degradations the build reports today: the EA bathing-water service returns 403 (archive fallback), the
  Wales directory has been a cached copy since 3 October, coastal advice unavailable, one official-advice
  item stale.

### 1.3 Accuracy (established, accuracy page built 6 Nov 23:22, and the usefulness read of 24 Oct)

| Measure | Figure |
|---|---|
| Forecasts scored live since 29 Sept | 146,618, on 31,153 overflow-days |
| Spills warned of at the High line | 35% |
| Warnings followed by a spill | 50% (base rate 5.8%) |
| Brier error against each overflow's long-run rate | 24% lower |
| Against the best simple rule, leads 1 to 4, all companies | skill 0.07 (−0.05 to 0.12) |
| Same day, against persistence | −0.05 (−0.19 to 0.17) |
| Thames Water, in advance, against rain over 10 mm | −0.10 (−0.47 to 0.02) |
| Ranking (AUC), same day and in advance | 0.88 and 0.84 |
| Held-out 2025 test, United Utilities only | 93 pairs in 100 ranked right |

No company passes the promise rule. The forecast ranks well and warns poorly. The 93-in-100 figure
on the README and accuracy page is the one most likely to be read as "93% accurate"; it is a ranking on
one company's data.

E. coli: 160 forecast-sample pairs, "no better than the average rate so far, too few to judge". The first
full season to judge it is May to September 2027.

### 1.4 Competition (established, read 6 Nov and 3 Oct)

| Who | What | Model |
|---|---|---|
| Wild Open Water | 23,000 spots, water temperature, waves, tides, river level, apps, community (40,000 reports), 7-day conditions | Free tier plus Pro at £3.99 a month or £29.99 a year; ad-funded (141 ad partners on its consent banner); uses Open-Meteo |
| Surfers Against Sewage, SSRS | Alerts after a discharge at 450 locations, illness reports | Charity, free, 150,000+ users |
| Islandswim | 24-hour score at 942 bathing waters, private spots, single worst outlet | Free |
| SewageMap | Downstream trace of live and 48-hour spills, England and Scotland | Free, academic |
| Yorkshire Water + UnifAI, Wessex Water Quality Live | Sensor and ML hourly E. coli at 3 and 20 river sites | Water company funded |
| River Truth | Council dashboards | £49 to £150 a month per council |

What only SwimSignal does: every monitored overflow upstream of any inland point, summed with travel,
die-off and dilution, five days ahead, with each forecast scored in public. What SwimSignal does not have:
an app, photos, a community, breadth beyond England's rivers, a demonstrated forecast edge.

### 1.5 Constraints before any money (established, markets plan, organiser pivot, monetisation notes)

- Ethan's employment contract check comes first. A no ends the plan. It has not been done.
- Open-Meteo's free tier is non-commercial. The build calls the ensemble API, so a commercial site needs
  Professional at €99 a month. Tips are allowed (confirmed 15 Oct). Whether a sponsor counts as
  advertising is unasked.
- CARTO tiles: free to 1M a month, then US$500 a month; a business's public map counts.
- GitHub Pages bars businesses. The terms, every footer and the embed licence say "free, non-commercial,
  not a company".
- PECR: sole traders and clubs cannot be cold-emailed; companies can.
- Liability: injury liability cannot be capped (UCTA s.2(1)); the customer must always be the decision
  maker. The draft pilot agreement exists privately; no solicitor has read it.
- Cost floor as a business: about £100 to £130 a month before a solicitor, insurance or a company.
- The code stays public under MIT (decided 24 Oct). Pilot-only work goes in a private repo that does not
  yet exist.

## 2. The diagnosis

Established facts above. What follows is inference.

**The build rate replaced the learning rate.** Eight weeks produced a product with more surface than
Wild Open Water and fewer users than a village noticeboard. Every strategy document ends with "Ethan's
items": interviews, sessions, the employer check, a phone test. None has happened. Meanwhile the parts
that agents can do (features, tests, exhibits, pages) have run far ahead. The result is a product that
answers questions no user has asked, written in the voice of its own research log.

**The headline promise is the weakest part.** The site is named for a forecast and leads every page with
it. The forecast's own scoring page says it misses most spills and does not beat a rain rule. The strongest
part, an exact and plain account of what is upstream and what it is doing now, is the third tile down.

**The markets plan sells the forecast to people who need a record.** British Triathlon's guidance asks
organisers to know the overflows upstream and be told when they discharge. That is monitoring and a
record, which SwimSignal does well. The pivot documents talk about a briefing with a forecast in it. Sell
what is true.

**The consumer product competes on the wrong axis.** A swimmer choosing where to go wants a photo, the
water temperature, parking and whether friends go there. Wild has all of that at 23,000 places. SwimSignal
has sewage risk at 123 places. Depth on one risk does not win a consumer against breadth on every
condition, and the no-ads, no-accounts promise rules out Wild's two revenue lines anyway.

**The honest hedging has become the design.** "Experimental", "provisional", "trial", "exploratory", "not
a water test", "what this means" seventeen times on one page. Each is defensible. Together they tell a
first-time visitor that the author does not trust the product. A professional site states its limits once,
clearly, and then speaks plainly.

## 3. The position to take

One sentence: **SwimSignal is the independent, publicly scored record of sewage risk at any inland
swimming point in England, used by swimmers for free and relied on by the organisations responsible for
people in the water.**

What changes under that sentence:

- The record (upstream overflows, live status, spill history, scored forecasts) is the product. The
  forecast is a feature of the record that is being tested in public. The wording flips from "forecast,
  caveat" to "record, plus a forecast under test".
- The consumer site stays free, with no ads and no accounts, as the public face and the proof. It is not
  where the money is.
- Organisations pay for the record in a form they can file: a dated, named, signed-off account of what was
  upstream, what it was doing, and what the site said, for a venue and a day or a season.
- Other apps and charities license the engine. Wild gives undesignated spots "nothing rather than a guess".
  SwimSignal has a scored guess for every inland point. That is a feed, not a competitor.

## 4. Who to target, in order

1. **Repeat swimmers in three catchments** where traffic already arrives and the model is strongest:
   Windermere and the Lake District (United Utilities, where the model was trained; Tim Boden's samples;
   the Great North Swim), the Wharfe (Ilkley, Burnsall; Yorkshire Water), and the Cam and Oxford Thames.
   Purpose: evidence of repeat use and of a changed decision, not revenue.
2. **Inland event organisers** for the 2027 season: Chillswim and Epic Events (Windermere, Coniston,
   Ullswater), the Great North Swim, Swim Oxford, Bedford, Henley, Marlow. Each has a date, a venue and a
   duty to document. Price per event or per season.
3. **AALA-licensed activity centres** in the Lakes and Dales, year-round, with a written risk assessment to
   maintain. The batch-1 interview list already names five. Price per month, winter included.
4. **Apps and charities as data customers**: Wild Open Water, SAS, The Rivers Trust, Islandswim. One
   conversation each about a licensed feed of spill risk for inland points. This is the only route that
   borrows an audience instead of building one.
5. **Councils with inland bathing waters** (about 50 after the 2026 designations) from 2027, once there is
   a season of scored E. coli forecasts to show.
6. **Water companies** not before the October 2027 scores, and only with the independence rule intact.

Not targeted: paddling clubs as payers (keep as a channel), anglers, dog walkers, Scotland, Wales and
Ireland (directories only until the data exists), a personal Plus tier.

## 5. The product: cut, fix, then add

### 5.1 Cut or hide (make the site read as one thing)

- Take Research Lab out of the top navigation and off the home page. Link it from About and the accuracy
  page. Research is credibility, not a destination.
- Hide the market and tool pages behind one "For organisations" page: organisers, clubs, sites, record,
  demo, partners. One entry point, one pitch, one contact.
- Fold the data and research pages (quality, lakes, lake-temperatures, durations, samples, waterhead,
  research-catalogue, sampling-planner, models) under Research & data. Keep them; stop linking them from
  the product.
- Remove the Scotland trial from the hero sentence. Either it is covered or it is not. "123 spots in
  England and Scotland" with the trial explained on the coverage page.
- Retire the hidden prototypes (replay, evidence map, "since you last looked", arrival guide) or ship them.
  Dead flags are maintenance.
- Switch off date alerts until they have run on a real iPhone. One subscriber in six weeks means the
  feature is either broken on phones or unwanted; find out which before leaving it on.

### 5.2 Fix (polish is consistency)

- **One name for the level.** The site says "pollution risk", "sewage spill risk", "risk from sewage
  spills" and "pollution risk forecast" on the same page. Pick "sewage risk" and use it everywhere,
  including the title tags.
- **Lead with what is known.** On a spot page where live status is known, the first line after the name
  should be the live fact ("1 overflow upstream. Not spilling at 23:22."), then the five-day line. The
  forecast caveat appears once, in one sentence, with a link to the accuracy page.
- **Say the limits once.** Replace the per-tile "what this means" links and the repeated "a forecast, not a
  water test" with one "How to read this page" fold at the top of the evidence section. Keep the legal line
  in the footer.
- **Winter tiles.** A tile that says "Out of season" or "Provisional estimate" should not be a tile. Show the
  E. coli estimate only in season. Show the water temperature with the measured-or-estimated word inside
  the figure's caption, not as a label above it.
- **Home page copy.** The hero has two sentences, a link, and a third explanatory sentence under the day
  strip. One sentence: "Sewage risk for the next five days at 123 river and lake swim spots, and anywhere
  you click." The day strip needs no explanation if it is labelled "spots at low risk".
- **Footer credits.** The data credit paragraph is 90 words on every page. One line and a link.
- **Stale counts.** README, About and the hero disagree on the number of spots. Generate every count from
  the build.
- **Photos.** Every competitor shows the place. Geograph photos are CC BY-SA and cover most of these spots.
  One photo per spot, credited, changes the site from a dashboard into a place.
- **Design.** The typeface pair, the slate header and the sky picture are good and should not change. The
  "frosted tile" treatment is applied to too many tiles; keep it for the forecast and the map, and let the
  rest be plain text on the page.

### 5.3 Add (only after 5.1 and 5.2)

- A measured funnel that keeps the privacy promise: a cookie-free counter in a Worker for six events
  (spot opened, day picked, saved, plan used, alert subscribed, "changed my plans" sent). Cloudflare Web
  Analytics cannot answer "did anyone come back".
- Spot page structured data (Place, Dataset) and unique first-paragraph prose per spot, written once by
  hand for the 40 most-searched places. This is the search asset.
- "For organisations": one page, one form, one example record, one price sentence after interviews.
- An alert-feedback button ("was this warning useful?") on each push notification, which the interview
  plan already lists as an open question.

## 6. Growth: how people will find it

Established: Facebook posts produce a spike that decays within the week. Google sends about a dozen visits
a week. The sitemap was discovered and not indexed in October.

The only channel that compounds without Ethan's time each week is search for place names. People search
"[place] wild swimming", "is the [river] safe to swim", "[lake] water temperature". Each spot page can own
those queries if it has unique prose, a photo, the practical guide, a stable URL and internal links from
nearby spots and area pages. Wild Open Water's traffic is built this way.

Targets to carry over from the winter plan, with the dates it set: 50 spot pages indexed by 6 December;
400 visits in four weeks with a third from search by 31 January; 1,000 visits a week in three of six
weeks from 15 May. Add one: by 31 March, search beats Facebook as a source.

Posts keep a role: one post per storm, in the group for the catchment where overflows are discharging, with
the live map. The storm-day kit exists. Posts in a dry week are noise.

## 7. Monetisation: the sequence and the numbers

| Step | When | Revenue scale | What must be true first |
|---|---|---|---|
| Tips (Ko-fi) | Live | Tens of pounds a year at this traffic | Nothing |
| Ten exploratory interviews | Now to 31 Jan 2027 | None | Employer check |
| Data feed conversations with Wild, SAS, Rivers Trust, Islandswim | Jan to Mar 2027 | £0 to low thousands a year per licence (inferred; no price discovered) | A documented feed, a licence that lets each use it, Open-Meteo Professional |
| Season records for organisers | Season 2027 | £150 to £300 per event, 10 to 20 events: £1,500 to £6,000 | Solicitor-read record, insurance, a company, terms rewritten, Cloudflare hosting |
| Monthly monitoring for centres | From spring 2027 | £49 to £99 a month, 5 to 10 centres: £3,000 to £12,000 a year | Same as above |
| Council dashboards | 2028 | River Truth charges £49 to £150 a month; councils buy slowly | A season of E. coli scores |
| Sponsorship | After a measured 2027 season | Unknown; needs the audience first | Open-Meteo's answer on advertising; 1,000 visits a week |
| Grants (CIC route) | Any time | £5,000 to £50,000 per award (inferred from typical Lottery and trust awards) | A CIC, a mission statement, and the decision not to be a product company |

Established costs as a business: Open-Meteo €99 a month, CARTO US$500 a month past 1M tiles, ICO £52 a
year, insurance unquoted, a solicitor's read unquoted. Inferred floor with insurance: £2,000 to £3,000 a
year.

Plain reading: the organisation route can cover costs and a modest surplus by the end of 2027 if ten
interviews turn into five customers. It will not pay a salary. The data-feed route is the one with a
ceiling above that, because it borrows audiences of 150,000 (SAS) and 23,000 spots (Wild). It is also the
cheapest to test: three emails.

The CIC question should be settled before the first invoice, not after. A CIC with an asset lock can take
grants and water-company community money without the independence problem a company has. A company can
take investment and sell licences. Doing both is possible with a trading subsidiary and is more than a
one-person project should carry. My recommendation: a company, licences and organisation fees, and no
water-company money; revisit the CIC only if the licence conversations all fail.

## 8. Research: what to pursue and what to stop

The register already archives most variants. Rank what remains by one question: does it raise the live
skill against simple rules at leads 1 and 2, which is what unlocks the word "forecast" in a sales
conversation?

Pursue, in order:

1. **Adopt the live-status input** (PR #254, #639). It passes all five pre-registered conditions at every
   lead on 2025 and 2026 data. The switch is drafted and off, waiting on Ethan after 23 November. This is
   the one tested change that targets exactly the weakness the usefulness read found.
2. **Company calibration (A8, PR #333).** The forecast runs high, and eight companies carry a United
   Utilities model. The frozen offsets read on 25 November. If they hold, deploy them.
3. **Report persistence and rain-rule baselines live** on the accuracy page, with intervals, so that in
   April the claim "beats a rain rule" can be made or withheld on the record. The 2027 preregistration
   uses only a climatology reference; the amendment the usefulness read proposed should be filed now.
4. **Regional routing** (shadow, PR #490). Read it when its window closes; adopt only if it moves the
   non-UU companies.
5. **Independent E. coli ground truth for 2027.** The E. coli estimate is the only route to saying
   anything about water quality rather than spill risk. Tim Boden's plates, Fluidion, and the partner
   intake (built, not deployed) are the way to get samples the EA does not take. Deploy the intake.

Stop or leave archived: satellite chlorophyll and algae (A fails, B too few, low-signal candidates
exploratory), neural challengers (worse twice), lake direction and own-rate (all fail), radar at each
overflow (verdict N), sea currents (no model to add it to), concentration study (ties production),
dry-weather spills (fails Q1 and Q2). Keep the Research Lab as a record of them. Spend no more build
time on lake exhibits until a lake user asks for one.

The five "ambitious directions" scoped on 1 November should wait until the five items above are read.
A new direction that cannot change the leads-1-to-2 skill figure by spring is a 2028 project.

## 9. The next ninety days

Ethan only (nothing below unblocks without these):

1. Employer check on outside work and press. One conversation or one clause.
2. Send the five batch-1 interview emails from hello@ (drafted, PECR-checked).
3. Run the first two comprehension sessions with the Lake District panel.
4. Test push alerts on a real iPhone. Switch date alerts off if they fail.
5. Decide: company or CIC. Decide: data-feed conversations yes or no.
6. Read the live-status switch after 23 November and the A8 offsets after 25 November.

Build (agents, in PRs against main, in this order):

1. Navigation and home: Research Lab out of the top nav; "For organisations" as one entry; hero to one
   sentence; footer credit to one line; counts generated from the build.
2. One name for the level, swept through every template and title tag.
3. Spot page: live fact first; limits said once; winter tiles removed; one photo per spot from Geograph
   with credit; unique opening prose for the 40 most-visited or most-searched spots.
4. Cookie-free event counter in a Worker; the weekly count reads it.
5. Persistence and rain-rule baselines on the accuracy page, with the preregistration amendment.
6. Deploy the partner sample intake.
7. A one-page feed description (what a licensee gets, update cadence, licence, attribution) for the
   data-feed conversations.

Measure (already scheduled weekly): visits, source share, spot visits by area, indexed pages, push
subscriptions, and the new six events.

## 10. What this review did not check

- Search Console figures (Ethan's account): how many spot pages are indexed today.
- Facebook insights, Ko-fi totals and the hello@ inbox.
- The phone layout, beyond the October QA record; the browser window would not resize for this review.
- Whether Open-Meteo would treat a licensed feed as commercial use of the ensemble API (it would, on
  the FAQ's wording; unasked).
- Prices any app or charity would pay for a feed. None was found; the table above says so.
