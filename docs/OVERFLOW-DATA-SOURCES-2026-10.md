# Storm overflow data SwimSignal does not yet use: what exists, and what it could feed

Written 25 October 2026. Research only: nothing was trained or scored, and no model, page or data file in the repo
changed. Labels: **[read]** a page or document fetched that day; **[checked]** a request to the live service, or a
file opened, that day; **[inferred]** my reading, not on any page.

## Why

The radar rain check (`docs/RADAR-RAIN-CHECK-2026-10.md`, 25 Oct) found that perfect rain barely helps the spill
forecast. The limit is what the model knows about overflows outside United Utilities, the only company it is
trained on. The project already holds the EA start/stop files for all ten companies (2024, 2025, 2026 to August),
live polls of nine companies since September, and older histories for Northumbrian, Wessex and Thames
(`docs/EARLIER-SPILL-HISTORY-2026-10.md`). It lacks upgrade dates, overflow size, and any direct measure of river
quality near overflows. This note says which of those exist, are open, and could be used.

Read first, so as not to repeat them: `docs/REVIEW-2026-10-16.md` §4, `docs/EARLIER-SPILL-HISTORY-2026-10.md`,
`docs/PE-SOURCES-2026-10.md`, `docs/UPGRADED-OVERFLOWS-2026-10.md` and `docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`.
The EA consents register (internal use only) is not repeated here.

## In short

- **No section 82 river-quality data is published yet, by anyone.** Defra's own standard says the duty "has not yet
  commenced" (August 2024) [read]. The EA's PR24 programme gives each of the nine English companies a statutory
  action to monitor upstream and downstream of 3,670 assets by 31 March 2030 [checked]. Once in force, readings must
  be public within one hour [read]. Nothing to use before 2030 [inferred].
- **No source gives an actual completion date per overflow.** Three things come close, and together they bound a
  date:
  - the EA's annual returns now say, per overflow and year, whether an improvement was completed or ongoing. The
    project already reads this layer and drops those columns [checked];
  - the EA's PR24 programme (WINEP) gives a regulatory deadline per action. For Ilkley's six overflows it is
    31 March 2026 [checked]. 92% of improvement actions join to an annual-returns permit reference [checked];
  - Southern Water publishes planned start and finish dates per overflow. None finishes before 2027 [checked].
- **More event history for two companies outside United Utilities.** Southern Water's own site has start/stop files
  from 2017, and Yorkshire Water's from 2021 [checked]. The earlier-history note listed both as missing. Neither page
  states a licence.
- **Live in-river ammonium and oxygen, from the EA, open.** The EA Hydrology API had 78 ammonium and 191 dissolved
  oxygen series reporting today, every 15 minutes, no key, OGL [checked]. Twelve stations are within 5 km of a listed
  spot, eight of them on becks around Windermere [checked].
- **E. coli truth at three listed spots.** Wessex Water's CC BY 4.0 river samples hold 4,123 E. coli results at 99
  sites, 2019 to 2025. 322 are at Warleigh Weir, 174 near Farleigh Hungerford and 98 at Tellisford Weir [checked].
- **Population equivalent stays parked.** Nothing new meets the reopen rule in `docs/PE-SOURCES-2026-10.md`.

## 1. The sources, ranked by use to the forecast

