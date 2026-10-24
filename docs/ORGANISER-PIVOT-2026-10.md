# Charging organisers and events: the plan, October 2026

How SwimSignal starts charging activity centres and event organisers this winter, while swimmers stay
free. Written on 20 October 2026, after Ethan's decision to run paid pilots this winter
(`docs/MARKETS-2026-10.md` §6a) and a legal pass done the same day by three research agents.

Marks: **[checked]** I opened the source on 20 Oct 2026. **[agent]** a research agent opened it on
20 Oct 2026 and I did not re-check it. **[inferred]** my reasoning, not a fact.

The legal pass itself, with the draft pilot agreement and the questions for a solicitor and a broker, is
kept private: it is a private page (link in Claude's memory) and a copy in `swimsignal-private/legal-2026-10-20/`. It is
research by an AI assistant, not legal advice.

## Revised 24 October 2026: interviews first

Ethan changed the order on 24 Oct 2026. Nobody has yet said they would pay for the briefing in §2, and an
organiser can get most of it from the free site. The sections below are kept as the reference for what a
pilot would be and what it would need, but the order is now this:

1. **Interviews first, and exploratory.** Centres and organisers are asked about their water-quality
   routine as it is now: what they check before a session, who checks it, how long it takes, what they
   write down, what it costs them and what has gone wrong. The briefing is not pitched. It comes up only if
   they ask what SwimSignal could do for them, and their reaction is noted with everything else. Centres
   that run water sessions every week come first: a decision made every week is more likely to be worth
   paying for than one event's [inferred].
2. **No pre-invoice spending until someone commits.** The paid items in §3 and §5 wait until one customer
   says in writing that they will pay a named price for a named scope: insurance, the solicitor, a
   company, Open-Meteo Professional, CARTO's commercial key, the ICO fee and card payments. Two items go
   ahead now because they cost nothing: the employer check (§5 item 1), which can still stop the plan, and
   the outreach rules (§5 item 10), which the interview emails must follow.
3. **Sponsorship is tested once there is a measured spring audience.** From the season's opening on
   15 May 2027, swimmer use is measured by region: visits a week, spot pages viewed, and push
   subscriptions. Web Analytics cannot tell a returning visitor, so push subscriptions are the repeat-use
   signal [inferred]. A sponsor is approached only with those figures, for one clearly labelled placement
   that has no say in any forecast. Open-Meteo's free API excludes sites with advertising (README,
   "Before taking money or running ads"), so a sponsor brings the paid plan into the numbers; ask
   Open-Meteo first whether a sponsor's placement counts.
4. **Swimmers stay free, and tips stay on.** Open-Meteo said on 15 Oct 2026 that a tip jar is fine.

This replaces the 20 October order, which set the paid service up by 20 Nov 2026 and aimed at three
paying pilots by 30 Apr 2027.

**Why.** From 1 to 24 Oct 2026 the site had about 420 visits and 900 page loads (Cloudflare Web Analytics,
sampled 1 in 10, checked 24 Oct). The busiest days match Ethan's own checks, so many are likely his
[inferred]. About 20 visits came from Facebook and 20 from Google. Neither a buyer nor an audience exists
yet, and looking for each costs nothing. The money in §3 is better spent after one of them is found.

## 1. What changes, in one paragraph

SwimSignal sells one thing to organisations: the same forecast as the public page, organised for the
customer's own water-quality decision and delivered on a schedule, with a copy of everything issued.
It never makes the decision. The customer stays the duty holder: their risk assessment, their lab
tests, their checks at the water. Everything below follows from keeping that line clear, because the
law, the insurers' wordings and the governing bodies' guidance all turn on it [agent: Caparo, Khan v
Meadows [2021] UKSC 21, Watson v British Boxing Board of Control; Hiscox wordings; British Triathlon
risk assessment guide].

## 2. The offer

**Who pays.** Commercial activity centres with several inland launch points, and open-water and
triathlon event organisers. Clubs stay free, as a channel. Councils and water companies wait.

