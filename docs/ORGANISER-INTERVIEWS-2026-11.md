# Organiser interviews and the demonstration: brief and measures, November 2026

Pillar 6 of the November programme: finding out whether clubs, activity centres and event organisers would pay
for anything, without building billing, accounts or a paywall. Written 2 November 2026. It follows the order set
on 24 October 2026 (`docs/ORGANISER-PIVOT-2026-10.md`, "Revised 24 October 2026"; `docs/MARKETS-2026-10.md` §6a):
interviews first, no spending until a written commitment, sponsorship only after a measured spring audience.

Marks: **[checked]** I opened the source on 2 Nov 2026. **[repo]** read from this repository or the private
measure folder on 2 Nov 2026. **[inferred]** my reasoning, not a fact.

Nothing in this document has been sent to anyone. It is a draft for Ethan. No interview has been held, no
organisation has been contacted for it, and no organisation pays for SwimSignal or has agreed to.

## 1. The demonstration

`demo.html` (this PR) is one worked example, on the live forecast, of the free tools that already exist:

| Step | What it shows | Tool it comes from |
|---|---|---|
| 1. The session | An invented activity centre's session on Windermere: a main launch point, three backups, who decides | demo.js |
| 2. The session briefing | `scripts/briefing.py`'s limits and "who decides" text word for word, then each venue's level on the day | briefing.py's wording; sites.js `dayWords` |
| 3. Several venues | The sites view for the four venues on the session's day | sites.js `view` |
| 4. What changed | Each venue against the previous update, from `data/since-last.json` | since.js `lastParts` |
| 5. A record kept | The issue id, the decision record prepared for the centre, and what a pilot would keep | printed.js, record.html, brief.js |
| 6. At the water | The printed sign, the live sign and the embed for the main launch point | sign/, embed.html |