| # | Source | Publisher | What it adds | Licence | Access | Coverage | Latest data | Commercial use | Could feed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | EDM annual returns, improvement and investigation columns | Environment Agency | Per overflow and year: improvement completed or ongoing, by type; investigations | OGL v3 [checked] | ArcGIS REST, no key; the layer the build already reads | 10 companies, England; return years 2024 and 2025 (empty in 2023) [checked] | 2025 return; layer edited 20 Oct 2026 [checked] | Yes (OGL) | Option B cross-check and dead-monitor check; page note |
| 2 | PR24 Water Industry National Environment Programme (WINEP) | Environment Agency | Regulatory deadline per action, improvement type, permit reference; proposed storage or flow in text for some rows | "Open Government Licence" in the catalogue; the attribution line says "All rights reserved" [checked] | One XLSX, 6.9 MB, no key; also an ArcGIS app | 19 companies in England; actions due 2025 to 2035 [checked] | Issued to companies 17 Jan 2025; catalogue record modified 18 Sep 2026 [checked] | Yes, if OGL holds [inferred] | Option B cross-check and dead-monitor check; page note |
| 3 | Individual spill data, 2017 to 2025 | Southern Water | Event start and stop, storm and emergency split | None stated; page footer "All Rights Reserved" [read] | CSV and XLSX on the company site, no key | Southern, 2017 to 2025 [checked] | 2025 file, modified 5 May 2026 [checked] | Not granted | Spill model: more years and per-overflow priors |
| 4 | Individual stop/start events, 2021 to 2026 | Yorkshire Water | Event start and stop, current EA ids, GMT | None stated on the page [read] | XLSX on the company site, no key | Yorkshire, 2021 to 2026 [checked] | 2026 file, modified 12 Oct 2026 [checked] | Not granted | Spill model: more years and per-overflow priors |
| 5 | Hydrology API, water quality series | Environment Agency | 15-minute ammonium, dissolved oxygen, turbidity, pH, conductivity, temperature from EA sondes | OGL v3 [read] | REST API, no key | 78 live ammonium stations on 25 Oct; 1,818 ever [checked] | 25 Oct 2026 21:32 UTC [checked] | Yes (OGL) | Page note; a check on spill status; a stated E. coli test |
| 6 | Wessex Water Environmental Water Quality 2019-2025 | Wessex Water | River samples with E. coli, enterococci, ammonia, oxygen | CC BY 4.0 [checked] | ArcGIS REST, no key | Wessex region, Sep 2019 to Dec 2025; 106,516 results [checked] | 17 Dec 2025 [checked] | Yes (CC BY) | E. coli estimate: held-out checks |
| 7 | Storm overflow investment ("Clean Rivers and Seas Plan") | Southern Water | Per overflow: solution, cost, planned start, finish and regulatory dates | None on the item [checked] | ArcGIS REST, no key | Southern, 974 overflows [checked] | Edited 29 Sep 2026 [checked] | Not granted | Option B: dates set beside the rule's |
| 8 | `overflow_context` and `pr24_storm_overflow_improvements` | Wessex Water | Per overflow: planned completion year; 2020-25 work in words, some with storage m³ and flow l/s | None on either item [checked] | ArcGIS REST, no key | Wessex, 1,479 and 1,298 rows [checked] | Edited 22 Oct 2026 and 30 Jul 2025 [checked] | Not granted | Page note; option B dates beside the rule's |
| 9 | National Storm Overflows Plan data | Water UK (copy on Stream) | Per overflow: planned year, improvement types, predicted spills after the scheme | None on the Stream item; Water UK's terms forbid copying without written permission [read] | ArcGIS REST, or one XLSX | 14,187 overflows, 9 English companies; plan as of March 2024 [read] | Superseded by Ofwat's PR24 decision, says Water UK [read] | No | Nothing without permission |
| 10 | Total daily volume (TDV) at treatment works | Thames Water; United Utilities; Southern Water | Daily treated flow per works, with meter fault notes | None stated; Thames footer "All rights reserved" [read] | XLSX on company sites | Thames 2019 to 2025; UU 2023; Southern 2019 to 2025 [read] | Thames 2025 file [read] | Not granted | Little [inferred] |
| — | Section 82 continuous water-quality monitoring | The companies, under Defra | Upstream and downstream DO, temperature, pH, turbidity, ammonia | Not yet published | Not yet published | None yet | None | — | Later: spill truth and a sewage marker |

Notes on the ranking:
- Rows 1 and 2 rank first because they are open, cheap and speak to the open question in option B: is a silent
  overflow upgraded, or is its monitor dead? Neither gives a day. Together they give a window [inferred].