**Where it fits their duty.** Swim England's 2025 club guidance has a "Water quality" row in its daily
risk assessment template and says live spill data "may be an important factor" [agent]. British
Triathlon's 2025 water-quality guidance says lab results take 48 hours, testing a river just before a
swim "is likely to have limited value", and knowing when upstream overflows discharge is crucial
[agent; quoted on the organisers' page already]. SwimSignal fills that gap: the overflow and rain
picture between lab results. It is evidence for that row, not a replacement for testing, algae checks
or briefing swimmers.

**What a pilot includes.**
- Their sites set up as a named list (the sites view).
- A briefing on the days they choose, from the sites view and the decision record, prepared by hand at
  first.
- Date alerts for their sessions or event, once the push Worker's date alerts are deployed.
- A copy of every briefing as issued, with its issue time, kept for the agreed period.
- A fixed end date and a short written review.

**What it never includes.** Water sampling, a safety or water-quality assessment, a risk assessment, a
guarantee, or the words safe, clean, certified or verified. Algae, leptospirosis, farm and road runoff,
unmonitored outfalls and physical hazards are named as out of scope.

**Prices to quote (hypotheses).** £79 a month for a centre, £200 for an event. These sit inside the
ranges the 20 Oct review proposed (£49–£99, £150–£300) and are untested. River Truth sells live
dashboards at £15–£49 a month to clubs and councils [checked 3 Oct 2026]. Record every reaction to the
price.

## 3. What it costs before the first pilot

| Item | Cost | Source |
|---|---|---|
| Open-Meteo Professional plan | €99 a month | [checked] pricing FAQ: ensemble and historical APIs "require the Professional API Plan or higher"; the build calls the ensemble API (`config.py`, `OPEN_METEO_ENSEMBLE`). Standard (€29) is not enough |
| CARTO map tiles | Free to 1M tiles a month for commercial use; then US$500 a month for 10M | [checked] terms of 29 Sep 2026: a service "operated by or on behalf of a business" is commercial, so the free public map counts once Ethan trades. Monthly tile count unknown |
| Insurance: professional indemnity and public liability | Published floors from £60 a year; likely referred and higher | [agent] Hiscox, Simply Business. [inferred] a service feeding swim decisions for children will be underwritten, not bought off the shelf |
| ICO data protection fee | £52 a year | [agent] SI 2025/63 |
| Company, if chosen | £100 (Ltd) or £115 (CIC) online, then £50 a year | [agent] Companies House fees, updated 25 Sep 2026 |
| Solicitor | Unknown | Ask for a fixed fee to review the pilot agreement and the site terms |
| Card payments | 1.5% + 20p per UK card (Stripe) | 29 Sep 2026 notes; take payment by invoice or a hosted Stripe page, never a card form on a free Cloudflare property [agent: Cloudflare terms s.2.2.1(h)] |
| Hosting | Cloudflare Pages free plan | [agent] 20,000 files and 500 builds a month on the free plan; the move is its own session |

Running cost after setup is about £100–£130 a month before the solicitor and the company [inferred:
€99 at about £0.87, insurance and the ICO fee spread monthly]. Two centres at £79, or one event a
month at £200, cover it.

## 4. Phases

As revised on 24 Oct 2026. The dates are proposals.

| Phase | When | Who | What | Gate |
|---|---|---|---|---|
| 0. Go or stop | Now | Ethan | Read the employment contract: IP assignment, outside work, conflicts, confidentiality, equipment. Ask the employer to confirm in writing that SwimSignal is outside the job and they claim no rights in it | Written confirmation. A no stops the plan |
| 1. Interviews | Nov 2026 – Jan 2027 | Ethan, from the launch kit | Ten exploratory conversations: six centres, four organisers. About their routine now, not about the briefing | Ten notes written up by 31 Jan 2027 |
| 2. Set up | Only after a written commitment | Ethan, with Claude's drafts | The §5 items, for the scope the customer named | Every item in §5 done before the first invoice |
| 3. Pilots | After set-up | Ethan runs, Claude builds what repeats | Pilots under the signed agreement, every issue logged | Each pilot logged; renewal for the season |
| 4. Audience | 15 May – 30 Jun 2027 | Both | Swimmer use measured by region: visits a week, spot pages viewed, push subscriptions | Six weeks of figures |
| 5. Sponsorship test | From Jul 2027, if the figures support it | Ethan | One sponsor approached for one labelled placement, after asking Open-Meteo whether it counts as advertising | A sponsor pays, or the test ends |
| 6. Season | May – Sep 2027 | Both | The prospective evaluation as planned | October 2027 scores |

## 5. Before the first invoice

Each item is from the legal pass. None is legal or tax advice. Since 24 Oct 2026, items 2 to 9 wait until a
customer commits in writing. Items 1 and 10 go ahead now.

1. **Employer confirmation** (phase 0).
2. **Trading form.** A sole trader trading as "SwimSignal" must put their name and a service address
   on invoices and give them in writing on request [agent: Companies Act 2006 ss.1200–1206]. A company
   shows its number and registered office on the site and its documents [agent: SI 2015/17 regs
   24–25]. Register for Self Assessment by 5 Oct 2027 for trading started in 2026–27; VAT is not
   due below £90,000 [agent: gov.uk].
3. **Insurance** with professional indemnity that covers third-party injury from negligent
   information. Check three exclusions in particular: computer or digital-technology errors,
   infrastructure (data feed) failure, and listed communicable diseases [agent: Hiscox PI summaries].
4. **Pilot agreement read by a solicitor.** The draft is in the legal pass.
5. **Open-Meteo Professional**, with the build calling `customer-api.open-meteo.com` and the key in a
   secret.
6. **CARTO** key reclassified as commercial, and the monthly tile count read from its dashboard.
7. **Hosting** off GitHub Pages for anything organisations pay for. The whole site is the simplest
   cut [inferred].
8. **The site's own words.** The terms page and every footer say "free, non-commercial" and "not a
   company"; the reuse and embed terms allow non-commercial use only. Rewrite after items 2 and 4,
   add the trading disclosures [agent: E-Commerce Regulations 2002 reg 6; Provision of Services
   Regulations 2009 reg 8], and publish the organisation terms.
9. **ICO fee and privacy notice** covering customer contacts and briefing recipients.
10. **Outreach email rules.** Companies and LLPs may be emailed without consent; sole traders,
    partnerships and unincorporated clubs may not. Every email names the sender and offers an
    opt-out [agent: PECR regs 22–23; ICO B2B guidance].

## 6. What Claude builds, one PR each

Only what the pilots need before they start. Anything else waits for a pilot to ask for it twice. Since
24 Oct 2026: OP1 to OP4 are merged (#273, #275). OP6 goes ahead, because the interview emails quote
figures. OP5 and the switch-over in OP7 wait for a written commitment.

- **OP1. Paid Open-Meteo endpoint.** The build reads `DIPCAST_OPEN_METEO_KEY`; when set, every call goes
  to the customer endpoint with the key; unset, nothing changes. Done when a dry run shows the URLs
  switch and the key never reaches a log or a page.
- **OP2. Credits on everything printed.** The decision record, the sites view and their print
  layouts carry the full credits: Open-Meteo (CC BY 4.0), the Met Office (CC BY-SA 4.0), each water
  company (CC BY 4.0), the EA statements, OS, and "© OpenStreetMap contributors" with
  openstreetmap.org/copyright written out, each with a note that SwimSignal changed the data [agent:
  each licence page]. Done when a printed record carries every credit for the sources it used.
- **OP3. An issue id on every record.** The decision record and the sites view show the build commit and
  the forecast issue time as one id, so any copy can be matched to the forecast log later. Done when two
  prints of the same build carry the same id and a later build a new one.
- **OP4. Decision-record wording.** The record says: prepared for the named organisation; one input to
  their own risk assessment beside lab tests, checks at the water and the EA's forecasts; the hazards it
  does not cover, by name; no data never means low. Done when Ethan approves it; then the solicitor.
- **OP5. Organisation terms and new site wording.** After §5 items 2 and 4. A plain-English page for
  organisations, the public terms changed from "non-commercial" to "free for swimmers", the trading
  disclosures in the footer. Done when the solicitor's changes are in.
- **OP6. Claims beside their evidence.** Wherever a page or an email gives an accuracy figure, the
  catch rate by company sits beside it [agent: CAP Code 3.7 and 3.9]. The verification page does this
  already; the organisers' page, the record and the launch-kit emails are checked. Done when no
  headline figure appears without the company split.
- **OP7. Hosting move.** Running as its own session (Cloudflare Pages).

## 7. Running a pilot

- A signed agreement before the first briefing, with the customer's statement that they buy for their
  business.
- Briefings by hand from the sites view and the record, saved as PDF with the issue id, kept for the
  agreed period.
- A log per pilot: each briefing, whether it was used in a decision, time saved, what was missing,
  delivery failures, and Ethan's support time.
- A written review at the end, and the price for the 2027 season named.

## 8. Risks

- **Looking like the decision maker.** A body that takes control of safety arrangements can owe the
  participants a duty [agent: Watson]. Every output and email keeps the customer as the decision maker.
- **Insurance gaps.** Standard wordings exclude advice from public liability and may exclude
  technology errors, data-feed failures and communicable disease from professional indemnity [agent].
  Buy through a broker who has read the agreement.
- **The forecast's record outside United Utilities.** About 2% of spills warned so far: 23
  of 1,402 forecasts made for a day with a spill, counted at each lead time, not spill days
  (verification page, 20 Oct 2026; PR #269). Say so in the agreement and before any price is named.
- **Met Office share-alike.** If a briefing counts as Adapted Material of the Met Office's rainfall,
  it goes out under CC BY-SA 4.0 and the agreement cannot forbid passing it on [agent: CC BY-SA s.3(b)].
  The draft lets customers share briefings whole; Open-Meteo or the Met Office can settle it in writing.
- **CARTO volume.** Over 1M tiles a month costs US$500 a month. Read the count before the first
  invoice; self-hosted tiles are the fallback [inferred].
