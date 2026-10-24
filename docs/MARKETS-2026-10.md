# Beyond swimmers: five markets, October 2026

How SwimSignal serves five groups besides swimmers, what to build for them, and in what order. Written
on 5 October 2026 after a market review (three research agents; key facts re-checked as marked). Read
with the launch kit (private page, link in Claude's memory) and `docs/ROADMAP-2026-10.md`.

Marks: **[checked]** I opened the source on the date given. **[agent]** a research agent opened it on
5 Oct 2026 and I did not re-check it. **[inferred]** my reasoning, not a fact.

## 1. Summary

The five markets, in order of priority:

1. **Open-water and triathlon event organisers.** They must already test the water and decide whether
   the swim goes ahead.
2. **Outdoor activity centres, Scouts, DofE and schools.** They write a go/no-go decision into a risk
   assessment for every water session.
3. **Councils and groups applying for bathing-water status.** The application deadline is
   **15 October 2026**.
4. **Paddling clubs.** Paddle UK's own guidance asks the two questions SwimSignal answers.
5. **Water companies and public funders.** They have money, but build their own tools. Approach them
   only after the 2027 season's scores.

The plan in one line, as revised on 24 October 2026: exploratory interviews with activity centres and
event organisers this winter, no money spent on charging until one of them commits in writing, and a
sponsorship test once the 2027 season has a measured swimmer audience. The forecast's limits are stated
first, and the 2027 season's scores are still the test of whether it is good enough. Section 6a has the
revision. Before it, on 20 October, the plan was paid pilots this winter; before that, free pilots and
no charging before October 2027.

Most of what they need exists already: the organisers' page, the signs, the embed, shared lists and
click-anywhere. Five shared pieces of work (section 4) cover most of the gap. Each market then needs
one small piece of its own (section 5).

## 2. Rules that hold for every market

- **Swimmers stay free.** Nothing a swimmer sees today goes behind a payment.
- **One forecast for everyone.** An organisation never gets a different level from the public page. It
  gets the same forecast, organised for its decision.
- **Say what it cannot do, every time.** At the High level the live forecast warned of 21% of spills,
  and 41% of its warnings were followed by a spill (live scores, 29 Sep to 4 Oct 2026). It is a planning
  aid, not a safety certificate. Every page and printout for an organisation says so in its first lines,
  never "safe" or "clean".
- **Independence from water companies.** No money from a water company may buy anything that changes a
  forecast, a level, a score or which spots are covered. The About page would say so before any such
  deal.
- **Nothing is charged before these are done.** The README section "Before taking money or
  running ads", lists them:
  - a company, either a Ltd, or a CIC, which also opens National Lottery grants;
  - public liability and professional indemnity insurance;
  - Open-Meteo's paid plan, from €29 a month, because its free plan excludes sites with subscriptions
    or adverts;
  - paid parts hosted off GitHub Pages, whose terms bar running a business;
  - business terms reviewed by a solicitor;
  - a check of Ethan's employment contract.
- **The terms change first.** Since PR #93 the terms let only non-commercial sites embed the card.
  Commercial events and hire centres need a written exception for pilots (open question 3).

## 3. What each market can use today

| Already built | Events | Centres | Applicants | Paddling clubs | Water companies |
|---|---|---|---|---|---|
| Organisers' page: a spot and a day, that day's level, the overflows upstream as a table and CSV, a checklist from British Triathlon's and Swim England's guidance, a print layout | Yes | Yes | | | |
| Printable QR sign per spot, live sign for a screen | Yes | Yes | | Yes | |
| Embed card for a web page | Yes (terms) | Yes (terms) | Yes | Yes | |
| Named lists of spots, shared by link | | Yes | Yes | Yes | |
| Click-anywhere for points off the list | Yes | Yes | Yes | Yes | |
| Push alerts for saved spots; email alerts (built, off) | Yes | Yes | | Yes | |
| River level, flood alerts, water temperature | Yes | Yes | | Yes | |
| Public data files, accuracy page with scores by company | | | Yes | | Yes |
| Practical guides (access, parking, entry points) | Yes | Yes | | Yes | |

## 4. Five shared pieces of work

Build these once. Each serves several markets.

**B1. Overflow names in plain words.** Names arrive as "Addingham/NO 1 SPS/Preliminary
Treatment-STW/6Xdwf Overflow". Show a plain name first ("Addingham sewage works overflow") and keep the
company's name beside it. All markets read these tables, and the first-time-user review of 5 Oct 2026
flagged them.

**B2. A sites view for an organisation.** Open a shared list as a table of an organisation's launch
points, with each site's five days, the reason, and the issue time, on one printable page. A centre or
club makes the list once, bookmarks the link and prints it before a session. Lists already live after
the `#` in the address, so nothing is stored and no account is needed.

**B3. A decision record.** A printable page for one site and one day:
- the level and why;
- each input with its age and source;
- what the forecast cannot see;
- when it was issued;
- blank lines for who decided what, and when.

It never says "safe". Organisers and centres write go/no-go decisions down already. This gives them
the evidence to attach. The wording needs a solicitor's read before anyone relies on it (open
question 4).