- Rows 3 and 4 are the only new data for the spill model itself. The multi-year test (PR #259) found that extra years
  alone moved the Brier score by -0.00066 [-0.00149, +0.00013]. So expect a small gain at best [inferred]. Their
  licence is the bar.
- Rows 5 and 6 are about the river, not the overflow. They are the only direct measures of water quality near
  overflows found.
- Rows 7 to 9 are plans. Plans say what should happen, not what did.

## 2. Each source, as checked

### 2.1 EA annual returns: the improvement and investigation columns

- **Where.** `edm_annual_returns_all_years_public`, the layer in `config.EDM_ANNUAL_RETURNS`. Owner
  `Peter.Boden_environment`, item 66fef44a4aab438991d7ce08fbc1de64. Its licence field names "Open Government Licence
  version 3" and credits the Environment Agency [checked].
- **Not read today.** `data/processed/annual_returns.parquet` has 21 columns. None of them is
  `improvement_activity_for_the_reporting_period` or `investigation_activity_for_the_reporting_period`. No code in
  `src/` or `scripts/` names either [checked].
- **What the columns hold** (2025 return, 14,303 rows) [checked]:
  - "No improvement action in reporting period": 11,033.
  - "Operational improvement completed", alone or with others: 1,646.
  - "Env Act (SODRP) improvement ongoing", alone or with others: 1,073.
  - A regulation-led improvement completed (UWWTR, SODRP or bathing/shellfish water): 79. The Rivers Trust gives the
    same 79 for 2025 [read].
  - In the 2024 return: 1,380 operational completed, 77 regulation-led completed. The 2023 return has the columns
    empty [checked].
- **Also in the layer.** `edm_operation_action_taken_planned_status_timeframe` says what was done about a faulty
  monitor, for example "Resolved - Dec" for YWS00191 in 2024 [checked]. PR #251's rule uses only
  `edm_operation_percent`.
- **A warning, from Ilkley.** All six overflows Yorkshire Water names at Ilkley read "No improvement action in
  reporting period" in 2025. Bridge Lane's works started on 17 Nov 2025 (`data/raw/overflow_upgrades.csv`). So the
  flag misses work under way, or counts only finished work [inferred]. The 2026 return, due about March 2027, is the
  first that could show Ilkley's work [inferred].
- **Grain.** A year, not a day.

### 2.2 EA PR24 WINEP

- **Where.** data.gov.uk dataset cf9b80c2-cae9-4ed1-88ce-890940be379a, "PR24 Water Industry National Environment
  Programme". One XLSX, "PR24 WINEP National Dataset.xlsx", 6,898,298 bytes, opened in scratch [checked]. The
  catalogue says it "was issued to water companies on 17th January 2025" [checked].
- **Layout.** Sheet "PR24 WINEP National Data": 18,598 actions, 83 columns. A row has the company, driver code,
  action name and description, permit reference (`Licence_Permit_Obstruction_ID`), water body, `Completion_Date`,
  quarter and financial year [checked]. The READ ME defines `Completion_Date` as "the date the Action should be
  delivered" [checked]. It is a deadline, not a record of delivery.
- **Storm overflow drivers** [checked]:
  - EnvAct_IMP2 to IMP5 (spill reduction, bathing water, the 10-spill target, screens): 2,534 actions. Almost all
    are due 31 March 2030; a few in 2027, 2028 or 2035.
  - Bathing water and shellfish water (BW_IMP1 to 4, SW_IMP): 106 actions.
  - EnvAct_INV4 investigations: 6,183, mostly due 30 April 2027.
  - 28 improvement actions were due by today, all on 31 March 2026: South West 12, Yorkshire 9, United Utilities 6,
    Thames 1.
- **Ilkley** [checked]. BW_IMP1 for Low Mill Lane, Addingham No 1 (two rows), Bridge Lane, Rivadale View and
  Ilkley Middleton, each due 31 March 2026, "One spill per bathing season within 5km upstream of the inland bathing
  water designated site". BW_IMP4 at Ilkley STW, same date: "Notional 300l/s FFT, notional 17,500m3 storage". PR #298
  found Middleton's last 2026 discharge on 31 March and the others' between 7 Feb and 8 May. That fits delivery near
  the deadline [inferred]. It does not prove it.
- **Joining to overflows** [checked]. Of 2,640 improvement actions (EnvAct_IMP2 to 5, BW_IMP, SW_IMP), 2,419 (92%)
  match a permit reference in the 2025 annual returns. By company 78% (Anglian) to 100% (Southern). 333 of the
  matches name a permit shared by several overflows, which needs the activity reference to split.
- **Licence.** The catalogue's `licence` field says "Open Government Licence"; its attribution line says "©
  Environment Agency copyright and/or database right 2025. All rights reserved." [checked]. The EA's start/stop
  files had the same mismatch, settled as OGL in `docs/WALES-PLAN-2026-10.md` §2.2. I assume the same here
  [inferred].

### 2.3 Southern Water and Yorkshire Water event histories

`docs/EARLIER-SPILL-HISTORY-2026-10.md` found "no open event-level record before 2024" for five companies, two of
them Southern and Yorkshire. It searched ArcGIS. Both companies post files on their own sites.

- **Southern Water.** "Flow and overflow release reporting" page [read]. Files opened [checked]:
  - 2017-19, one CSV: start and end date and time, spill count, duration, per site number and EA number.
  - 2020 and 2021 CSVs: the same, with a schedule type column ("Storm Sewage" in the rows seen).
  - 2022 XLSX, sheets "2022 Storm 1224 Count" (8,020 rows) and "2022 Emergency 1224 Count". Times are on the hour,
    so these may be 12/24-hour count blocks, not raw events [inferred].
  - 2023 XLSX: raw events to the second, 11,181 storm and 532 emergency.
  - 2024 and 2025: listed [read]. The 2025 file was modified 5 May 2026 [checked].
  - Ids are Southern's site numbers and EA permit numbers, not the annual returns' `SWS` ids. A crosswalk by events,
    as for Wessex, would be needed [inferred].
  - Licence: none on the page. Footer: "Copyright © 2024 Southern Water. All Rights Reserved." [read]. Southern's
    Stream layers are CC BY 4.0, which suggests it would agree if asked [inferred].
- **Yorkshire Water.** "Event Duration Monitoring (EDM)" page [read]. "Individual stop/start events" for 2021 to
  2026 to date. The 2021 file holds 230,581 events with columns `Unique ID` (current `YWS` ids),
  `Discharge Start (GMT)`, `Discharge Stop (GMT)` and duration [checked]. The 2026 file was modified 12 Oct 2026,
  12.4 MB [checked]. No licence text on the page [read].
- **Use.** More years at two companies outside United Utilities, for the spill model's per-overflow layer and for
  priors. Event definitions differ by company (PR #258), so each needs the same checks as Northumbrian and Wessex.

### 2.4 EA Hydrology API: water quality sondes

- **What.** The EA's own sondes, not the companies'. The Hydrology API lists 15-minute instantaneous series for
  dissolved oxygen, fDOM, blue-green algae, turbidity, chlorophyll, conductivity, temperature, ammonium, nitrate and
  pH. "All content is available under the Open Government Licence v3.0" [read].
- **How much is live** [checked]. Readings since 15 Oct 2026: 78 ammonium series and 191 dissolved oxygen series,
  latest 25 Oct 2026 21:32 UTC. 1,818 stations have ever had an ammonium series. Many are short deployments, named
  with a start month (for example `STOUR_CATTAWADE_E_202604`).
- **Near listed spots** (straight line, not along the river) [checked]. 12 live ammonium stations within 5 km, 31
  within 15 km. Eight are becks around Windermere (Mill Beck, Trout Beck, Leven at Newby Bridge, Dubbs Beck,
  Blelham Beck, Cunsey Beck at three points). Others: the tidal Thames (Cadogan Pier, Hammersmith, Putney), the
  Stour near Dedham (Cattawade, Boxted Mill) and the Rhee near Grantchester.
- **Not the same as the ruled-out source.** The review of 16 Oct ruled out the blue-green algae sensors (zero 2026
  readings). The ammonium and oxygen series are live.
- **Use.** Ammonium is a sewage marker. A rise downstream of an overflow during a reported spill is independent
  evidence of it [inferred]. It could give a page line where a sonde sits near a spot. Any model use needs a stated
  test. Coverage is thin and the stations move [inferred].

### 2.5 Wessex Water's river samples (E. coli)

- **Where.** `Wessex_Water_Environmental_Water_Quality_view`, item 4659ab28caa640c58e725b41ecbba79f, owner
  `WessexWaterData`. "Wessex Water Environmental Water Quality © 2026 by Wessex Water is licensed under CC BY 4.0"
  [checked].
- **What** [checked]. 106,516 results. Fields: date, determinand, units, operator (for "<"), result, position, type.
  River E. coli: 4,123 results at 99 positions, 75 with 20 or more, 11 Sep 2019 to 15 Dec 2025. Enterococci 4,137.
- **At listed spots** [checked]. Warleigh Weir (`avon-warleigh-weir`): 272 and 50 results at two points 50 m away.
  Farleigh Hungerford (`bw-ukk2301-36051`): 151 and 23 at 1 km. Tellisford Weir (`frome-tellisford-weir`): 68 and
  30 at 210 m.
- **Use.** Held-out checks of the E. coli estimate at non-bathing sites, never training (the review's rule for
  citizen E. coli, §4 item 8). Warleigh Weir is not a designated bathing water, so the EA archive has no samples
  there [inferred].

### 2.6 Company plan layers

- **Southern Water, "Clean Rivers and Seas Plan"** (`COR_RO_StormOverflow_Investment_PROD_View`, web map item
  c2789367439c4154b6de59990c8fe417) [checked]. 974 overflows with `overflow_id_new` (`SWS` ids), solution
  (screen only 356, SuDS and storage 324, storage only 102, sealing 57), cost, and planned start, finish and
  regulatory dates. 297 have a finish date: 53 in 2027, 58 in 2028, 2 in 2029, 85 in 2030, 99 in 2035. None
  before today. No licence on the item.
- **Wessex Water, `overflow_context`** (item 3ff7018195fd496da08e1009185d4600), behind the company's coast and
  rivers map [checked]. 1,479 overflows with `National_Unique_Id`. `Construction_complete` is empty on every row.
  `Future_Construction_Complete` holds years ("2023 or before" 558, then 2024 to 2050). `What_are_we_doing` gives
  2020-25 work in words for 82 overflows, 30 with a storage volume. For example WSX0612: "Provision of 150m3 storm
  storage & increase FPF from 5l/s to 9l/s". Planned years only, no dates. No licence on the item.
- **Wessex Water, `pr24_storm_overflow_improvements`** (item c01a7765966b4e2f99afe33bc3ec5965) [checked]. 1,298 rows;
  `Current_Construction_Complete` is empty on every row. No licence.
- **Water UK, National Storm Overflows Plan** [read, checked]. Stream copy `National_Plan_Data_` (item
  40b3997ad1724f308573f00fcb1e315c, with current ids) and the original
  (5f44823642834c00a15c7e95e913065a). 14,187 rows. Fields include `Spill_improvements_planned_` (a year; 4,377
  rows read 2023, a value the data does not explain), `Improvements_List`, and predicted spills after the scheme.
  Five of Ilkley's six read 2026 with 3 predicted spills a year; Bridge Lane reads 2023 with none. Water UK's page says the plan "has now been superseded by the Ofwat Final
  Determinations Report for PR24" and shows the plan "as of March 2024". Its terms: "no part of the website may be
  copied ... or used for any purpose" without written permission; report extracts for "non-commercial purposes
  only". Do not use.

### 2.7 Daily treated flow (TDV)

- **Thames Water** posts "total daily volume (TDV) data showing the amount of wastewater treated each day", 2019 to
  2025, and says it reports this to the EA yearly [read]. **United Utilities** posts "2023 Flow Data - Total Daily
  Volume (TDV)": 304 works, 18 Apr 2022 to 31 Dec 2023, 84,598 numeric days and 26,773 text notes such as "Flow
  meter failure" [checked]. **Southern Water** posts daily flow data from 2019 [read].
- **Use.** Treated flow tops out at the works' flow to full treatment, so a run of days at the top may mark a works
  at capacity [inferred]. It says nothing about network overflows. No licence on any page. Low rank.

### 2.8 Wessex Water Quality Live layer

`rwq_test_data` (item 04651145f74c412498637b152e737bce), "Test layer for River Water Quality data for three sites",
holds the sensor fields and predicted E. coli fields behind waterqualitylive.info, a service the verification page
already cites [checked]. On 25 Oct it had three rows, with temperature, flow and a "lower risk" message filled and
the sensor readings empty. No licence. Not a source yet.

## 3. Question 1: section 82 water-quality monitoring

- **The law.** Section 141DB of the Water Industry Act 1991, inserted by section 82 of the Environment Act 2021.
  Undertakers wholly or mainly in England "must continuously monitor the quality of water" upstream and downstream of
  storm overflows and sewage works that discharge to a watercourse. Parameters: dissolved oxygen, temperature, pH,
  turbidity, ammonia. Exceptions and a duty to publish come only through regulations, which need both Houses'
  approval [read, legislation.gov.uk, text up to date to 25 Oct 2026]. The section shows as in force from
  3 Nov 2023 "for specified purposes" [read].
- **Not yet commenced.** Defra's interim technical standard, dated August 2024 and released on 18 March 2026 under
  EIR2026/03894, says the duty "has not yet commenced" [read]. No regulations under section 141DB were found
  [inferred from a search; not proven absent].
- **Timetable.** Defra's government response (updated 14 Sep 2023): "rollout of 25% of all sites by 2030";
  overflows spilling fewer than 10 times a year over 5 years are excluded [read]. The April 2023 provisional
  guidance: "Full monitoring of statutory assets must be completed no later than 2035" [read]. The PR24 WINEP
  (EnvAct_MON4, statutory, due 31 March 2030) gives each company a number of assets [checked]: United Utilities 633,
  Yorkshire 563, Severn Trent 560, Anglian 523, Wessex 356, South West 336, Northumbrian 265, Thames 218, Southern
  216. Total 3,670. A non-statutory driver (EnvAct_MON3) runs to 2035 as holding lines only.
- **Publication.** When in force: "publicly available on a visualisation platform in near real time (within one
  hour), and in a common format across England". Measured values of DO, temperature, pH, turbidity, ammonium and
  conductivity, plus derived ammonia [read, Annex C §5.3]. Defra wants "an interactive national map" [read]. No
  channel is named. The NFU (26 Aug 2026) reports that data "is expected to become publicly available from 2030"
  [read].
- **What is out now.** Nothing under section 82. Stream's ArcGIS catalogue holds drinking-water quality layers only;
  a search for river sensors, s82, sonde, ammonia and WINEP found none [checked]. Wessex's RiverHub lists "Water
  quality sensor data" as "not yet available in RiverHub, but is planned" [read]. The EA's own sondes (2.4) are the
  only live river-quality feed found.

## 4. Question 2: upgrade dates

**No source gives the day an overflow upgrade was finished.** What exists:

| Source | Grain | Open | Ilkley's six |
|---|---|---|---|
| EA annual returns, improvement column | Year, completed or ongoing | OGL | 2025: "No improvement action" for all six |
| EA PR24 WINEP | Regulatory deadline, a day | OGL [inferred] | 31 March 2026, all six |
| Southern investment layer | Planned start and finish, a day | No licence | — |
| Wessex `overflow_context` | Planned year | No licence | — |
| Water UK plan | Planned year | No | 2026 for five; 2023 for Bridge Lane |
| Company project pages (`data/raw/overflow_upgrades.csv`) | Prose | Varies | Future tense on 21 and 24 Oct |

Also checked and empty: the Stream hub's web map layers (activity feeds only), Wessex's `Construction_complete` and
`Current_Construction_Complete` fields, Yorkshire's "Environment Act Storm Overflow Report 2025" (the annual return
columns again) [checked]. Ofwat's PR24 price control deliverables were not opened; the search found no per-overflow
table [inferred].

