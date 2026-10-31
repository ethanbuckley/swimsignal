# Partner sampling programme: privacy, liability and wording

Written 31 October 2026. Status: a plan with code, nothing live. The Worker route is not deployed, no partner has been
contacted through it, and nothing here has been reviewed by a solicitor. Owner: Ethan. Register entry: WET in
[the recovery register](RESEARCH-RECOVERY-2026-10.md).

The parts:

| Part | Where | State on 31 Oct 2026 |
|---|---|---|
| Data contract, template, checker | [PARTNER-SAMPLES-CONTRACT-v1.md](PARTNER-SAMPLES-CONTRACT-v1.md), `scripts/partner_samples.py` | [#571](https://github.com/ethanbuckley/swimsignal/pull/571) open |
| Moderated intake | `reviews/` Worker, `POST /partners/samples`, `/moderate` | [#572](https://github.com/ethanbuckley/swimsignal/pull/572) open; not deployed, switch off |
| Evidence timeline on the spot page | `src/dipcast/site/timeline.js` | [#573](https://github.com/ethanbuckley/swimsignal/pull/573) open |
| This document and the partner page | `docs/PARTNER-PROGRAMME-2026-11.md`, `partners.html` | this PR |

## Why the programme exists

Forecasts can only be judged against samples nobody chose after seeing them. The Environment Agency samples the 38
inland bathing waters in SwimSignal's sample export from May to September, roughly every week or two. That is too few places and too few days to
tell two forecast models apart with confidence. A group that samples weekly at its own point, under a test-use
agreement made before it samples, adds exactly the data that is missing. Ambleside Action for a Future's Waterhead
series is the first: 59 samples, published at `waterhead.html`, but seen before any test was designed, so
exploratory only (WET contract).

## What personal data the intake holds

The partner files themselves should hold no personal data: the contract asks for the sampler as a role or a group,
never a private person's name. The intake adds:

| Item | Why | Personal data? |
|---|---|---|
| Organisation name | To credit and to know whose file it is | Usually not; a sole trader's name is |
| Contact name (optional) | To address a reply | Yes |
| Email address | The only way to reply about the file | Yes |
| Message (optional) | What the sender wants to say | May be |
| The file, its SHA-256, row count and first and last sampling day | The data itself, and to match what is checked with what was sent | Not if the contract is followed; a `sampler` or `notes` cell could name someone |
| Arrival and acceptance times | Retention and moderation | No |
| A hash of the withdrawal key | So the sender can withdraw the file | No |
| Rate-limit counts | Three files a day per connection | No: an HMAC of the address, kept two days, as for reviews |

Not held: the IP address, the browser, any account or password. There are no partner accounts.

### Basis

Inferred, not legal advice. For the contact details: legitimate interests (replying to someone who sent us data and
asked us to look at it), or steps at their request before an agreement. For any personal data inside a file:
the partner's own basis for collecting it, which is why the contract asks them to leave names out. Publication and
test use of results rest on the written permissions in the file, which are agreements with an organisation, not
personal-data consent.

## Retention

| What | How long | How it goes |
|---|---|---|
| A file and its contact details in the Worker | 90 days from arrival, accepted or not (`PARTNER_KEEP_DAYS`) | The daily cron deletes the row; the operator can delete sooner; the sender can withdraw it with their key at any time |
| An accepted file | Kept in `swimsignal-private/partners/<partner_id>/`, outside the repository, while the partnership lasts and for one year after it ends, so a published score can be reproduced | Deleted by hand at that point; the register entry says when |
| The written agreement (email) | As long as any result it covers is published or used in a published score | Kept in the mailbox, referred to by `consent_ref`, never copied into the repository |
| Published results | Until the partner withdraws publication | Removed from the public files at the next build after the private file changes |
| Email correspondence | As for any email to hello@ | Ethan's mailbox |

Withdrawal: a partner may withdraw publication or test use at any time by email. Withdrawal takes results off the
site from the next build and out of any future test. It cannot undo a score already published on them; the score's
page then says that some of its data has been withdrawn.

## Moderation

Every file waits for Ethan. Nothing is published by the Worker, ever. The steps:

1. Download the file on `/moderate`.
2. Run `uv run python scripts/partner_samples.py check FILE.csv`. Errors go back to the partner, with the checker's
   lines. Do not fix a partner's values by hand: a changed value is no longer theirs.
3. Read the warnings with the partner: an unconfirmed site, no sampling time, a 0 whose meaning is not known. Record
   their answers in the file's `notes` (labelled "partner:") or fix the column if they confirm a value.
4. Confirm both permissions by email, row by row if they differ. A `holdout` row needs an agreement dated before its
   sampling day; anything else is `exploratory`.
5. Move the file to the private folder and press Accept.
6. Only then, and by pull request: a public copy of the rows with `publish_consent` `yes`, and a page or spot link.

Things to turn down: a file of someone else's results without their permission; results that name or identify a
person (a sampler, a landowner, a swimmer who fell ill); results that accuse a named person or business of causing
pollution. Those are for the Environment Agency or Natural Resources Wales.

## Wording rules

These apply to every page that shows partner, agency, satellite or community evidence. The evidence timeline keeps
them, and its tests check the wording.

1. Each item is labelled **Measurement** (a lab or instrument measured it), **Report** (what someone saw or
   published) or **Forecast** (worked out ahead), in words. No colour, badge or pill carries the meaning.
2. Each item says whose it is, its date, and its review status: who checked it and how far.
3. A community report is never shown as a verified pollution warning. Suspected pollution or algae says "Suspected"
   and "what one swimmer saw, not a water test", even after the operator has matched it to an official source; the
   line then points to that source's own notice, which is the warning.
4. Missing satellite imagery is not a clear result. Days without a usable image are not listed, and the page says that
   a missing image says nothing about algae.
5. A satellite index is not a toxin measurement, a chlorophyll concentration or a swimming clearance.
6. A sample is the water at that place at that moment. Not today's water, not the rest of the water body, not a
   forecast, not a rating and not "safe".
7. A below-limit count is "below 10", never 0 or "none". A recorded 0 whose meaning is not confirmed says it may be
   below the detection limit.
8. Nothing in the timeline or a partner's results changes the forecast's level.
9. Official advice comes first and is never restated in SwimSignal's words as weaker than it is.

## Liability

Inferred, not legal advice; a question for the solicitor review already planned (paid pilots decision).

- SwimSignal publishes a partner's results as theirs, credited, with the laboratory and method they give, and says it
  did not take or check the samples. The partner is responsible for their accuracy; SwimSignal for showing them
  faithfully and with their limits.
- The defamation risk is in words, not counts: no page names a cause or a culprit for a result. Files that do are
  turned down (above).
- The terms page should gain a short "Partner results" section once the first public copy beyond Waterhead is
  published. Not written yet: it needs the solicitor's view.

## Open question for Ethan: the ICO data protection fee

Ethan's notes say the fee may already be owed. What is established:

- Under the Data Protection (Charges and Information) Regulations 2018, a controller that processes personal data
  must pay the ICO an annual fee unless an exemption applies.
- Since February 2025 tier 1 (micro organisations) is £52 a year, tier 2 £78 and tier 3 £3,763 (secondary sources:
  [Lewis Silkin](https://www.lewissilkin.com/insights/2025/02/06/fee-payable-to-the-ico-to-increase-in-february-102jzb9),
  [Acuity Law](https://acuitylaw.com/rise-in-ico-fees-data-protection-fees-february/),
  [the government response](https://assets.publishing.service.gov.uk/media/6788f8d293d4eae3088bd2ce/data_protection_fee_regime_proposed_changes_government_response.pdf)).
  The ICO's own fee page returned an error when checked on 31 Oct 2026; read it before paying.
- The exemptions cover processing only for staff administration, advertising and marketing of one's own business,
  accounts and records, and some not-for-profit purposes, and purely personal or household activity.

What is inferred: SwimSignal already processes personal data for purposes outside those exemptions (reviews with
names and photos, visit notes, the push-alert subscriptions, and from this programme partner contact details). It is
not a household activity, since it is a public service. So the fee is most likely owed already, independent of this
programme; the partner intake does not change the answer, only adds to the reasons.

What would settle it: the ICO's fee self-assessment at ico.org.uk ("Does my organisation need to pay a fee?"), which
takes a few minutes. **Decision for Ethan:** take the self-assessment, and if it says pay, register at tier 1 before
the partner intake is switched on. Nothing in this PR registers, pays or contacts the ICO.

## Before the intake is switched on

1. ICO question above, decided.
2. Worker migration and deploy (`reviews/README.md`, "Deploying partner files"), switch still off.
3. The partner page gains its upload form, posting to the Worker (a later, small change: today it asks for files by
   email).
4. The privacy notice gains a "Partner files" section, from the table above, in the build's usual way.
5. Switch `PARTNER_SAMPLES` on.

Until then, partners send files to hello@swimsignal.co.uk, and steps 2 to 6 of Moderation apply to an emailed file
just the same.

## The next useful deliverables

- **Waterhead 2027 holdout agreement.** Ask Tim Boden (Ethan, by email; not sent) to agree in writing, before the
  first 2027 sample, that every 2027 Waterhead sample is held-out test data for both his model and SwimSignal's, with
  the site point, laboratory, method and detection limit stated. That turns the next season into a fair test.
  Milestone: agreement before 1 April 2027.
- **His model files** (expected from 9 Nov): reproduce privately, freeze, log in shadow for 2027 (register, WET).
- **A second partner**, from the swimmer groups already contacted, once the page is live.
