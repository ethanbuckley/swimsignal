# Expansion and independent review, 3 October 2026

The first public step is `coverage.html`: official bathing-water services for English coasts,
Wales and Scotland, plus UKCEH's algae map. These links do not imply that SwimSignal issues
regional or coastal forecasts. The source pages were checked on 3 October 2026.

## Work remaining before importing observations

| Layer | Source and next implementation | Acceptance condition |
| --- | --- | --- |
| English coasts and estuaries | [EA bathing-water profiles](https://environment.data.gov.uk/bwq/profiles/) and its documented bathing-water API. Start with official observations and pollution warnings, separately from the inland model. | Source/site identifiers, sampling time, issue/expiry time and missing-warning state survive ingestion. Missing or expired advice never means clear. Test against dated source fixtures before publishing. |
| Wales | [NRW monitoring and approved widget](https://naturalresources.wales/days-out/bathing-water-quality/?lang=en), which links to [Welsh profiles](https://environment.data.gov.uk/wales/bathing-waters/profiles/). | Verify the exact dataset's reuse licence and API contract; preserve NRW provenance. Welsh observations first. No Welsh forecast until regional spill coverage and independent validation are available. |
| Scotland | [SEPA bathing waters](https://bathingwaters.sepa.org.uk/) and [dataset licence catalogue](https://www.sepa.org.uk/environment/environmental-data). [Hydrometric API](https://timeseriesdoc.sepa.org.uk/) is OGL without registration. Bathing-water datasets have separate terms; the hydrometric licence cannot be assumed for them. | Verify the selected bathing-water licence and authoritative access method. Add gauge age/river matching tests, with no English calibration carried over as demonstrated Scottish skill. |
| Wider algae reports | [Bloomin' Algae project and verification categories](https://www.ceh.ac.uk/our-science/projects/bloomin-algae), [map](https://bloominalgae.ceh.ac.uk/). | Obtain explicit permission/licence for the report export. Ingest confirmed, unverified, unable-to-verify and no-bloom records as distinct states; preserve observation date and water-body match. Never convert absent/old reports or a nearby unrelated pond into an all-clear or a confirmed local bloom. |

For every adapter: keep a bounded timeout, source URL, fetched-at and observed-at timestamps,
schema validation, explicit unavailable/stale states and attribution. A failed adapter must not
stop the inland site publishing. Do not copy citizen photos or personal details into the site.

## Scientific review package

Review entry points: [method](https://swimsignal.co.uk/methods.html),
[live accuracy](https://swimsignal.co.uk/verification.html),
[public data and scored rows](https://swimsignal.co.uk/data.html),
[`model/transport.py`](../src/dipcast/model/transport.py), and
[`model/forecast.py`](../src/dipcast/model/forecast.py). Record the exact code revision and
downloaded score/data hashes when a reviewer starts; the live scores keep growing.

Ask an independent hydrologist or bathing-water scientist to assess:

1. Whether the exposure index's travel speed, dilution and decay assumptions support the
   interpretation in the UI; assess correlated overflow events and unmonitored discharges.
2. Whether temporal/site holdouts, calibration fitting and forecast logging avoid leakage.
   Check rain issue times, late/out-of-order feed observations and genuinely advance forecasts.
3. Whether E. coli estimates are supported by the sample size and river/site coverage. Assess
   season and lake abstention, threshold interpretation and uncertainty in each risk band.
4. Whether comparisons with climatology and the EA use matched sites/dates and report missing
   observations, effective independent sample size and uncertainty.
5. Whether “no monitored overflows upstream” and all other abstentions communicate the remaining
   hazards adequately. Review coastal and regional boundaries before any expansion.

The reviewer should declare independence and conflicts, identify material changes, and provide
a dated written assessment. Publish that assessment and a response/correction log only with
their consent. This package is prepared; no external review has taken place or been endorsed.

## Prospective May–September 2027 evaluation

Before 1 May, freeze a versioned model, band thresholds, eligible-site list, matching rules and
analysis script. Register the protocol publicly in the repository with the revision/hash. Log
every forecast before observations arrive and retain failures, missing feeds and abstentions.
Do not tune the frozen evaluation model on the evaluation season. A replacement model runs
as a separately labelled candidate and starts its own prospective evaluation.

Use the same published sample threshold and exact site/date matching for all compared models.
Report Brier score, reliability by band, discrimination and skill against a training-only
season/site climatology; for an official binary warning use the matched event confusion table
and the same sample denominator. Separate same-day and advance forecasts and each lead.
Publish coverage/abstention rates, river/lake/region strata and sample counts. Estimate uncertainty
with site/time-block resampling chosen before evaluation; treat correlated samples as clustered.
Report the full season without stopping early when scores look favourable. Region/coastal
release decisions require positive held-out skill with uncertainty and external review.

## Access review

All 16 OSM spots now carry an explicit desk-check note. Five Peak District river locations
carry the [authority's restrictions guidance](https://www.peakdistrict.gov.uk/visiting/planning-your-visit/swimming).
Ullswater and Windermere have [lake-wide swimming permission](https://lakedistrict.gov.uk/explore/things-to-do/on-the-water/lakes-activities-guide/),
with bank entry permission still unconfirmed. Longbridges links to
[Oxford's current safety-sign announcement](https://www.oxford.gov.uk/news/article/1860/new-signage-to-be-installed-to-improve-water-safety-in-oxford).
Drogo Weir links to the National Trust's walking-route description and explicitly flags the weir.
The other seven, including Rivelin outside the Peak District set, retain unconfirmed status.
No remote check has established current signs, legal bank access or a usable entry/exit at any
of these pins. A public footpath or an OSM swim tag is insufficient evidence.

An on-site check needs a dated sign record, landowner/site-management permission evidence,
public route to the exact bank, entry/exit condition and closures. Never label a pollution
forecast as an access or physical-safety assessment.

## Location-provider keys

The request workflow already supports `W3W_API_KEY` and `OS_API_KEY` repository secrets; neither
is currently installed. Coordinates and OS grid references work without either. Provider
accounts/keys must come from the owner; no paid account or subscription was created. Test each
key's quota/error and ambiguous-name response before enabling it. A settlement centre is not
an exact swimming entry point and should not be silently substituted for one.

## Draft UKCEH enquiry — not sent

SwimSignal is a free, non-commercial inland pollution-risk website. May we reuse the Bloomin'
Algae report export to display dated, water-body-matched reports with UKCEH attribution and
links back to the original map? Please confirm the licence, permitted fields, update limits,
verification status definitions, correction/deletion handling and whether reporter information
or photos must be excluded. We would keep unverified records distinct and would never interpret
missing reports as absence of algae. We can provide a preview before publishing.

Destination if authorised: the project's published bloomin-algae@ceh.ac.uk contact. No enquiry
has been sent. An independent reviewer also needs to be identified and invited by the owner.