**What this means for option B** (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, on main with its 25 Oct addendum;
no import or score yet):
- The draft's choice of a change-point rule over cited dates stands. No cited date exists for most overflows.
- The draft already says cited dates, where they exist, are "set beside" the rule's start dates and reported. WINEP
  deadlines and the annual-return flags are open and cover every company. They could be the file it sets beside
  [inferred].
- **The dead-monitor check could use them.** The draft's open risk is a silent monitor read as an upgrade. An
  overflow that goes quiet near a WINEP deadline, and later reads "improvement completed", is more likely upgraded
  than dead [inferred]. Adding that is Ethan's call. It would be a dated addendum, as arm P1 was on 25 Oct, made
  before any import, fit or score for the test.
- For `data/raw/overflow_upgrades.csv` (option C), WINEP gives a dated, citable deadline for Ilkley. It is not a
  completion date, so the `completed` column stays blank [inferred].

## 5. Question 3: overflow size and capacity (new findings only)

`docs/PE-SOURCES-2026-10.md` parked this until an open source gives PE per overflow, or per works with overflow ids.
New this time:
- **WINEP text sizes.** 285 improvement actions carry a storage volume or a flow in the description or the proposed
  permit [checked]: Southern 165, Thames 84, South West 32, a handful elsewhere. They are proposed sizes for the new
  scheme, not today's.