**B4. Alerts for a date.** "Tell me when 14 June enters the forecast, and again if its level
changes." This would be a new subscription type in the push Worker, for push and email. It needs a
privacy-notice update and a Worker deploy by Ethan.

**B5. A site profile.** One page per spot or clicked point:
- the overflows upstream, each with its spills and spill hours for each year 2021–2025, from the EA's
  annual returns (`data/processed/annual_returns.parquet`, OGL v3; credit in the terms);
- the share of past season days at each level, where the forecast log has them;
- for a designated bathing water, its EA samples.

The page is printable and carries a caveat in its first lines. Applicants, councils and water companies
use it; organisers use it to choose a venue.

## 5. The five markets

### 5.1 Event organisers

- **Who.** Open-water swims, triathlons, swimruns. Triathlon England had over 700 events in England in
  2022 [agent: British Triathlon annual report 2022].
- **Their rule.** British Triathlon's Water Quality Guidance (2025) makes the organiser responsible for
  water samples. It suggests tests a month, two weeks and a week before the event. It says testing
  before an event on a river "is likely to have limited value" [agent; the organisers' page already
  quotes this guidance].
- **What it costs them.** A UKAS E. coli test costs £141, or £110 each for four or more [agent:
  simplexhealth.co.uk]. Henley Swim said it was "effectively bankrupt" after water-quality fears cut
  entries [agent: Henley Standard, 9 May 2025].
- **What we add.**
  - An **event week** on the organisers' page. Months ahead, it gives the lab-test dates from British
    Triathlon's schedule, with a calendar file to download. Inside five days, it shows the daily levels
    already there.
  - B4 alerts for the event date.
  - B3 for the race-day decision.
  - B5 when choosing a venue.
- **Reach.** British Triathlon's event-organiser team, Swim England, and the launch kit's event emails
  (Great North Swim, krono:sports Henley). Those are ready, and wait for the pilot season.
- **Pilot.** Paid since 20 Oct 2026 (section 6a); first written as free for 3 to 5 events in the 2027 season. In return: their own lab results, which score
  the forecast, and a written view of whether it changed a decision.
- **Price, later (hypothesis).** A season or per-event fee well under the cost of one lab test.
- **Measure.** One written pilot by 30 April 2027, the launch kit's gate.

### 5.2 Outdoor activity centres, Scouts, DofE and schools

- **Who.** 956 AALA-licensed providers; 5,023 DofE licensed organisations, with 345,908 starters in
  2025–26 [agent: AALA register; DofE annual statistics].
- **Their rules.**
  - Scouts: "No water based activity should proceed if there are any concerns around water
    contamination" [agent: Scouts guidance, Jan 2022].
  - The outdoor-education guidance OEAP 7.2i points leaders to SewageMap and the SAS app [agent: OEAP,
    12 Aug 2025].
  - Girlguiding checks for visible pollution only [agent].
- **What it costs them.** One YMCA centre stopped water activities for 10 days and cancelled "more than
  1,000 sessions" [agent: Hansard, Lords, 29 Feb 2024].
- **What we add.**
  - B2, a sites view of the centre's launch points, five days ahead, printable before a session.
  - B3 for the risk assessment.
  - A short "for leaders" note: what each level means for a group of children, what to do on a high
    day, and the 0800 80 70 60 incident line.
