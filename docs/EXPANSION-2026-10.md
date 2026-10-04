# Expansion and independent review, 3 October 2026

The first public step is `coverage.html`: a searchable directory of 426 designated English coastal and estuary bathing waters, plus official bathing-water services for
Wales and Scotland, plus UKCEH's algae map. The English directory publishes dated EA advice and historical ratings under OGL, with explicit missing/expired/unavailable states; it does not issue a coastal model forecast. These links do not imply that SwimSignal issues
regional or coastal forecasts. The source pages were checked on 3 October 2026.

## Work remaining before importing observations

| Layer | Source and next implementation | Acceptance condition |
| --- | --- | --- |
| English coasts and estuaries | [EA bathing-water profiles](https://environment.data.gov.uk/bwq/profiles/) and its documented bathing-water API. The official directory, historical ratings and dated pollution advice are implemented in `coastal.py` and published as `data/coastal.json`, separately from the inland model. Each site's latest statutory lab sample (E. coli and intestinal enterococci from the same visit, with its sampling time) comes from the EA Water Quality Archive via `data/raw/coastal_wqa_points.json` (`scripts/map_coastal_wqa.py`, run off CI). Current advice is unavailable in production builds: the bathing-water service has refused GitHub's runners since 28 Sep 2026, and the build stops at the first refusal rather than routing round it. Its API sends no `access-control-allow-origin`, so a reader's browser cannot read it either (checked 4 Oct 2026). Instead, each site's "Today's EA advice" on the coverage page loads the EA's own [embeddable widget](https://environment.data.gov.uk/bwq/widget) for that site, from the reader's browser when opened, sandboxed and never stored. It shows open pollution incidents, which the build never read: on 4 Oct 2026 it advised against bathing at Plymouth Hoe East and West (sewage, since 1 Oct) and Blyth South Beach (oil or fuel, since 11 Aug). | Source/site identifiers, sampling time, issue/expiry time and missing-warning state survive ingestion. Missing or expired advice never means clear. Test against dated source fixtures before publishing. |
| Wales | [NRW monitoring and approved widget](https://naturalresources.wales/days-out/bathing-water-quality/?lang=en), which links to [Welsh profiles](https://environment.data.gov.uk/wales/bathing-waters/profiles/). Implemented as observations only (`wales.py`, `data/wales.json`): the [Welsh API](https://environment.data.gov.uk/wales/bathing-waters/) states it is under the Open Government Licence, with NRW's attribution wording. 114 sites (107 coast, 3 estuary, 2 lakes, 2 rivers), ratings and latest samples. Its gateway refused GitHub's runners on 3 Oct 2026, so the build shows a dated snapshot (`scripts/fetch_wales.py`, run off CI) and the coverage page asks NRW for current samples and forecasts in the reader's browser, which the API permits (`access-control-allow-origin: *`); forecasts are never stored. No published rate limit was found. | Ask NRW to confirm acceptable use and any rate limit. Welsh lab-result history, regional spill coverage (Dŵr Cymru has no live feed) and independent validation come before any Welsh forecast. |
| Scotland | [SEPA bathing waters](https://bathingwaters.sepa.org.uk/) and [dataset licence catalogue](https://www.sepa.org.uk/environment/environmental-data). [Hydrometric API](https://timeseriesdoc.sepa.org.uk/) is OGL without registration. Implemented: `scotland.py` lists SEPA's 90 waters with latest ratings and links, from the "Bathing Water Points" REST layer, which the catalogue lists under the Open Government Licence (linked to v2.0) and which answers GitHub's runners. Samples ("Locations": "SEPA website conditions of use") and the signs' daily predictions (no stated licence) are not read. | Ask SEPA which licence covers sample results and sign predictions, and how they want them reused. Add gauge age/river matching tests, with no English calibration carried over as demonstrated Scottish skill. |
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
has been sent. An independent-review invitation has been prepared for Professor Richard Quilliam at the University of Stirling (https://www.stir.ac.uk/people/257111). Availability and conflicts have not been established; the invitation is awaiting owner authorisation.