- **WINEP's PE column is not published.** The READ ME defines `Population_Equivalent_for_STW`; the national sheet
  has no such column [checked]. Its `Current_Permit_DWF` column is dry weather flow, which failed in PR #210.
- **Wessex RiverHub** shows "Population equivalent for WRCs", per works, Wessex only [read]. The part of the site's
  terms read (Riskaware Ltd, 30 Oct 2024) names no data licence [read].
- **Wessex `overflow_context`**: 30 storage volumes in prose (2.6).

None meets the reopen rule. PE stays parked.

## 6. Question 4: other information the current inputs lack

- **Monitor health.** Still no per-event or per-poll validity field in any feed (as `ingest/live.py` says). New and
  unused: the annual returns' `edm_operation_action_taken_planned_status_timeframe` (2.1), yearly. United Utilities'
  TDV file flags meter faults per day, at works only (2.7).
- **Cause of a discharge.** Southern's 2022 and 2023 files put storm and emergency events on separate sheets; the
  earlier ones carry a schedule type (2.3). The EA files and the
  live feeds do not.
- **Treatment works flow.** TDV (2.7).
- **River quality.** The EA sondes (2.4) and Wessex's samples (2.5).

## 7. Licences, with paid pilots in view

- **Open for commercial use with credit:** the EA layers (OGL v3: annual returns, Hydrology API, and WINEP if its
  catalogue licence holds) and Wessex's river samples (CC BY 4.0). Credit lines would go on the terms page.
