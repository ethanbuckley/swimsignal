# Satellite readings on EA harmful-algae incident days at lakes: the test, stated before any fetch

Written 26 October 2026, before any run. No incident history has been fetched for this test. Nothing has been
scored. The satellite readings are #377's, already made and hashed; none of them has been looked at for this test.
Results go below the line at the end. Nothing above it changes after a result is seen.

**This statement waits for Ethan's approval.** Nothing is fetched or run until he gives it.

## The question

**Is the Sentinel-2 NDCI reading at a lake bathing water higher on days the Environment Agency has a harmful-algae
pollution incident open there than on other days at the same lake, in the same season?**

#377 (`docs/LAKE-ALGAE-SATELLITE-TEST-2026-10.md`) asked whether the reading ranks the EA sampler's weekly visual
check. It failed for "algae seen". "Objectionable" had 20 events, too few to judge; its AUC of 0.81 is description
only. A harmful-algae incident is a different label. The EA opens one when it finds a bloom it treats as harmful, and
it stays open until the EA closes it. So it covers days between sampling visits, and it marks the blooms the EA acted
on, not every trace seen at the shore.

What it cannot answer, whatever the result:
- **Toxic or not.** The reading is chlorophyll, in all algae (#377, "Why"). An incident says the EA judged a bloom
  harmful. A higher reading on those days would show the reading sees the bloom, not that it can tell harmful from
  harmless.
- **Detection or forecast.** This compares readings with incidents already open. It does not forecast one.
- **Safety.** Nothing here is a health figure.

**Whatever the verdict, nothing on the site changes, in this PR or because of it.**

## The label: an EA harmful-algae incident

### The data, from the API reference

Read on 26 October 2026 from the EA's Bathing Water Quality API reference
(https://environment.data.gov.uk/bwq/doc/api-reference.html, "This Version: api-reference-v0.6"), sections
"Pollution Incidents" and "Pollution Incident Endpoints". Open Government Licence v3.0, as the advisory finder records
(PR #379).

- A pollution-incident record has these properties: `bathingWater` (one or more), `incidentType`, `samplingPoint`,
  `sampleYear`, `startOfIncident`, `expectedEndOfIncident`, `endOfIncident`, `nirsRef`, `incidentNotation` and
  `recordDateTime`.
- `startOfIncident`: "The date and time (xsd:dateTime) at which the corresponding 'pollution-incident' was first
  recorded in the BWQ system." `endOfIncident`: the date and time at which it "actually ended".
  `expectedEndOfIncident`: a date on which it "is expected to end".
- `incidentNotation` groups several records of one incident. Each record's address ends in its `recordDateTime`.
- The list endpoint `/doc/bathing-water-quality/pollution-incident` "Lists the most recent available
  pollution-incident records for each pollution incident". It can be filtered by `bathingWater.eubwidNotation`.
- The reference's table of incident types (code, description; 001 to 005 are marked deprecated):
  001 Bacterial contamination, 002 Potential contamination from sewage, 003 Non-bacterial contamination, 004
  Localised Flooding, 005 Contamination from sewage, 010 sewage, 011 agricultural waste, 012 animal waste, 013
  decaying marine life on beach, **014 harmful algae**, 015 oil or fuel, 016 chemicals, 017 dredging or construction
  work, 018 landslip, 019 drain or road runoff, 020 other. Only 014 names algae. The reference adds that "further
  incident types may be assigned".
- The reference does not say from which year incidents are recorded. Its example record is dated 18 September 2023.
  Whether 2020 to 2022 hold any incident is not known until the fetch.
- The JSON field names are as in the advisory finder's fixtures (`incidentNotation`, `incidentType` with `notation`,
  `name` and `label`, `startOfIncident`, `endOfIncident`, `som_recordDateTime`).

### The rule

- **The field and the words.** A record is a harmful-algae incident when its **`incidentType`** has notation
  **`014`** and its name (or label) is **"harmful algae"** (case and spacing ignored). When `notation` is missing,
  the code is read from the type's address (`.../def/incident-type/014`).
- **Two stop rules on the type.** A record with code 014 and other words, or with words containing "alga" and another
  code, stops the run before any score. Either would mean the reference's table no longer describes the data.
- **One record per incident.** The latest `recordDateTime` per `incidentNotation`. An incident listed under two test
  sites is fetched twice and kept once. Two different records with the same latest time stop the run.
- **Days.** The day of a time is its date as written; the reference gives no time zone. An incident is open on its
  start day, its end day and every day between. **An incident with no `endOfIncident` is open to the fetch date**
  (the UTC date the fetch starts). `expectedEndOfIncident` is not used: it is an expectation, not an end.
- **Where.** A day is an incident day at a bathing water when a harmful-algae incident that lists that bathing water
  is open. An incident at another bathing water on the same lake does not count; those days are counted and reported.
- **Other incident types: excluded days.** A day with any other incident open at that bathing water (any other code,
  or no type), and no harmful-algae incident, is left out of the comparison. Why: codes 003 ("Non-bacterial
  contamination") and 020 ("other") could hold algae without saying so, and the rest (sewage, chemicals, dredging)
  may change the water. The number of excluded days is reported.
- **Malformed records.** A harmful-algae incident at a test site with no readable start, or an end before its start,
  stops the run. Any other incident with either is kept as its start day only (or the fetch date if it has no start),
  so its days are excluded, and it is counted.

## Sites, days and readings

- **Sites:** the 14 bathing waters past #377's size rule, on 8 water bodies
  (`docs/LAKE-ALGAE-SATELLITE-TEST-2026-10-sizes.json`, `in_test`). Out, with 0 core pixels: the three Hampstead Heath
  ponds and Henleaze Lake. They have no reading, so their histories are not fetched.
- **Days:** every day from 1 May to 30 September, 2020 to 2026, at each site. 2022 has no reading (#377, revision 3).
- **The reading:** #377's features file, used as it is. SHA-256
  `41f234d3a953df246306aa7785978e7c3d76f82ed1765e5518923633c50b5d0e`, committed in #377 (4ec237b). The harness checks
  that hash before the fetch and before the score, and stops if it differs. Usable scenes only, one per site and UTC
  date (#377's `one_per_date`: most clear core pixels, then first item id).
- **Pairing, as #377:** a day takes the latest usable scene at its site dated that day or up to 3 days before. A day
  with no such scene has no reading and is left out. Consecutive days often share one scene.

## The comparison

**Strata.** One stratum is one bathing water in one season. A stratum counts when it has at least one incident day and
at least one control day with a reading. Comparing only within a stratum means a lake that is green all season, and
a season that is green at every lake, gain nothing.

**The statistic, S.** Within each stratum, every pair of (incident day, control day) is compared: 1 if the incident
day's reading is higher, a half for a tie, 0 if lower. S is the total over all counted strata divided by the number of
pairs. It is the Mann-Whitney U summed over strata, over the pairs summed over strata: a stratified AUC. S = 0.5 means
no difference. Strata with more pairs weigh more.

**Interval.** Cluster bootstrap with water bodies as clusters (those with a counted stratum), drawn with replacement,
2,000 draws, numpy `default_rng(20261026)`. One comparison is judged, so the interval is 95% (2.5th to 97.5th
percentile).

**Labels.** The near-miss framework (addendum to `docs/LAKE-ECOLI-LINE-TEST-2026-10.md`) on d = S − 0.5, with the
interval (L − 0.5, U − 0.5): Better, Promising not shown, No useful difference, Possible harm, Harm, Too uncertain, the
first that fits; "Unlabelled" if none fits. Here "harm" means the reading is lower on incident days. Following the
note of 26 October 2026, a secondary check labelled "Possible harm" or "Harm" counts as harm.

**B and H.** The framework sets B from forecasts crossing a band cut. This reading has no band and nothing on the site
would change, so that method has nothing to work from. **B = 0.15** (S of 0.65, the AUC bar of both earlier lake
tests) and **H = 0.05**. They are a convention, stated before the data, not a measure of what a swimmer would notice.

### The gate, checked first

S is judged only if all of these hold, counting in counted strata:
- at least **30 incident days with a reading**;
- at least **5 distinct harmful-algae incidents** with an incident day with a reading;
- at least **4 water bodies** with a counted stratum;
- at least **6 counted strata** (bathing water and season).

Below that the result is **"Too few to judge"**. It cannot pass. Every figure below is still computed and reported as
description.

### It passes if the primary label is Better and all of these hold

1. **Shift placebo.** In each bathing-water season with an incident day, the whole pattern of day labels (incident,
   excluded, control) is moved round the 153-day season by an offset drawn from 1 to 152, wrapping at the ends. The
   readings stay on their days. Each stratum gets its own offset; strata in sorted order. 200 times, numpy
   `default_rng(20261026)`. S is recomputed each time. The real S must be above the 95th percentile of the 200 and
   above the 190th smallest. This asks whether the reading follows the incident's days rather than any equally long
   stretch of the same season.
2. **Seasonal anomaly.** The shift placebo moves incident days to other times of the season, so a reading that only
   rises through the summer, with incidents in late summer, passes it (the synthetic test shows this). So S is
   recomputed on an anomaly: each day's reading minus the median reading of usable scenes at the same bathing water in
   the same calendar half-month (1st to 15th, 16th to month end) of its scene, **in the other seasons**. A day whose
   reference has fewer than 5 scenes has no anomaly and is left out. This S must be **at least 0.60**, with its 95%
   interval's lower end above 0.50 (same bootstrap and seed).
3. **Leave one lake out.** S recomputed with each water body (with a counted stratum) left out in turn. Every one must
   be above 0.50, and there must be at least two. This matters most for Frensham Great Pond, whose 2026 incident was
   seen before this statement (below).
4. **No group labelled harm.** The same S, interval and label for the Lake District water bodies (Windermere,
   Coniston Water, Derwent Water) and for the lowland ones (the rest), each with its own bootstrap. Neither may be
   labelled Possible harm or Harm. A group with no counted stratum is "No data", which is not harm.
5. **Stop rules.** Both hashes match (features, and the incidents file committed before scoring); the fetch holds one
   complete page for each of the 14 sites (below); the type rule holds; no malformed harmful-algae incident; the
   scoring makes 0 network attempts. If any fails, the run stops and that is reported before any score.

**Promising, not shown** on the primary comparison, with conditions 1 to 5 holding, is reported as that. It is not
adopted and starts nothing. A later test of it would need its own statement and new seasons.

**Fails** in every other judged case.

### Why these choices

- The day unit follows the brief and #377's pairing. One scene can stand for up to four days, and incidents last weeks,
  so days are far from independent. That is why the interval is over water bodies, the placebo moves whole label
  patterns, and the gate counts incidents and water bodies, not only days.
- With 8 water bodies at most, and likely fewer with an incident, the cluster bootstrap is rough. It is used because it
  is the unit that is closest to independent.

## What is expected, stated now

These are guesses.
- **Too few to judge, most likely.** Seen already: Frensham Great Pond has a harmful-algae incident open since 19 June
  2026, and on 26 October it was the only lake site among the open incidents. A Waverley Borough Council page about
  Frensham dated 22 August 2025 suggests 2025 may hold one too (inferred from a line in the advisory finder's notes,
  not checked). Other lake incidents are not known. The reference gives no start year for incident records, and its
  example is from 2023, so 2020 to 2022 may hold none. Reaching 4 water bodies and 5 incidents looks unlikely.
- **If anything shows, it will be at Frensham.** #377 found Frensham's readings ranked the EA's checks best (AUC 0.92,
  description). Its 2026 stratum would compare 19 June to 30 September with 1 May to 18 June, which is also early
  against late season. Condition 2 is there for that.
- **What is still reported if too few:** the incidents found per site and type, the harmful-algae incidents with their
  days, S with its interval and label as description, the per-stratum table, the placebo, the anomaly S, the
  leave-one-lake-out values, and S without Frensham 2026.

## What follows

- **Whatever the verdict, nothing on the site changes.**
- **Passes:** a result to report. Whether lake spots ever show a satellite reading stays a separate decision for
  Ethan, after a forward test stated in its own file.
- **Promising, not shown; Fails; Too few to judge:** this PR stays as the record.

## The fetch

One fetch, after approval, saved with its SHA-256 before anything is scored.
- **What:** each of the 14 sites' incident history, open and closed, one request per site, sorted by id:
  `https://environment.data.gov.uk/doc/bathing-water-quality/pollution-incident.json?bathingWater.eubwidNotation=<id>&_pageSize=200`.
- **Completeness:** each page must report `itemsPerPage` 200, hold fewer than 200 items and have no `next` link, and
  every item must list the site asked for. Otherwise the score stops (a site with 200 or more incidents would need a
  second page, which this fetch does not make).
- **Caps** (`scripts/lake_algae_incident_eval/incident_fetch.py`): one request at a time, at least 1 second between
  requests, a 60-second timeout; at most 40 requests and 20 MB in all, 5 MB in one response; only `environment.data.gov.uk`
  over https; no account, token, key or cookie; stop at once on HTTP 429, any 5xx or any status other than 200,
  nothing retried. A ledger line per request (time, URL, status, bytes).
- **Estimate:** 14 requests, about 15 to 30 seconds at the 1-second pace. A record is about 4 KB (Ham and Kingston's
  2-incident history is 8.6 KB), so even 100 incidents at a site is about 0.4 MB. Well inside 40 requests and 20 MB.
- **If it stops:** no body is saved and none is read; the stop is reported, and a second attempt needs Ethan's yes.
- **Blind:** the fetch prints only counts of requests and bytes and the hash. Nothing from the histories is looked at
  before the hash is committed. Nobody runs the advisory finder's `--ea-history` before the score; if it is run, that
  is recorded here as seen.
- No Open-Meteo call is made, and no satellite request.

## Running

After Ethan approves, from a `git archive` of the harness commit, in a private folder:

1. **Fetch once** (online): `run.sh fetch <out> <features file> 41f234d3…` writes `incidents.json`,
   `incidents.sha256` and the ledger.
2. **Commit the incidents hash** to this file's run log, before scoring.
3. **Score** (offline): `run.sh score <out> <features file> 41f234d3… <incidents SHA-256>`, under the group's
   heavy-run lock (`heavy-run.lock` in the shared notes folder). The script refuses while the lock is held, takes it
   with noclobber and deletes it when it ends. It runs under `scripts/lake_distance_eval/run_offline.py`, so every
   outgoing connection is refused and counted; it must print "network attempts: 0". It writes `score.json`.
   Before it starts, by the group's rules: no other evaluation, training, build or test running (`pgrep -fl`, never
   `pkill`), and at least 35% memory free.
4. The order inside the score: stop rules, then the gate, then the scores.

## Harness choices

Fixed in `scripts/lake_algae_incident_eval/algae_incidents.py` before any history was fetched:
- #377's protocol module is loaded by its path under its own name, so its `one_per_date`, hashing and label function
  are the ones used, and no other `protocol` module can stand in.
- Pairing uses `pandas.merge_asof` backwards by site with a 3-day tolerance, both ends counted.
- Ties in S count a half (ranks from `scipy.stats.rankdata`, average method).
- A bootstrap draw sums U and pairs over the drawn water bodies, repeats included.
- A rotation that leaves a stratum without an incident day or a control day with a reading drops that stratum from that
  placebo S.
- The anomaly's reference uses scenes, not days, so a scene is not counted several times.
- Percentiles are numpy's default (linear).

## What will be reported

Whatever the verdict:
- the fetch: requests, bytes, statuses, time, the incidents hash, the ledger;
- incidents per site, code and year; open-ended ones; malformed ones;
- the harmful-algae incidents at the test sites: id, sites, start, end;
- days by label (incident, excluded, control), with and without a reading; control days with an incident at another
  site of the same lake;
- the gate counts;
- S, its interval and label, with d, B and H; the per-stratum table (incident days, control days, AUC);
- each condition with its figures: the 200 placebo values (lowest, median, 95th percentile, 190th, highest), the
  anomaly S and interval, the leave-one-lake-out values, the two group labels;
- as description: S with 0-day and 7-day pairing, and S without Frensham 2026;
- the features and incidents hashes, the harness commit and the network-attempt count.

## Seen before writing

- **#377 in full**, including its results: NDCI against the EA's checks failed for "algae seen" (AUC 0.60); 20
  objectionable checks (AUC 0.81, description); AUC by water body against the checks (Frensham 0.92, the Serpentine
  0.73, Windermere 0.64, Cotswold 0.42, Colwick 0.40, Rutland Water 0.35, Coniston Water 0.14, Derwent Water none).
  Its sizes table. Not its features file: only the file's size and name were listed, and its hash is checked in code.
- **The advisory finder's EA fixtures** (PR #379, branch `proto/advisory-finder`, saved 26 October 2026 at 18:37 UTC):
  - the open list: 7 open incidents. **Frensham Great Pond, harmful algae (014), start 19 June 2026 14:28, no end.**
    The other six are not lakes: Blyth South Beach (oil or fuel), Plymouth Hoe West and East, Ryde, Perranuthnoe and
    Portreath (sewage). So on 26 October no other test site had an open incident.
  - Ham and Kingston's history (a river, not in this test): harmful algae from 17 August 2026, ended 19 October 2026;
    oil or fuel from 10 to 11 September 2026. Its records carry `replaces` and `som_recordDateTime`.
- **Lines of the advisory finder's notes** (`docs/ADVISORY-FINDER-2026-10.md` on that branch, found by a text search):
  the EA panel for Frensham said bathing was not advised because of harmful algae; a Waverley Borough Council page
  about Frensham is dated 22 August 2025; a GOV.UK news item of 2018 about blue-green algae at four Lake District
  locations (outside this test's years); its `--ea-history` option has never been run live.
- **The API reference** above, and one web search for it.
- No incident history for any test site, from any source. No reading from the features file. No score of any kind.

## Approval

Ethan approved this statement on 27 October 2026 at 00:36 UTC, in the coordinating session, in his words: "I approve the #386 and #385 statements as written. Run #386 then #385 under their stated protocols and caps, record the approval and results in each PR, and draft the 2027 forward statement for the third question without running anything." He had the statement at 735e882. Codex had reviewed it on 26 October as a bounded exploratory question and kept it unrun during the product window. Nothing above this section changes after approval. Nothing had been fetched: no incident history, and the features file was not opened. It runs after #386, as he asked.

## Run log, after approval

- **27 October 2026, 01:03 UTC: the one fetch**, from a `git archive` of bac9c34 (the approved statement): 14 sites,
  14 requests, 65,422 bytes, no stop. **Incidents file SHA-256:
  `68ca1552bea27546ad87256043e719e0c95cc223c718661b5548822a1b458d1b`**, committed here before scoring. Nothing in the
  histories was read beyond the counts the fetch prints. The features file is #377's
  (`41f234d3a953df246306aa7785978e7c3d76f82ed1765e5518923633c50b5d0e`).

---

## Results

Added 27 October 2026 after the one scoring run, from the archive of bac9c34, under the heavy-run lock, **network
attempts: 0**; both hashes matched.

**Verdict: too few to judge.** The gate needs incidents at 4 or more water bodies; there were 3 (Colwick Country Park
West Lake, Frensham Great Pond, Windermere). Everything below is description and decides nothing.

- **Incidents:** 13 harmful-algae incidents (type 014) in the histories of the 14 sites, 9 of them on days with
  a satellite reading; 415 incident days, 106 with a reading; 14,579 control days, 4,277 with a reading. One open
  incident: Frensham Great Pond, since 19 June 2026.
- **Gate:** 106 incident days with a reading (30 needed: met); 9 incidents (5: met); 3 water bodies (4: **not met**);
  7 lake-seasons (6: met).
- **Primary (description):** stratified S = 0.64, 95% interval 0.33 to 0.73, label "Too uncertain".
- **Shift placebo: not beaten.** Real S 0.64 against a 95th percentile of 0.72; 35 of 200 shifted patterns scored at
  or above it.
- **Seasonal anomaly:** S = 0.48 (interval 0.23 to 0.53): no signal once the usual time-of-year pattern is removed.
- **By group:** Lake District S 0.33 ("Possible harm", 2 lake-seasons); lowland S 0.71 ("Too uncertain", 5).
- **Leave one water body out:** Colwick 0.65, Frensham 0.34, Windermere 0.71.

**What it means:** too few lakes have had harmful-algae incidents to judge. On what there is, the reading does not
beat moving the incident around the season, and nothing remains once the usual seasonal rise is taken out. Nothing on
the site changes. Full tables: `docs/LAKE-ALGAE-INCIDENT-TEST-2026-10-score.json`.