The venues are four EA bathing waters on Windermere: Millerground Landing (main), Rayrigg Meadow, Fellfoot and
Lakeside YMCA. The Lake District is the winter plan's focus area (chosen 25 Oct 2026) [repo: `measure/focus.txt`].
I first drew it on the Wharfe and moved it: the Wharfe example leaned on Ilkley, whose upgraded overflows read high
(PR #298), which would have made the demonstration look worse for a known model fault, not for the tools.

The page's commercial wording, at the top in a "Free today" box:
- every tool on the page is free, with no account;
- SwimSignal is looking into whether organisations would pay for a service built on them; no price is set, and no
  organisation pays or has agreed to;
- the public forecasts and everything for swimmers stay free, whatever is decided;
- it is a forecast, not a water test, it misses many spills (link to the accuracy page, which splits by company),
  and the organisation decides.

It is linked from the organisers' page and the clubs page, and listed in the sitemap. It is not in the offline copy.
The test `tests/site_demo.test.cjs` fails if the briefing's limits drift from `briefing.py`, or if the page loses
"No organisation pays for SwimSignal or has agreed to" or gains "customer", "client", "trusted by" or "used by".

Use in an interview: only after the interviewee has described their own routine (section 3), and only if they ask
what SwimSignal could do. Open the page on the day; the levels and the "what changed" lines are live and differ from
day to day. On a quiet day every venue reads low and nothing changed, which is a true picture and worth saying so.

## 2. Who to interview

Ten conversations by 31 January 2027, as the 24 October plan set: six centres, four event organisers. Clubs are
added below as a smaller third group, since clubs stay free and are a channel, not a buyer [repo: ORGANISER-PIVOT §2].

| Group | How many | Who in the organisation | Why them |
|---|---|---|---|
| Commercial activity centres with several inland launch points, running water sessions weekly | 6 | The person who signs off a session on the water (duty instructor, operations or water-sports manager), and whoever holds the budget, if different | A decision made every week is more likely to be worth paying for than one event's [inferred, as in the pivot plan] |
| Open water and triathlon event organisers with 2027 dates on inland water | 4 | The race director or the person who writes the water-quality part of the risk assessment | Fixed dates, a written risk assessment, and British Triathlon's guidance already asks them to know when overflows spill |
| Clubs (open water, paddling, triathlon) | 2–3, optional | The club's safety or welfare lead | To learn what a free user does with the tools; not to sell |

Lake District centres first, to match the focus area; then the Wharfe, the Thames and the Dart, where the site has
the most organiser-relevant spots [inferred]. The launch kit (private artifact; see Claude's memory, "Launch kit
artifact") holds the candidate list and the email drafts. Its rules apply: send from hello@swimsignal.co.uk; a
company may be emailed without consent, but a sole trader, partnership or unincorporated club may not, and every
email names the sender and offers an opt-out [repo: ORGANISER-PIVOT §5 item 10]. Nothing is sent from this PR.

Who should not be interviewed for this: anyone already helping SwimSignal as a data partner (for example the
Waterhead sampler), since a sales question would strain that relationship [inferred]; water companies and councils,
which wait (MARKETS §5.3, §5.5).

## 3. The interview

About 30 minutes. Their routine first, the tools only if they ask. Take notes in their words. Do not name a price
unless they ask for one; if they do, give the hypothesis (£79 a month for a centre, £200 an event) and record the
reaction word for word [repo: ORGANISER-PIVOT §2].

Opening, read out: "I'm Ethan. I run SwimSignal, a free sewage-pollution forecast for river and lake swim spots.
I'm not selling anything today. I'd like to understand how you decide whether a session goes on the water, and what
that costs you. Is it all right if I take notes? I won't quote you or name you without asking."

The questions. Open, about what happened, not about what they would do.

1. Tell me about the last time you had to decide whether a session went ahead because of the water. What happened?
2. Who made that call, when, and what did they look at? Walk me through it in order.
3. Where do you write the water-quality part down: a risk assessment, a log, an email? Can you describe what it says?
4. How long does checking the water take each time, and who does it? Is that time paid?
5. What do you spend on water quality in a season: lab tests, testing kits, subscriptions, staff time, anything else?
   Who holds that budget?
6. When the forecast or the rain changed after you had decided, what did you do? How did you find out?
7. What has gone wrong: a session cancelled late, swimmers ill afterwards, a complaint, a question from an insurer,
   a governing body or a parent? What did it cost?
8. If you had to show someone later what you knew when you decided, how would you do it today?
9. What tools or services have you tried for this, and why did you keep or drop them?
10. If something did this part of the job for you, what would it have to do, and what would make it not worth having?

Only if they ask what SwimSignal does: show `demo.html`, then ask "Which part of this, if any, would you use, and
for what?" Record which step they point at.

After each interview, the same day: a one-page note in `swimsignal-private/interviews/` (personal data stays out of
this public repository), with the date, the organisation type (never its name in anything public), the answers, the
current spend named in question 5, any reaction to the demonstration and to a price, and the next step they agreed to.

## 4. What counts as a written commitment

The 24 October rule: the paid items (insurance, a solicitor, a company, Open-Meteo Professional, CARTO's commercial
key, the ICO fee, card payments) wait until one customer commits in writing [repo: ORGANISER-PIVOT, "Revised 24
October 2026", point 2]. A written commitment, for that rule, is all of these:

- **In writing from the organisation**: an email or a signed letter from someone who can approve the spend,
  named with their role. A message from a staff member without budget authority is interest, not a commitment.
- **A named price**, in pounds, per month, per season or per event.
- **A named scope**: which sites, which days or event dates, what is delivered (for example a briefing the evening
  before each session and copies kept for the season), and the start and end dates.
- **A statement that they buy for their business**, as the pilot agreement asks [repo: ORGANISER-PIVOT §7].
- **Conditional only on things in Ethan's control**: the pilot agreement being signed, the service starting on the
  date named. "We'd pay if..." about something outside the scope (a grant coming through, a board meeting) is not
  yet a commitment; record it and the date to ask again.

Not a commitment: a verbal yes, "sounds great", a request for a proposal, a survey answer, a tip, a sponsorship
conversation, or a free pilot. Record each of these in the note; none of them unlocks spending.

On the first commitment, the order in `docs/ORGANISER-PIVOT-2026-10.md` §5 runs: employer confirmation first (it can
still stop the plan), then the trading form, insurance, the solicitor's read of the agreement, Open-Meteo, CARTO,
hosting, the site's own words, the ICO fee, then the first invoice.

## 5. The Open-Meteo cost to account for

The forecast's rain comes from Open-Meteo's free API. Its terms, opened 2 Nov 2026 [checked
https://open-meteo.com/en/terms]:
- the free API is for non-commercial use only, under 10,000 calls a day, 5,000 an hour, 600 a minute;
- "Websites or apps that have subscriptions or display advertisements" and "Commercial products" are commercial use;
- "Voluntary donations, including contributions through a tip jar, are permitted."

So a paid service to organisations is commercial use and needs a paid plan, from the first paid pilot [inferred from
the terms; Open-Meteo has not been asked about this case]. Which plan:
- The pricing page [checked https://open-meteo.com/en/pricing, 2 Nov 2026] says "Historical, climate, ensemble, and
  satellite radiation APIs require the Professional API Plan or higher". The build calls the ensemble API
  (`config.py`, `OPEN_METEO_ENSEMBLE`) [repo]. So Standard is not enough; Professional is the floor.
- Professional allows 5M calls a month. The build uses about 8,600 calls a day since PR #243, about 260,000 a month
  [repo: memory of PR #243; recount before subscribing], well inside it.
- **Price: €99 a month**, as recorded on 20 Oct 2026 [repo: ORGANISER-PIVOT §3]. The pricing page I opened on
  2 Nov 2026 lists the plans and their limits but showed no price in its text, so I could not re-check the figure.
  Read it at checkout.
- At about £0.87 to the euro, €99 is about £86 a month, about £1,030 a year [inferred; the rate moves].

What it means for a price: one centre at the £79 hypothesis does not cover Open-Meteo alone. Two centres, or one
event a month at £200, cover it, before insurance, the ICO fee, CARTO and the solicitor [repo: ORGANISER-PIVOT §3
puts running costs at about £100–£130 a month]. Ask every interviewee what they spend now (question 5) so the price
can be tested against their own budget, not against this cost.

Two open points for Ethan, to settle in writing with Open-Meteo before the first invoice, not now:
- whether one paid pilot makes the whole public site commercial use, or only the paid deliverable [inferred: the
  terms speak of the website or app as a whole, so assume the whole site];
- whether a sponsor's labelled placement counts as advertising (already listed in the pivot plan, point 3).

## 6. Success measures

Four measures. Each says where it is read, how, and what it cannot tell.

Cloudflare Web Analytics samples page loads adaptively. Every figure from it is an estimate: report the estimate
with its `sampleSize`, request `confidence(level: 0.95)`, quote the bounds only where `isValid` is true, and keep one
query shape from week to week. Never rescale a count (it is already weighted) [repo: Claude's memory, "Cloudflare
Web Analytics sampling", checked 24 Oct 2026]. A "visit" is an arrival from another site or a direct link, not a
person: Web Analytics cannot tell a returning visitor.

| Measure | What counts | Where it is measured | Limits |
|---|---|---|---|
| **Completed planning journeys** | A visit that reaches an end point of planning: a decision record (`record.html`), a sites view (`sites.html`), the organisers' page with a spot picked, or a spot page opened from Plan a swim | Web Analytics, `rumPageloadEventsAdaptiveGroups` grouped by path, weekly, with `sampleSize`. The weekly count already records `plan_visits` and `spot_page_visits` [repo: `swimsignal-private/measure/weekly.csv`]; add `record_loads`, `sites_loads` and `demo_loads` columns in the same query shape | Paths only: the part after `#` (which spot, which day) never reaches the counter, and steps cannot be joined into one journey. Visitors who object, or send GPC or Do Not Track, are not counted. A real journey count would need an event beacon, which is not built and would need a privacy-notice change |
| **Return visits** | Repeat use by the same person or organisation | Push subscriptions (KV `sub:` keys in the `swimsignal-push` Worker, each with an `updated` time) and date alerts (`d` in the key's metadata); email alerts (`mail:` keys). The weekly count records `push_subs` | Web Analytics cannot see returns. A subscription is repeat intent, not repeat use. Counting subscriptions still live 4 weeks after they were made needs a read of `updated`, by hand |
| **Alert usefulness** | Whether an alert led to a decision, and whether the level it announced was borne out | (a) In interviews and comprehension sessions: "Did an alert change what you did? Tell me about it." (b) Offline, against the live spill feeds: for each alert sent, whether an overflow upstream spilled on the alerted day, as the accuracy page scores forecasts | Nothing in the product measures usefulness today: no feedback button, no record of who acted. (b) scores the level, not the alert's effect. A one-tap "Was this useful?" would need a Worker endpoint and a privacy-notice line: Ethan's decision, not built here |
| **Customer commitments** | Written commitments as defined in section 4 | The interview notes in `swimsignal-private/interviews/`, one row per interview in a sheet: date, organisation type, current spend, reaction to the demonstration, reaction to a price, commitment yes or no, next step and its date | Ten conversations is a small number: it can show whether anyone will pay, not how many would [inferred] |

Read-outs, not targets: the winter plan's gates (24 Oct 2026) stay diagnostic prompts, as v2 of that plan made them.
The one hard gate in this pillar is section 4: no spending without a written commitment.

## 7. What is Ethan's

- Approving the demonstration's wording, especially the "Free today" box.
- Choosing whom to contact, and sending anything. Nothing here is sent.
- The employer confirmation (pivot plan phase 0), before any interview that could lead to a sale.
- Asking Open-Meteo the two questions in section 5, when a commitment is close.
- Whether to add the three Web Analytics columns to the weekly count (a change to the private scheduled task).
- Whether an alert-feedback button is worth building.