- **No licence stated:** Southern's and Yorkshire's event files, Southern's investment layer, Wessex's
  `overflow_context` and PR24 layers, the TDV files. Copyright and database right still apply [inferred]. Using them
  in a model that feeds a paid pilot, or publishing anything derived, needs the company's written permission or a
  licence on the item. The same companies already license their Stream feeds CC BY 4.0, so asking is likely to work
  [inferred]. Add to the solicitor's list: does a model trained on unlicensed company data carry their rights into
  its forecasts?
- **Refused:** Water UK's plan data. Its terms forbid use without written permission.
- No email was sent for any of this.

## 8. What could follow (each its own PR; none started)

1. Read the annual returns' improvement, investigation and EDM-action columns into `annual_returns.parquet`. Data
   only, no model input.
2. Offer Ethan a dated addendum to the option B test, before any import or score: WINEP deadlines and
   annual-return flags beside the rule's start dates, and in the dead-monitor check.
3. Ask Southern Water and Yorkshire Water to put a CC BY 4.0 licence on their event files (draft only; Ethan sends).
   Then import them as PR #258 did for Northumbrian and Wessex.
4. A stated E. coli check at Warleigh Weir, Farleigh Hungerford and Tellisford Weir on Wessex's samples.
5. Watch for section 141DB regulations and a national map. Recheck in spring 2027 [inferred timing].