- **Reach.**
  - Ask OEAP to list SwimSignal next to SewageMap in 7.2i.
  - The Institute for Outdoor Learning, to reach centres.
  - The Scouts' and Girlguiding adventure teams.
- **Pilot.** 3 AALA centres on rivers, winter and spring 2027, paid (section 6a).
- **Price, later (hypothesis).** About River Truth's club and council prices, £15 to £49 a month
  [checked 3 Oct 2026: rivertruth.co.uk/business].
- **Measure.** A centre that uses the sites view in a real decision, and says so.

### 5.3 Councils and groups applying for bathing-water status

- **Who.**
  - 449 designated bathing waters in England [agent: gov.uk, 25 Nov 2025].
  - 13 new ones in 2026, 7 of them rivers. Applicants include parish councils and river trusts [agent].
- **Their rule.** Applications close on **15 October 2026** [checked 5 Oct 2026, gov.uk "Designate a
  bathing water: guidance on how to apply"]. Defra's triage then judges "the likely water quality at
  the proposed site" and its "potential sources of pollution" [checked, same page].
- **What we add.** B5, the site profile: the overflows upstream with their spill history, which an
  application can cite.
- **The catch [inferred].** A profile can count against a site with many overflows upstream. Say so
  plainly to every applicant, before they ask for one.
- **Before 15 Oct.** B5 will not be built in time. The quick route:
  1. A script (task T8) writes a profile for a given point.
  2. Ethan emails the SAS team that supports applicants, offering free profiles. The draft goes in the
     launch kit.
  3. Each profile goes to an applicant who asks.
- **After 15 Oct.** Councils with designated waters can use B2 and B5 for monitoring and reports. River
  Truth charges councils £49 or £150 a month [checked 3 Oct 2026].
- **Measure.** Profiles used in this year's applications. A council pilot by 30 April 2027.

### 5.4 Paddling clubs

- **Who.** 401 clubs affiliated to Paddle UK in England, about 75,000 members [agent: Paddle UK annual
  report 2024].
- **Their rule.** Paddle UK's guidance asks "Has there been heavy rainfall…?" and "Are there CSOs
  upstream…?", and points to the Rivers Trust and SAS [agent: Paddle UK, 5 Nov 2024].
- **What we add.**
  - A **for clubs** page (task T7): the embed, the sign, the sites view, the decision record, and how
    each of Paddle UK's questions is answered.
  - A line saying the levels are about getting in the water, which matters for capsize drills and
    rolling.
- **Reach.** Ask Paddle UK to link SwimSignal in its water-quality guidance. The Clean Water Sports
  Alliance, founded by seven governing bodies, aims to help people make "real-time informed choices
  about where and when to participate" [agent: RYA, 28 Apr 2025].
- **Price.** Free. Clubs are a channel, not a customer [inferred from River Truth's £15 club price].
- **Measure.** A link from Paddle UK or the Alliance. Clubs that embed the card.

### 5.5 Water companies and public funders

- **Who.**
  - Severn Trent said in 2022 it was building its own "forecasting model to feed into a public app"
    [agent].
  - The EA's Shropshire Wild Bathing app came from a region funded with £4m by DSIT [agent].
  - Ofwat's Breakthrough 7 needs a water company to lead and closes at noon on 5 January 2027 (launch
    kit, checked 29 Sep 2026). The kit has a ready email to United Utilities (`e-uu-ofwat`).
- **What we add, after the 2027 season.**
  - An independent report of how well the forecast did, per company. The accuracy page already scores
    each company.
  - B5 profiles.
  - A data feed of overflow spill probabilities under a licence.
- **Conflict.** The forecast is partly about their own spills. Any deal must follow the independence
  rule in section 2.
- **Now.** Only the Breakthrough 7 email, if Ethan wants a partner bid this winter (open question 5).
- **Measure.** One conversation that names a budget, after October 2027.

## 6. Timeline

| When | What | Gate |
|---|---|---|
| By 15 Oct 2026 | T8 profiles for applicants; email to SAS's applicant support | Profiles sent to anyone who asks |
| Oct–Nov 2026 | T1 plain names, T2 sites view, T3 decision record, T7 for-clubs page. Emails to OEAP, the Institute for Outdoor Learning, the Clean Water Sports Alliance, Paddle UK and British Triathlon. Terms exception for pilots | Pages live; replies logged in the kit |
| Nov 2026 – Jan 2027 | T4 event week, T5 date alerts, T6 site profile page | Ethan deploys the Worker |
| Now | Employment contract check (section 6a item 1) | Written confirmation from the employer |
| Nov 2026 – Jan 2027 | Ten exploratory interviews: six centres, four organisers (section 6a). Councils get free profiles | Ten notes written up by 31 Jan 2027 |
| After a written commitment | Section 6a items 2–9, then that customer's pilot | Every item done before the first invoice |
| 15 May – 30 Jun 2027 | Swimmer use measured by region | Six weeks of figures |
| From Jul 2027 | Sponsorship test, if the figures support it | One sponsor pays, or the test ends |
| By 1 May 2027 | The 2027 test is frozen | Test registered |
| May–Sep 2027 | Pilots run; organisers' own lab results collected | Results logged |
| Oct 2027 | Season scores published. Pricing decided. Water-company offer, if the scores justify it | The launch kit's October decision |

## 6a. Paid pilots, winter 2026–27 (decided 20 October 2026, revised 24 October 2026)

**Revised 24 October 2026.** Interviews come first, and they are exploratory: about the centre's or
organiser's water-quality routine as it is now, not a pitch for the briefing. Nothing in the table below
that costs money is bought until a customer commits in writing to a named price and scope. Item 1, the
employment contract, still goes first because it costs nothing and a no ends the plan. Sponsorship is
tested from July 2027, once six weeks of the season's swimmer use have been measured by region.
`docs/ORGANISER-PIVOT-2026-10.md` ("Revised 24 October 2026") has the reasons and the phases. The rest of
this section is the 20 October plan, kept as the reference for what a pilot would be.

Ethan decided on 20 Oct 2026 to run paid pilots this winter, after an outside review argued for
organisation pilots before the 2027 season. Free pilots until the October 2027 scores was the earlier
proposal. Swimmers stay free (section 2).

**Who.** Commercial activity centres with several inland launch points first; event organisers beside
them. Clubs stay free, as a channel. Councils and water companies wait.

**The season problem [inferred].** Most open-water events run May to September, and many centres run
few water sessions in winter. A winter pilot is therefore mostly a centre that runs sessions now, or an
organiser who signs now for its 2027 dates. Expect fewer pilots in use before April.

**What is sold.** The same forecast as the public page (section 2), organised for the customer's
decision. A pilot is bounded in writing:
- a named list of sites (B2), set up for them;
- a briefing on the days they ask for, built from the sites view and decision record (B3), by hand at
  first;
- date alerts for their sessions or event (T5);
- a copy of every briefing as issued, with its issue time;
- a fixed end date and a short written review at the end.

It is not a safety certificate, a water test or a guarantee. The pilot agreement says so in its first
lines, with the live figures: outside United Utilities, the High line has warned of about 2% of spills
so far, 23 of 1,402 forecasts made for a day with a spill (verification page, 20 Oct 2026). Those are
forecasts, counted at each of up to five lead times, not spill days (PR #269). By 23 Oct, after a wet
week, it was 1,095 of 4,232, about a quarter, but still under 6% in Anglian Water's and Severn Trent's
areas (verification page, read 24 Oct 2026). The figure moves fast, so any document quotes it with its
date and by company.

**Prices to test (hypotheses, not evidence).** £49–£99 a month for a centre; £150–£300 an event. These
come from the 20 Oct review and are unvalidated. River Truth's live dashboards sell at £15–£49 a month
for clubs and councils [checked 3 Oct 2026]. Name the eventual price at the start of each pilot.

**Before the first invoice.** Each item names who does it. None is legal or tax advice.

| # | Item | Who | Notes |
|---|---|---|---|
| 1 | Check Ethan's employment contract for outside work, IP and conflict clauses | Ethan | First, because a no ends the plan |
| 2 | Choose a trading form: sole trader now, or a Ltd or CIC (open question 6) | Ethan | A sole trader can invoice at once [inferred]; a company limits personal liability. Register with HMRC either way |
| 3 | Professional indemnity and public liability insurance | Ethan | About £100–£500 a year, indicative (29 Sep notes); tell the insurer what the forecast is and is not |
| 4 | Pilot agreement and customer terms, read by a solicitor; decision-record wording (open question 4) | Ethan, with a draft from Claude | Uses section 2's caveat and the live figures |
| 5 | Open-Meteo paid plan, from €29 a month | Ethan pays; Claude checks the call count fits | Its free plan excludes sites with subscriptions [checked 29 Sep 2026]. Builds use about 8,600 calls a day since PR #243, inside Standard's 1M a month [inferred, recheck]. Historical API use by eval scripts needs Professional (€99) if it counts as commercial |
| 6 | Host off GitHub Pages | Claude builds, Ethan switches DNS | GitHub's terms bar an online business on Pages. Cloudflare Pages is the obvious move, since the domain is already on Cloudflare [inferred] |
| 7 | Change the site's own words | Claude | The terms and every footer say "free, non-commercial" and "not a company"; the embed and reuse terms allow non-commercial use only (open question 3) |
| 8 | ICO fee and privacy notice for customer contacts | Ethan pays, Claude drafts | £52 a year (29 Sep notes); the ICO self-assessment settles whether it applies |
| 9 | Payment: Stripe invoices or bank transfer | Ethan | Stripe 1.5% + 20p per UK card (29 Sep notes) |

**First steps, in order** (revised 24 October 2026).
1. Ethan checks item 1.
2. Ten exploratory conversations by 31 January 2027: six centres, four organisers. Each walks through
   their last water decision: what they checked, who checked it, how long it took, what they wrote down,
   what it cost them and who holds the budget. The briefing is not pitched. The script and the emails
   are in the launch kit.
3. Items 2–9 only after a customer commits in writing, and only for the scope they named.
4. A pilot for each customer who commits, with a written scope, end date and named price.
5. Build only what the pilots ask for more than once. Start from scheduled briefings, delivery to a
   team, and the archive of what was issued. No account system until pilots need one.
6. Record per pilot: use, time saved, what was missing, delivery failures, and Ethan's support time.

**Measures** (revised 24 October 2026). Ten interviews written up by 31 January 2027, and whether any
interviewee commits to pay. Then renewal for the 2027 season, which says more than a first sale. The May–September 2027 evaluation and the October 2027 scores stay as planned.

## 7. Tasks, one pull request each

Each task names what is done when it is done. Follow `docs/DESIGN.md`: screenshots at 320, 375 and
1440 px. Never run the pipeline, or several local builds at once.

- **T1. Plain overflow names (B1).** A short plain name before the company's name, everywhere a name
  appears (the spot page, the organisers' table and CSV, alerts). Rules for the common abbreviations
  (WwTW, STW, WRC, SPS, CSO, SSO), and a test over every name in `overflows.geojson`. Done when no shown
  name starts with a code.
- **T2. Sites view (B2).** `sites.html#spots=a,b,c&name=…` shows each site's five days, its headline
  and the issue time, with a print layout. A "Make a sites link" button on the organisers' page and the
  Saved page. Done when a list of 10 spots prints on one A4 page.
- **T3. Decision record (B3).** From a spot page or the sites view: one A4 page per site and day, with
  the inputs and their ages, the limits in the opening lines, and blank decision lines. Done when the
  wording has Ethan's approval; a solicitor's read comes before any paid use.
- **T4. Event week.** On the organisers' page, for a date more than five days ahead:
  - the three lab-test dates from British Triathlon's schedule;
  - a calendar file (.ics) with them and with the day the forecast first covers the event;
  - inside five days, today's daily view.

  Done when an event date in June 2027 gives correct dates and a file that imports into Apple Calendar
  and Google Calendar.
- **T5. Date alerts (B4).** The push Worker takes a (spot, date) subscription. It notifies when the
  date enters the forecast and when its level changes. Email too, once email is on. Tests in
  `push/test`; the privacy notice says what is stored; Ethan deploys. Done when a test date fires both
  notices in the Worker's tests.
- **T6. Site profile page (B5).** `spot/<id>/profile/` and a click-anywhere version:
  - the overflows upstream, with spills and hours each year 2021–2025 from the annual returns;
  - the EA's samples for designated bathing waters;
  - the share of logged season days at each level, where the forecast log has them;
  - credits, and the caveat first.

  Done when the Wharfe at Ilkley's profile matches the annual returns for its 15 overflows.
- **T7. For clubs and centres page.** A prose page with:
  - the embed;
  - the sign;
  - the sites view;
  - the decision record;
  - Paddle UK's two questions and the Scouts' rule, each with where the site answers it;
  - the levels' meaning for groups of children;
  - the incident line.

  Linked from About. Done when it reads in short plain sentences (most under 20 words) and passes the
  page tests.
- **T8. Applicant profile script, by 15 Oct.** `scripts/site_profile.py LAT LON` writes a profile for
  one point as Markdown and as a printable HTML page. It reads the network, the annual returns and the
  overflow table already on disk, so it needs no new downloads. Done when the Ilkley and Wolvercote
  profiles agree with the site's upstream lists.

## 8. Emails to add to the launch kit

None of these exist yet. Draft each one before it is sent, and check every address on its own site
first.

- SAS bathing-water applicant support: free profiles before 15 Oct.
- OEAP: list SwimSignal beside SewageMap in 7.2i.
- Institute for Outdoor Learning: 3 centre pilots.
- Clean Water Sports Alliance.
- Paddle UK: a link in its water-quality guidance.
- British Triathlon events team: the event week, and pilots for the 2027 season.
- Swim England: the same, for open-water clubs and events.

## 9. Open questions for Ethan

1. **When to charge.** Answered 20 Oct 2026: paid pilots this winter. Revised 24 Oct 2026: interviews first, no spending until someone commits, sponsorship tested once the 2027 audience is measured (section 6a).
2. **Applicants.** Offer profiles even though one can count against an application? The proposal is
   yes, with the caveat stated first.
3. **Terms.** May commercial events and hire centres show the card and the signs during a free pilot?
   Today's terms say no.
4. **Decision record.** Is it acceptable that organisations attach SwimSignal to their written
   go/no-go decisions? A solicitor should read the wording first.
5. **Water companies.** Take any money from one, ever? Join a Breakthrough 7 bid with United Utilities
   this winter?
6. **A company.** A Ltd or a CIC, and when? A CIC fits grants and the independence rule.

## 10. Sources

Facts marked [agent] were opened by research agents on 5 Oct 2026. Their URLs:

- British Triathlon annual report 2022:
  https://btfwebsite.s3.eu-west-2.amazonaws.com/british-triathlon-annual-report-2022.pdf
- British Triathlon Water Quality Guidance:
  https://events.britishtriathlon.org/uploads/content/Water%20Quality%20Guidance.pdf
- UKAS E. coli lab test price: https://www.simplexhealth.co.uk/product/e-coli-ukas-lab-test/
- Henley Swim: https://www.henleystandard.co.uk/news/home/496546/water-fears-force-swim-firm-to-shut.html
- AALA providers: https://aala.hse.gov.uk/aala/provider_results.php
- DofE statistics 2025–26:
  https://www.dofe.org/wp-content/uploads/2026/05/DofE-UK-wide-Annual-Stats-2025-26.pdf
- Scouts water safety:
  https://www.scouts.org.uk/volunteers/running-your-section/programme-guidance/information-for-volunteers/general-activity-guidance-a-z/general-water-activities/water-safety-waterborne-diseases-and-immersion/
- OEAP 7.2i: https://oeapng.info/download/1280/
- Bathing waters, 449: https://www.gov.uk/government/news/87-of-bathing-waters-rated-excellent-or-good-as-new-reforms-come-into-law
- Designation guidance [checked]:
  https://www.gov.uk/government/publications/bathing-waters-apply-to-designate-or-de-designate/designate-a-bathing-water-guidance-on-how-to-apply
- River Truth prices [checked 3 Oct]: https://rivertruth.co.uk/business
- Paddle UK annual report 2024: https://paddleuk.org.uk/shared-files/49904/Annual-Report-2024.pdf
- Paddle UK water quality: https://paddleuk.org.uk/water-quality-dont-get-sick-doing-what-you-love/
- Clean Water Sports Alliance: https://www.rya.org.uk/news/a-year-of-action/
- Severn Trent: https://www.stwater.co.uk/news/news-releases/severn-trent-sets-out-rivers-vision-as-it-launches-uk-s-largest-/
- Shropshire Wild Bathing: https://www.gov.uk/government/news/daily-bathing-water-testing-expands-across-shropshire
