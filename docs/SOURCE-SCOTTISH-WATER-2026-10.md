# Scottish Water overflow data: licence and terms, October 2026

Written 16 October 2026. It checks the licence and terms of the two sources SEPA pointed to on
13 October 2026, when it replied that it would "assume" Scottish Water's overflow data is under
the Open Government Licence. It is a source note, not code: nothing here changes the site, and no
one was emailed.

It updates sections 2.1 and 2.2 of `docs/SCOTLAND-PLAN-2026-10.md` (written 4 October). Where the
two disagree, this note is newer.

Two marks keep what is known apart from what is not. **Checked** means I read the source or made
the request on 16 October 2026, between 00:20 and 00:40 UTC; section 6 gives each URL. *Inferred*
means a deduction that no source settles. SEPA's reply itself was relayed to me; I did not read it.

## 1. Answers

| Question | Annual event files ("Published Overflow Data") | Near-real-time API ("Overflow Map API") |
|---|---|---|
| Licence named? | **Yes.** Open Government Licence v3.0, on both data.gov.uk records published by Scottish Water (checked) | **No.** "an open license for reuse" (checked). A Scottish Water ArcGIS record of the same feed adds "free to use, share, and adapt the data, subject to appropriate attribution" (checked). Neither names a licence |
| 1. Free, non-commercial site with a tip link may reuse it? | **Yes.** OGL v3 allows use "commercially and non-commercially" (checked). A tip link does not matter under it | **Yes, inferred.** "use, share, and adapt" with attribution, and no stated limit on commercial or non-commercial use (checked). SEPA's OGL is its own assumption, not Scottish Water's statement |
| 2. May publish forecasts and accuracy scores built from it? | **Yes.** OGL v3 allows you to "adapt the Information" and combine it "with other Information" in "your own product or application" (checked) | **Yes, inferred.** "adapt" is stated; scores are an adaptation. Nothing stated forbids it |
| 3. Credit line required? | OGL v3 default, as Scottish Water states no specific wording for the files (checked on the records; the files' own tabs not opened): "Contains public sector information licensed under the Open Government Licence v3.0." | "Users must cite Scottish Water as the data source." The ArcGIS record ends "Attribution © Scottish Water" (both checked) |

Conditions that come with both (checked, quoted in sections 2 and 3):

- Do not suggest Scottish Water endorses SwimSignal or its forecasts (OGL v3 "Non-endorsement").
- Scottish Water "is not liable for third-party interpretations", and its monitors "do not confirm
  overflow events, they only indicate them".
- Its pages ask readers to check "the official Scottish Water website" for accuracy.

**Proposed credit line** (*inferred*: it meets both sets of terms as written, but Scottish Water
has not approved it):

> Overflow data © Scottish Water, from its Overflow Map API and published overflow event data.
> Event data contains public sector information licensed under the Open Government Licence v3.0.
> Scottish Water does not endorse these forecasts.

Link "Overflow Map API" to Scottish Water's API page, "published overflow event data" to its
Published Overflow Data page, and "Open Government Licence v3.0" to the licence.

**What is still open.** The API's licence has no name, no version and no link. *Inferred:* the
stated terms already cover what SwimSignal would do (show, adapt, score, credit). An unnamed licence
leaves out what OGL spells out: how the grant ends, the warranty, and which law applies. Question 1
of the draft email in `docs/SCOTLAND-PLAN-2026-10.md` section 8.1 still asks Scottish Water to name
it. Whether that answer must come before a shadow test, or only before release, is Ethan's call.

## 2. Near-real-time API: "Overflow Map API"

### 2.1 What the page states

Checked, page title "Overflow Map API - Scottish Water", heading "How to Access our Near Real-time
Data", https://www.scottishwater.co.uk/Help-and-Resources/Open-Data/Overflow-Map-Data. The
"Terms of Use" section, exactly:

> Other overflow maps may use different icons, colours, descriptions, and statuses. We are not
> responsible for how third parties may reuse our data. For accuracy, we advise you to refer to the
> data presented on the official Scottish Water website.
>
> - Data is provided under an open license for reuse.
> - Scottish Water is not liable for third-party interpretations.
> - Users must cite Scottish Water as the data source.

"open license" is plain text, not a link (checked in the page HTML). The word "licen" appears
nowhere else on the page except in the field name `LICENCE_NUMBER` and a menu link to "Licensed
Providers" (checked).

Other wording on the page that bears on reuse (checked):

- "We are being open and transparent, sharing our data exactly as we receive it, and have provided
  a public Application Programme Interface (API) that allows you to access and reuse this data in
  your application."
- "The API is open for public use. No authentication is required, but users should respect rate
  limits and cache data where possible."
- "We can't say there has been any pollution or promise the water is safe to swim in. Our
  information can help water users make more informed decisions, but this data is not advice on
  water quality."
- "EDM monitors do not confirm overflow events, they only indicate them."

The Overflow Map page has a "Data Re-use" section with the first paragraph above, and a click-
through: "Using this map, you agree that we and our partners are not liable for your interpretation
of this information." It states no licence (checked; I read the page text and did not click "I
Agree").

Scottish Water's Open Data hub page and its Legal page state no licence (checked). The Legal page
lists only access to land, accessibility, authorised departures, community empowerment, property,
customer engagement and the code of practice. Every page footer reads "© Copyright 2026 Scottish
Water. All rights reserved." (checked). *Inferred:* the footer is the site's default notice, and the
data-specific statements above override it for the data. A licence lawyer might read the two as in
tension; that is one more reason to ask Scottish Water to name the licence.

A search found a "Terms & Conditions for Scottish Water" page hosted on termsfeed.com, dated
February 2019. No Scottish Water page I checked links to it, so I give it no weight.

### 2.2 Scottish Water's ArcGIS record of the same feed

Checked: the hosted layer "Scottish Water Overflow Map Data" (item `b5124ddad99e4dff98d56df83cf65ac3`)
belongs to the ArcGIS organisation named "Scottish Water" (org id `SClJFeTjrkPbtMzT`), and its
owner account is a Scottish Water one. The plan of 4 October said the Scottish Government's spatial
data service published it; that is the harvester shown on data.gov.uk, not the owner. Its
"licenseInfo" field (terms of use), exactly (its headings in bold; HTML tags removed):

> This dataset is provided for general information, transparency, and analytical purposes. The
> data represents recorded overflow events and should not be interpreted as real-time conditions or
> confirmation of pollution events. Event Duration Monitoring (EDM) data may include inaccuracies or
> false activations due to operational or environmental factors. Visualisations created by third
> parties may use different symbols, colours, classifications, or interpretations of this data.
> Scottish Water is not responsible for how this data is used, displayed, or interpreted outside of
> its official platforms. For authoritative public information, users should refer to the official
> Scottish Water website and overflow map.
>
> **Reuse and Licensing**
>
> This dataset is provided under an open licence for reuse. Users are free to
> use, share, and adapt the data, subject to appropriate attribution. All reuse must include
> attribution to Scottish Water as the data source.
>
> **Liability**
>
> Scottish Water makes no warranties regarding the completeness, accuracy, or fitness
> for purpose of the data. Scottish Water shall not be held liable for any loss, damage, or
> misinterpretation arising from the use of this dataset.
>
> **Attribution**
>
> © Scottish Water

It has no links. The item was created 25 March 2026 and last modified 28 May 2026. *Inferred:* the
ArcGIS layer and the API carry the same data (the item says it is "derived from publicly available
Scottish Water overflow data"), so these terms are Scottish Water's terms for the feed, and the
clearest written statement of what "open license" means.

Its data.gov.uk record (publisher "Scottish Government SpatialData.gov.scot") shows "Licence: Not
set" on the page (checked). Its metadata keeps `access_constraints = ["Open Government Licence
(OGL)"]` with no version and an empty `licence` field (checked, data.gov.uk's CKAN API). The page
no longer shows the access constraint, which the 4 October plan quoted.

The layer's data was last edited at 00:04 UTC on 16 October, 19 minutes before I read it
(checked). On 4 October it was 39 hours old. One reading each, so *inferred* only: it may now be
refreshed hourly, as its description says.

### 2.3 One request to the API

Checked: one plain GET from this Mac at 00:22:56 UTC on 16 October 2026, to
`https://api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time`, no key, with
SwimSignal's User-Agent from `src/dipcast/config.py` and `Accept-Encoding: gzip`. No other request
was made to the API.

| Item | What I found |
|---|---|
| Answer | HTTP/2 200, 2,956,821 bytes in 0.22 s, from 20.26.243.94 |
| Headers | Only `date`, `content-length` and `request-context` (an Azure Application Insights id). No `content-type`, no compression although gzip was asked for, no cache, ETag or rate-limit headers |
| Shape | `{"results": [...], "last_updated": <epoch ms as a string>}`. `last_updated` was 00:00:38 UTC, 22 minutes before the request |
| Rows | 2,072, one per `ASSET_ID` (2,074 on 4 October). Latitude 54.79 to 60.76 |
| Fields | 33 on every row, every value a string, including numbers and booleans (the page's example shows numbers and booleans, and lists 31: the live answer adds `OVERFLOW_DISCHARGEID` and `OVERFLOW_DISCHARGEID_PREVIOUS`) |
| Status | 1,324 No Overflows (15), 411 Recent Overflow (14), 66 Overflowing (13), 271 No Data Available (16) |
| Why no data (`INTERNAL_OVERFLOW_STATUS_ID`) | 210 under maintenance (19), 28 no data in 48 hours (17), 27 not real-time monitored (20), 3 no valid data (18), 2 non-matching asset id (23), 1 inactive device (21) |
| Types | CSO 1,732; SSSO 177; EO 102; CSO/EO 58; CSO/SSSO 2; CSO/SSSO/EO 1 |
| Freshness | 1,829 rows have a `DEVICE_LAST_TRANSMITTED_DATETIME`; 1,755 of them within 6 hours; median age 1.3 hours |
| Rain | `RAINFALL_HISTORY` filled at 1,795 rows: 48-hour rain in mm, source not stated |

The 33 fields: `ASSET_ID`, `ASSET_NAME`, `SW_UNIQUE_MEASUREMENT_POINT_DESCRIPTION`,
`LICENCE_NUMBER`, `OVERFLOW_TYPE`, `RECEIVING_WATER`, `LOCAL_AUTHORITY_NAME`,
`DISCHARGE_OVERFLOW_LOCATION_GRID_REFERENCE`, `_POSTCODE`, `_X`, `_Y`, `_LATITUDE`, `_LONGITUDE`
(each `DISCHARGE_OVERFLOW_LOCATION_…`), `OVERFLOW_STATUS_ID`, `OVERFLOW_STATUS_DESCRIPTION`,
`INTERNAL_OVERFLOW_STATUS_ID`, `OVERFLOW_START_DATETIME`, `OVERFLOW_END_DATETIME`,
`OVERFLOW_DURATION_MIN`, `OVERFLOW_DISCHARGEID`, and the same four with `_PREVIOUS`,
`TOTAL_OVERFLOWS_DURATION_MIN_PAST_48_HRS`, `LAST_TRANSMITTED_DATETIME`,
`DEVICE_LAST_TRANSMITTED_DATETIME`, `INVESTMENT_PRIORITY`, four `IS_INVESTMENT_DRIVER_…` flags
(aesthetic, water quality, operating in dry weather, emergency storage), and `RAINFALL_HISTORY`.

| Property | Finding |
|---|---|
| History | Two events per asset: the latest and the one before (checked). The page documents one endpoint and no query parameters for past dates (checked). The oldest "latest" start in the answer was 24 November 2024, at an asset with no event since |
| Update rate | "updated every 60 minutes. However, not all the overflows record data and update data at the same frequency" (page, checked). One `last_updated` reading agrees: 00:00:38 UTC |
| Times | UTC in the API, UK local time on the map (page, checked) |
| Rate limits | "users should respect rate limits and cache data where possible", with no number (page, checked). No rate-limit headers (checked). The site's current plan, one request per build, is about one every three hours (`docs/SCOTLAND-PLAN-2026-10.md` section 8.1) |

### 2.4 Can a GitHub Actions runner reach it?

**Not tested.** This task allowed one request from this Mac only. A runner test needs a throwaway
workflow on a throwaway branch, with a read-only token, deleted afterwards; it was not run.

What bears on it (checked): the API host answered a plain curl request from this Mac. The main
website, www.scottishwater.co.uk, sits behind an Azure Application Gateway that returned
"403 Forbidden" to the same kind of curl request, for both pages in this note, while the in-app
browser loaded them. The API's address, 20.26.243.94, and its `request-context` header point to
Microsoft Azure.

*Inferred:* the API does not filter script clients the way the website does, so it is more likely
than the website to answer a runner. Whether it refuses cloud address ranges is unknown. Task S4 in
the Scotland plan already puts the runner test first.

## 3. Annual event files: "Published Overflow Data"

### 3.1 What the pages state

Checked: Scottish Water's Published Overflow Data page,
https://www.scottishwater.co.uk/Your-Home/Your-Waste-Water/Overflows/Overflow-Event-Data, states
**no licence**. Its text and HTML contain no "licence", "license", "OGL" or "reuse" wording for the
data. Its download buttons lead to the document hub page
(https://www.scottishwater.co.uk/help-and-resources/document-hub/key-publications/urban-waters-improvements),
which lists the two files and states no licence either. Both carry the "All rights reserved" footer.

The licence is stated on data.gov.uk, on two records whose publisher is Scottish Water (checked,
web pages and CKAN API):

| Record | Licence field | Links to | Last updated |
|---|---|---|---|
| "Scottish Water Reported Overflow Event Data to SEPA 2021 - 2025 & Summary Version 2 published 05/08/26" | "UK Open Government Licence (OGL)" (`uk-ogl`) | https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ | 9 September 2026 |
| "Scottish Water Non-Reported Overflow Event Data 2022 - 2025 & Summary Version 2 published 31/08/26" | "UK Open Government Licence (OGL)" (`uk-ogl`) | the same OGL v3 page | 9 September 2026 |

Neither record gives a specific attribution statement (checked: no author, maintainer or
attribution field, and none in the description). Those are the only two records under the
Scottish Water publisher (checked).

*Inferred:* a record entered under Scottish Water's own publisher account is Scottish Water's
statement of the licence, even though its own pages do not repeat it. The files themselves were not
opened (downloading them needs Ethan's yes). Their metadata or user-guidance tabs may carry licence
or credit wording; task S1 should look when it opens them.

### 3.2 The OGL v3 terms that matter here

Checked, https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/:

> You are free to:
> copy, publish, distribute and transmit the Information;
> adapt the Information;
> exploit the Information commercially and non-commercially for example, by combining it with
> other Information, or by including it in your own product or application.
>
> You must (where you do any of the above):
> acknowledge the source of the Information in your product or application by including or linking
> to any attribution statement specified by the Information Provider(s) and, where possible, provide
> a link to this licence;
>
> If the Information Provider does not provide a specific attribution statement, you must use the
> following:
>
> Contains public sector information licensed under the Open Government Licence v3.0.

> This licence does not grant you any right to use the Information in a way that suggests any
> official status or that the Information Provider and/or Licensor endorse you or your use of the
> Information.

Among its exemptions is "personal data in the Information". *Inferred:* the files hold asset
postcodes and grid references, not people, so the exemption does not bite.

### 3.3 Fields, history and update rate

Checked, from the data.gov.uk descriptions (the files were not opened):

- **Reported to SEPA, 2021 to 2025.** Overflows with annual reporting in their EASR discharge
  permits. Per event: asset, measurement point and permit details, start and stop time
  (dd/mm/yyyy hh:mm:ss), duration ([h]:mm:ss) and volume (m³), for each event over 15 minutes
  30 seconds. Per measurement point and year: total number, duration and volume (if required),
  overflow type, bathing-season-only reporting, asset postcode, local authority, X and Y
  (eastings and northings) and receiving water. A Version History tab.
- **Not reported to SEPA, 2022 to 2025.** Overflows with permit requirements for permanent event
  monitoring, or with monitoring data, that are not in the annual return. The same per-event and
  summary fields without volume and bathing-season flag. The summary "includes a column which
  confirms whether all events based on available data have been published or only those greater
  than 15 minutes 30 seconds."
- **Coverage.** About 300 reported locations; about 1,000 more added for 2025 (Published Overflow
  Data page, checked). The page says "published data covers only monitored overflows where data has
  been quality assured."
- **History.** A rolling five years: "From 2025, updates are published annually for the previous
  five years" (checked). Only the two current files are listed now (checked); earlier editions back
  to 2017 were published but are no longer on the hub.
- **Update rate.** Annual, usually March. In 2026, 11 May (pre-election period) and August for the
  2025 additions. "In March 2027, we plan to publish annual available overflow event data for 2026
  for all locations shown on the map" (checked).
- **Caveats stated.** No reasons for events. PFI operators' overflows are not included ("Scottish
  Water does not publish information that other operators report to SEPA"). "Any grid references
  within the data set relate to the asset location/monitoring point and not the receiving water."
- **Access.** Static files on www.scottishwater.co.uk, so behind the same gateway that refused
  curl (section 2.4). *Inferred:* fetch them by hand, off CI, as task S1 already plans.

## 4. SEPA's reply, against what Scottish Water states

SEPA said it would "assume" OGL (relayed; not read by me). Checked against the sources:

- For the **annual files**, Scottish Water's data.gov.uk records say OGL v3. SEPA's assumption
  matches what Scottish Water states.
- For the **API**, Scottish Water states "an open license for reuse" and "free to use, share, and
  adapt ... subject to appropriate attribution". It does not name OGL. SEPA's assumption is
  consistent with those terms but is not Scottish Water's statement.

SEPA's own 2020–25 file ("Overflow events reported to SEPA") is out of scope here; its licence
is still unanswered.

## 5. What this changes

- The 4 October plan's finding 2 ("The live feed's licence is not named") still holds. The
  ArcGIS record now gives written grant terms ("use, share, and adapt"), which the plan did not
  have.
- The ArcGIS copy belongs to Scottish Water, and was fresh on 16 October. It may serve as a
  fallback for the API; that needs more than one reading.
- The website refuses curl. Any script that fetches Scottish Water's pages or files will need a
  browser or a manual step.

Not done here, on purpose: no adapter, no email, no runner test, no file download.

## 6. Sources

All read on 16 October 2026, 00:20 to 00:40 UTC, in the in-app browser unless marked.

Scottish Water:
- Overflow Map API page: https://www.scottishwater.co.uk/Help-and-Resources/Open-Data/Overflow-Map-Data
- API, one GET with curl at 00:22:56: https://api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time
- Published Overflow Data page: https://www.scottishwater.co.uk/Your-Home/Your-Waste-Water/Overflows/Overflow-Event-Data
- Document hub with the two files: https://www.scottishwater.co.uk/help-and-resources/document-hub/key-publications/urban-waters-improvements
- Overflow Map page: https://www.scottishwater.co.uk/your-home/your-waste-water/overflows/live-overflow-map
- Open Data hub: https://www.scottishwater.co.uk/help-and-resources/open-data
- Legal page: https://www.scottishwater.co.uk/about-us/what-we-do/legal
- curl to the API page and the Published Overflow Data page: both "403 Forbidden", server
  "Microsoft-Azure-Application-Gateway/v2"

ArcGIS (curl):
- Item record, `licenseInfo` and owner organisation: https://www.arcgis.com/sharing/rest/content/items/b5124ddad99e4dff98d56df83cf65ac3?f=json
- Organisation name: https://www.arcgis.com/sharing/rest/portals/SClJFeTjrkPbtMzT?f=json
- Layer edit times: https://services3.arcgis.com/SClJFeTjrkPbtMzT/arcgis/rest/services/Scottish_Water_Overflow_Map_Data/FeatureServer/0?f=json

data.gov.uk (pages in the browser; metadata by curl from https://ckan.publishing.service.gov.uk/api/action/package_show?id=…):
- Reported events: https://www.data.gov.uk/dataset/c885ee0b-22f9-4184-9a37-cec9b3207216/https-www-scottishwater-co-uk-your-home-your-waste-water-overflow-event-data-v2-published-05-08-26
- Non-reported events: https://www.data.gov.uk/dataset/146660d4-485d-4aec-989a-560f2a64b694/www-scottishwater-co-uk-help-and-resources-document-hub-key-publications-urban-waters-improvements
- Map data: https://www.data.gov.uk/dataset/57fff4dc-b8fd-4baa-a08c-3a5132359866/scottish-water-overflow-map-data
- Scottish Water's records: https://ckan.publishing.service.gov.uk/api/action/package_search?fq=organization:scottish-water

Licence: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