## Sources

All fetched or queried on 25 October 2026.

- EA annual returns layer: https://services1.arcgis.com/JZM7qJpmv7vJ0Hzx/arcgis/rest/services/edm_annual_returns_all_years_public/FeatureServer/0
  (item https://www.arcgis.com/home/item.html?id=66fef44a4aab438991d7ce08fbc1de64)
- PR24 WINEP: https://www.data.gov.uk/dataset/cf9b80c2-cae9-4ed1-88ce-890940be379a/pr24-water-industry-national-environment-programme
  and the file https://environment.data.gov.uk/api/file/download?fileDataSetId=63ec410d-733f-4042-8682-b70cf25f1d70&fileName=PR24%20WINEP%20National%20Dataset.xlsx
- PR19 WINEP (deadlines for 2020-25, not opened): https://ckan.publishing.service.gov.uk/dataset/a1b25bcb-9d42-4227-9b3a-34782763f0c0
- Southern Water flow and release data: https://www.southernwater.co.uk/about-us/environmental-performance/healthy-rivers-and-seas/flow-and-spill-reporting/
- Southern Water investment layer: https://services-eu1.arcgis.com/6qJmARkS2dt2IjVA/arcgis/rest/services/COR_RO_StormOverflow_Investment_PROD_View/FeatureServer/0
- Yorkshire Water EDM page: https://www.yorkshirewater.com/environment/river-health/storm-overflow-investment/event-duration-monitoring/
- EA Hydrology API: https://environment.data.gov.uk/hydrology/doc/reference and
  https://environment.data.gov.uk/hydrology/id/measures?observedProperty=ammonium
- EA Water Quality Live (viewer, OGL): https://www.data.gov.uk/dataset/dccd6c78-5a29-48d7-8d91-bd6a152742a5/national-real-time-water-quality-data
- Wessex Water river samples: https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/Wessex_Water_Environmental_Water_Quality_view/FeatureServer/0
- Wessex Water `overflow_context`: https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/overflow_context/FeatureServer/0
- Wessex Water PR24 layer: https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/pr24_storm_overflow_improvements/FeatureServer/0
- Wessex Water test layer: https://services.arcgis.com/3SZ6e0uCvPROr4mS/arcgis/rest/services/rwq_test_data/FeatureServer/0
- RiverHub: https://riverhub.co.uk/monitoring and https://riverhub.co.uk/terms_of_use.html
- Water UK plan: https://www.water.org.uk/overflows-plan, terms https://www.water.org.uk/terms-and-conditions,
  Stream copy https://services-eu1.arcgis.com/XxS6FebPX29TRGDJ/arcgis/rest/services/National_Plan_Data_/FeatureServer/0
- Stream catalogue search: https://www.arcgis.com/sharing/rest/search with `q=orgid:XxS6FebPX29TRGDJ AND "<term>"`
- Thames Water TDV: https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data
- United Utilities data returns: https://www.unitedutilities.com/better-rivers/our-challenges/storm-overflow-performance/
- Section 141DB: https://www.legislation.gov.uk/ukpga/1991/56/section/141DB
- Defra government response: https://www.gov.uk/government/consultations/continuous-water-quality-monitoring-and-event-duration-monitoring/outcome/summary-of-responses-and-government-response
- Defra provisional guidance, April 2023: https://assets.publishing.service.gov.uk/media/6436dc0dcc9980000cb89426/CWQM_programme_provisional_technical_guidance_for_sewerage_undertakers_April_2023.1.pdf
- Defra interim technical standard (EIR2026/03894): https://www.gov.uk/government/publications/continuous-water-quality-monitoring-programme-interim-technical-standard-eir202603894
- NFU, 26 Aug 2026: https://www.nfuonline.com/news/continuous-water-quality-monitoring-programme/
- The Rivers Trust, 31 Mar 2026: https://theriverstrust.org/about-us/news/reduction-in-sewage-spills-must-not-be-misidentified-as-progress
