# Five ambitious research directions: scoping records

Written 1 November 2026. **Scoping only.** No data was fetched, no model was fitted or scored, and no outcome was
read for this record. No evaluation window, frozen file or live setting changed. Nothing was sent, bought or opened.

An outside review of 1 November 2026 proposed five research directions and a table of model work. Ethan asked to do
all of it. The review itself is not in the repository; its five ideas and its table are restated below as they were
relayed to this session. Each idea gets a scoping record in the [research workflow](RESEARCH-WORKFLOW.md)'s format:
a bounded first deliverable, a budget, a milestone and a stop rule. None is a licence to build the whole idea.

Checked against main `4deeedd3` (1 Nov 2026), the open PRs #383 and #584-#587, and the linked session building a
catchment workspace prototype (branch `claude/lab-catchment-workspace-aa0aad`, no PR yet). Each finding is marked
**established** (read in a named file, PR or command output) or **inferred** (a reasoned reading that a named check
would settle).

## Summary

| ID | Idea | Smallest useful first deliverable | Milestone | Stage |
|---|---|---|---|---|
| CATCH-SIM | Catchment experiment simulator | Offline rain and "remove an overflow" sensitivity for two spots, inside the catchment workspace | Record by **15 Dec 2026** | development (exploration) |
| SOURCE-ID | Pollution source investigation | An "explanations table" for high samples at 5 bathing waters, and the measurements that would separate them | Record by **31 Jan 2027** | development (exploration) |
| LAKE-ECO | Lake ecosystem observatory | A coverage inventory of measured nutrients, oxygen, temperature and chlorophyll at the satellite lakes | Inventory by **31 Jan 2027**; model rule fixed before **1 May 2027** | development (exploration) |
| RESTORE | "Did the restoration work?" | Weather-adjusted observed vs expected spill days at overflows with a cited completion date | Starts after option B's read (**on/after 2 Dec 2026**); record by **31 Jan 2027** | waiting (on the option B read) |
| BENCH | Open water-quality benchmark | One frozen task (inland bathing-water E. coli, 2023-26) with a licence manifest, three baselines and a scoring script | Release candidate by **28 Feb 2027** | development |

Owner of all five: Ethan, with Claude sessions doing the work. Every record below lists what needs his decision or an
outside contact. None of those has been acted on.

## Rules that apply to all five

- Reused 2023-26 outcomes are development data. An analysis of them is exploratory and says so.
- The 2027 primary evaluation (`docs/PREREGISTRATION-2027.md`) and every active window keep their rules: REGIONAL
  (read 28 Nov), lead calibration B (16 Nov), ensemble rain (21 Nov), live-status shadow (23 Nov), A8 (25 Nov),
  upgraded-overflows option B (on/after 2 Dec), winter recalibration (fit on/after 10 Dec). Nothing here reads their
  outcomes early or changes their inputs.
- Scratch `DIPCAST_ROOT`, `DIPCAST_STATE` and output directories before importing build code. Fingerprint shared
  caches before and after. No Open-Meteo calls unless a record says so; every EA fetch has a written request cap.
- A satellite index is not a toxin measurement. Missing imagery is not a negative observation. An E. coli count does
  not identify its source.

---

## 1. CATCH-SIM: catchment experiment simulator

**The idea.** Let a reader change rainfall, overflow upgrades and restoration, and see the effect on spills and E. coli
risk at a spot, with uncertainty and explicit assumptions.

**What already exists (established).**
- The production chain: the spill model (`data/processed/spill_model.pkl`), transport to the spot
  (`transport.upstream_overflows`: distance, travel time, decay, dilution, weight) and the E. coli model.
- Catchment replay (#390, `?replay=1`, `docs/CATCHMENT-REPLAY-2026-10.md`): the last 48 hours upstream as issued.
- Evidence map (`?evidence=1`, `docs/EVIDENCE-MAP-2026-10.md`): where the forecast has evidence upstream.
- Pollution paths exhibit (open draft #586, `docs/POLLUTION-PATHS-EXHIBIT-2026-11.md`): every overflow's path,
  travel time and weight for 81 spots, with a clock slider. Prototype only.
- A linked session is building a "connected catchment workspace" prototype now. No PR or note yet.
- PR #298 found the spill model's response to the overflow covariate `lta_spills` is "jagged and not monotone"
  (Middleton: 0 gives 8.1 expected spill days a year, 2 gives 3.3, 10 gives 12.2). So an "upgrade" scenario made by
  writing a smaller `lta_spills` would be an artefact of the trees, not a forecast.
- No model of wetlands, storage tanks or river restoration exists anywhere in the code (grep for "restoration",
  "wetland", "scenario": none in `src/`).

**The claim it could support.** "Under the production model as fitted, if the rain over these overflows were X, or if
this overflow did not discharge, the model's expected spill days and level at this spot would be Y, within this range."
That is a sensitivity of the model, labelled as such.

**The claim it must not make.** That a real upgrade or restoration scheme will cut spills or E. coli by a stated amount.
That the model is valid outside the rain it was trained on. Any effect of a wetland, tank or tree planting: there is no
mechanism for one in the model.

**Data and licence.** All inputs are already in the build: EA EDM and annual returns (OGL v3), company event layers
(CC BY 4.0), ERA5-Land archive rain via the existing caches (Open-Meteo: CC BY 4.0 data, free API non-commercial).
No new source.

**Smallest useful first deliverable.** An offline record and export for two spots with very different catchments
(Wharfe at Cromwheel, Ilkley; Windermere at Waterhead):
1. Rain scaled ×0.5 to ×1.5 on the 2024-25 archive, and three replayed historical storms.
2. "Remove one overflow": drop it from the upstream list. This is defined by the transport rule, not by editing a
   covariate.
3. Uncertainty from the model's own year-to-year spread and its calibration error at each level, stated beside the
   number.
4. A check of monotonicity: the share of overflows whose expected spill days fall when rain falls.

Completion check: the export reproduces the published level for the unchanged scenario at both spots, and the record
states the monotonicity share. It becomes a mode of the catchment workspace, not a second page.

**Budget and caps.** Offline. Cached rain only, zero Open-Meteo calls, zero EA requests. At most 2 CPU-hours.

**Owner.** Ethan; the catchment-workspace session is the natural place for the view.

**Milestone.** Record by **15 Dec 2026**.

**Stop or narrow if.** More than 10% of overflows at the two spots respond non-monotonically to scaled rain. Then rain
scenarios are artefacts too: keep "remove an overflow" only and record why.

**Needs Ethan.**
- Whether a scenario view is shown publicly at all, or stays in the Lab with a "model sensitivity, not a prediction"
  label.
- Whether "remove an overflow" may name a company's overflow on a public page.

---

## 2. SOURCE-ID: pollution source investigation

**The idea.** For high E. coli, compare sewage, agricultural runoff and other explanations, and name the measurements
needed to tell them apart.

**What already exists (established).**
- Farm pressure test (#332, `docs/FARM-PRESSURE-TEST-2026-10.md`): the EA water body's rural-pollution flag as an
  E. coli input. "fails conditions 1, 2, 5 and 6. Nothing is adopted."
- The water body's reasons for not reaching good status, shown on spot pages (#256, `data/raw/rnags.json`, OGL v3).
- Dry-weather spills (#346): top dry spillers are chronic groundwater sites.
- Weather die-off and urban dilution tests failed (register, "Variants with meaningful negative evidence").
- Sonde signal (#403): 71 matched river rows at 4 sites against a gate of 150; unrun.
- EA sondes: 78 live ammonium and 191 live dissolved-oxygen series on 25 Oct; 12 live ammonium stations within 5 km
  of a listed spot (`data/research/source_inventory.v1.json`, `ea-hydrology-sondes`).
- Wessex Water river samples, CC BY 4.0: E. coli, enterococci, ammonia and dissolved oxygen at 99 river positions.
- No microbial source tracking anywhere in the repository (grep for "HF183", "bacteroid", "microbial source": none).

**Inferred.** A culture count of E. coli cannot tell human from animal sources. Separating them needs a human-specific
marker (for example HF183) or a ruminant marker, tested on the same sample. This is general method knowledge, not
checked in this repository.

**The claim it could support.** "At this site, of N samples over 900, A followed a recorded spill upstream within the
transport window, B had no recorded spill while the feed was polled, and C fell in poll gaps. These are the other
explanations that remain open, and these measurements would separate them."

**The claim it must not make.** That a sample was caused by sewage or by farming. A percentage apportionment between
sources. Blame of a named farm, landowner or company. "No spill recorded" as proof that sewage was absent.

**Data and licence.** EA bathing-water samples and the Water Quality Archive (OGL v3), EA EDM (OGL v3), company layers
(CC BY 4.0), `rnags.json` (OGL v3), EA sondes (OGL v3), Wessex samples (CC BY 4.0). Not usable in anything
published: the EA consents register (internal use only), Southern and Yorkshire Water event histories (no licence).

**Smallest useful first deliverable.** An explanations table for the five bathing waters with the most samples over
900 in 2023-26 (seen data, exploratory). Per high sample: recorded spill upstream in the transport window (yes, no,
not polled), rain in 48 h, dry-weather spill history, water-body pressures, and sonde ammonium where a station
exists. Then a section naming, per site, which measurement would separate the open explanations: paired
upstream/downstream samples, a human marker, ammonium at the time of the sample, or timing against spill ends.

Completion check: every high sample at the five sites is in the table with no blank cell; "not known" is a value.

**Budget and caps.** Offline from committed files and caches, plus at most 50 EA requests for sonde readings, paced.
Zero Open-Meteo calls.

**Owner.** Ethan.

**Milestone.** Record by **31 Jan 2027**.

**Stop if.** Fewer than 20 high samples across the five sites have a known spill status. Then the table is too thin to
compare explanations: publish the measurement plan alone.

**Needs Ethan or an outside contact.**
- Any marker sampling is a lab purchase and needs a partner who samples anyway (AAFAF at Waterhead, Ilkley Clean
  River). Both are outside contacts.
- Public wording about farming as a possible source.

---

## 3. LAKE-ECO: lake ecosystem observatory

**The idea.** Nutrients, temperature, satellite colour and verified field observations together, with chlorophyll or
oxygen-stress models only where suitable measurements exist.

**What already exists (established).**
- SAT-OBS: `/lakes.html`, 55 sites, 2,097 index readings and 1,774 dated lab values; a weekly five-site pilot from
  31 Oct (#537); Sentinel-2 imagery (issue #550).
- Lake temperature observations: `/lake-temperatures.html`, 210 lakes, 11,502 EA readings (#529).
- #386: NDCI against lab chlorophyll, ρ 0.502 [0.2997, 0.667]; "promising, not validated".
- Open draft #586: with each month's mean removed, ρ 0.245 (0.071 to 0.405); direction of change from the index was
  not better than a calendar guess.
- WET partner samples at Waterhead (`/waterhead.html`, #561) and the partner-samples contract drafts (#571-#575).
- Reviewed official harmful-algae notices on spot pages (#379).
- UKCEH lake buoys: reuse of live data "Unknown"; status `needs_permission` in the source inventory.
- No dissolved-oxygen profile at any lake in the project's data (inferred from the inventory: the 191 DO series are
  EA sondes, listed as river series; not counted by water body here).

**The claim it could support.** "At this lake, these were the measured nutrient, temperature, oxygen and chlorophyll
values, on these dates, from these sources, beside the satellite index on its own dates."

**The claim it must not make.** A lake health score. A bloom or toxin forecast. Oxygen stress at a lake with no
oxygen measurements at depth. Satellite index units as chlorophyll concentration. A swimmer's photo as a verified
observation without the partner contract's moderation.

**Data and licence.** EA Water Quality Archive (OGL v3) for nutrients, oxygen and chlorophyll; Sentinel-2 via the
existing pipeline (Copernicus open licence); EA lake temperatures (OGL v3); partner samples under the partner contract.
UKCEH buoys need a licence answer before any use.

**Smallest useful first deliverable.** A coverage inventory, not a model. For the 55 satellite sites and the 20 lake
spots: which have total phosphorus, nitrogen, dissolved oxygen, temperature and lab chlorophyll, by year and month,
2015-2026. Written as a minor version of the lake-observations contract. It then fixes, before any model is tried, the
rule a lake must meet to get one (for example, at least monthly paired nutrient and chlorophyll samples in three
seasons). The rule is written before 2027 data arrive, so 2027 can judge it.

Completion check: the inventory's counts match a recount from the raw responses, and the eligibility rule is committed
with a date.

**Budget and caps.** At most 200 EA Water Quality Archive requests, one at a time with a pause. No imagery download
(reuse the existing scenes). Zero Open-Meteo calls.

**Owner.** Ethan; SAT-OBS's session is the natural owner of the contract change.

**Milestone.** Inventory by **31 Jan 2027**; eligibility rule committed before **1 May 2027**.

**Stop if.** Fewer than 5 lakes meet the rule. Then no chlorophyll or oxygen model: the observatory stays observations
only, and the record says which lakes fall short and by what.

**Needs Ethan or an outside contact.**
- The UKCEH licence enquiry (already his, per the AI programme doc).
- Whether swimmer field observations are collected for lakes at all, and under which moderation.

---

## 4. RESTORE: "did the restoration work?"

**The idea.** Weather-adjusted before/after comparisons of interventions, starting from the upgraded-overflows work.

**What already exists (established).**
- #298 (`docs/UPGRADED-OVERFLOWS-2026-10.md`): Ilkley's six named upgraded overflows showed 1 spill day in April to
  August 2026 against 23.0 expected by the production model on archive rain; the ten others showed 49 against 68.7.
  This is already a weather-adjusted before/after comparison, for one scheme.
- Option B (`docs/UPGRADED-OVERFLOWS-TEST-B-2026-10.md`, #325): each overflow's own record since an upgrade. Frozen;
  run on or after **2 Dec 2026**. Ilkley is excluded from its deciding scores because its 2026 outcome is published.
- `data/raw/overflow_upgrades.csv`: 20 rows, 2 marked upgraded. Page notes only; the model never reads it.
- WINEP storm-overflow deadlines in `data/processed/winep_overflow_actions.parquet`, shown on overflow records.
- The source inventory ranks the EA annual-return improvement columns `ready_to_integrate`. "No source gives an actual
  completion date per overflow" (`docs/OVERFLOW-DATA-SOURCES-2026-10.md`).
- Monitor anomalies (#382) can flag a monitor quiet through storms. A quiet monitor is not proof of an upgrade.
- No record of a non-overflow intervention (wetland, river restoration) with a date and a measured outcome.

**The claim it could support.** "At these overflows, after the cited date, spill days were N against M expected given
the actual weather, with this interval, and monitor uptime was U. Nearby unchanged overflows moved by this much."

**The claim it must not make.** That a river or bathing water is cleaner because of a scheme, without samples before
and after. A causal effect where the completion date is not cited. Any result from the Ilkley six as a confirmation:
they were seen before any test was designed. Any reading that pre-empts option B.

**Data and licence.** EA EDM start/stop and annual returns (OGL v3), company layers (CC BY 4.0), ERA5-Land archive rain
in the caches. Southern and Yorkshire Water event histories carry no licence: not for publication.

**Smallest useful first deliverable.** After option B is read, a descriptive file for every overflow with a cited
completion date (the 2 upgraded rows plus annual-return "improvement completed" rows once that data PR lands):
observed against expected spill days by month, before and after, with a Poisson interval, monitor uptime beside it,
and the same numbers for unchanged overflows on the same river. Ilkley is labelled "seen".

Completion check: each row names its cited date and source; rows without one are listed apart, not dropped.

**Budget and caps.** Offline from committed files and caches. Zero Open-Meteo calls. EA requests only for annual-return
files already listed in the source inventory, at most 20.

**Owner.** Ethan.

**Milestone.** Start on or after **2 Dec 2026**, once option B is read. Record by **31 Jan 2027**. Any page line
decided before the 2027 freeze (**30 Apr 2027**).

**Stop if.** Fewer than 10 overflows have a cited completion date with 6 months after it and monitor uptime of 90% or
more. Then it stays a set of case notes, with no pooled figure.

**Needs Ethan or an outside contact.**
- Completion dates confirmed by a company or Ilkley Clean River: an outside contact.
- Whether a per-overflow before/after figure names a company on a public page.

---

## 5. BENCH: open water-quality benchmark

**The idea.** Reproducible datasets, simple baselines and transparent comparisons that outsiders can contribute to.

**What already exists (established).**
- Versioned public research files with contracts in `data/research/`: E. coli evidence (2,265 EA samples at 38 bathing
  waters), spill durations (802,781 spills 2024-25), lake observations, lake temperatures, sampling planner, research
  catalogue and model scorecard (`/models.html`, #570).
- Code is MIT; data licences per file in `LICENSE-DATA.md` (ODbL kept apart in `spots-osm.csv`).
- The 2027 primary's site list and climatology (`data/eval2027/`), and the issued-forecast history kept by each build.

**Licences (established, from the source inventory and `LICENSE-DATA.md`).**
- Publishable with attribution: EA data (OGL v3), Northumbrian, Wessex, United Utilities and stream layers (CC BY 4.0),
  HydroLAKES (CC BY 4.0), EPA Ireland (CC BY 4.0).
- Publishable with conditions: Met Office radar (CC BY-SA 4.0: derivatives share alike); OpenStreetMap (ODbL: keep
  apart).
- Not publishable: the EA consents register ("you must not publish the Information in any way"); Southern and
  Yorkshire Water event histories (none stated); Dŵr Cymru history (personal use only); NI Water EDM; SEPA sample
  results; the Water UK plan.
- Unsettled: Thames discharge API (unnamed licence with CC BY wording); Open-Meteo-derived rain (CC BY 4.0 data, but
  the free API is non-commercial, so redistributing fetched values needs a check).

**The claim it could support.** "This frozen dataset and task, scored by this published script, gives these baseline
scores; anyone can reproduce them and submit another model the same way."

**The claim it must not make.** That the task represents UK water quality in general. That a better score means a
model is fit to guide swimming. Any release of 2027 outcomes before the 2027 primary is read.

**Smallest useful first deliverable.** One task: E. coli over 900 at the 38 inland bathing waters, May-September
2023-26, all already published.
- Inputs only from publishable sources, each column with a licence line in a manifest.
- Three baselines: month-of-year rate, last sample, and the production model's published hindcast.
- A scoring script with grouped-by-site intervals, and a data card stating seen data, gaps and limits.

Completion check: a fresh clone reproduces the three baseline scores to the stated decimals with one command.

**Budget and caps.** Offline. Zero Open-Meteo calls if the rain column is dropped or cleared; zero EA requests (all
from committed files).

**Owner.** Ethan.

**Milestone.** Release candidate by **28 Feb 2027**.

**Stop if.** A required input column has an unresolved licence. Drop the column; if the task is then meaningless,
publish the licence manifest alone as the deliverable.

**Needs Ethan or an outside contact.**
- The dataset's licence (CC BY 4.0 would match most inputs).
- Whether outside submissions are accepted, and who reviews them.
- A DOI archive (for example Zenodo) is a new account: his.
- Whether Open-Meteo rain values may be redistributed: a question to Open-Meteo, an outside contact.

---

## 6. The model-strengthening table, checked against the register

"Under way" means a record with a PR and a date already exists. "New" is what no record covers yet.

| Review item | Under way (record, PR, next date) | New |
|---|---|---|
| Spill: regional | REGIONAL, #490/#510/#533; shadow 31 Oct-27 Nov, **read 28 Nov 2026** | Nothing until the read |
| Spill: live-status | Live-status shadow, #254/#262; **read on/after 23 Nov 2026** | Nothing until the read |
| Spill: calibration comparisons | Lead calibration B (#252, **read 16 Nov**); A8 (#333, **read 25 Nov**); winter recalibration (#374, fit on/after **10 Dec**, judged 14 Dec-7 Mar 2027); nine-company v2 (#357, closed as a test, feeds REGIONAL) | Nothing until the reads |
| Spill: missing-feed fallback | The live-status shadow scores its fallback as part of the candidate: "The fallback rule is part of the candidate." REGIONAL falls back to production at UU. Missing event ends (#384), re-measure **on/after 9 Nov**. Live status wording on every page (evidence map PR) | Inferred, not checked: no record scores the **production** forecast on builds where a company feed was stale against builds where it was fresh. A small offline check after the 23 Nov read |
| Lake bacteria: uncertainty | LAKE-CONC: lake spread (#526); open #584 passes all three stated conditions on 2012-22 (central 80% range holds 78.9%) | Nothing beyond #584/#585 |
| Lake bacteria: unsampled lakes | Open #584 (supplementary: 75.6% inside at a lake with no samples of its own) and #585 ("average lake" wording) | A **stated** held-out-lake check, since #584's figure is supplementary. It needs samples at lakes with none: the partner programme or 2027 |
| Lake bacteria: prospective checks | #584's next step: shadow log at lake spots, 2027 lake samples as the prospective check | Nothing new |
| Satellite: suspicious readings | Lake-observations contract: exclusion reasons (`invalid_band_values`, `snow_or_ice_in_core`, `sun_too_low`, `core_not_classed_water`) and same-date pair differences (#468, #537) | A review flag for a reading far outside its lake's own range. Small; SAT-OBS's |
| Satellite: shoreline effects | #377 used a 20 m shore margin and core pixels; small ponds lacked core pixels | A measured sensitivity: index against distance from shore, rings at one or two lakes. Small; SAT-OBS's |
| Satellite: change beyond seasonality | Open #586: ρ 0.245 with month removed; direction not better than calendar | Nothing until #586 is reviewed |
| Satellite: matched field samples | #386; draft 2027 shallow-lake protocol, margins before **1 May 2027**; #586: shallow pairs 8-34 a summer against a draft minimum of 30 | Nothing new; partner samples could add pairs |
| Duration: polling gaps | #539 replay at the live poll timetable; live check (`docs/SPILL-DURATION-LIVE-CHECK-2026-11.md`); next **1 Dec 2026**, refit ~**28 Dec 2026** | Nothing new |
| Duration: recording differences | Per-company curves; live vs EDM labels (#253: feed matches EA 281/342); `scripts/compare_event_sources.py` | Inferred: no record compares the **same spill's** length between the live feed and the EA annual file. Possible once the 2026 EA file covers the poll period |
| Transport: arrival-time ranges vs measured events | Transport fit (#248) chose 0.2 m/s on E. coli samples and says it "should not be read as a measured speed". River rises (open #383) times gauge rises, which are flood waves, not water | **New.** Compare the model's arrival window with measured downstream signals after timed spills: EA ammonium sondes below overflows (12 live stations within 5 km of a spot, 8 on becks around Windermere). Offline first, at most 100 EA requests. Not scoped as its own record here; a candidate for DURATION or the transport owner |

## 7. Decisions and contacts that are Ethan's

Nothing in this list has been done.

1. CATCH-SIM: public or Lab-only scenario view; naming overflows in scenarios.
2. SOURCE-ID: any marker sampling (purchase, partner contact); wording about farming.
3. LAKE-ECO: the UKCEH licence enquiry; whether to collect swimmer lake observations.
4. RESTORE: completion dates from companies or Ilkley Clean River; naming companies in before/after figures.
5. BENCH: the dataset licence; accepting outside submissions; a DOI account; asking Open-Meteo about redistribution.

## 8. What this record does not do

- It does not rank the five against current work. The active reads in November and December come first.
- It does not test the review's ideas. Each first deliverable is exploration or data work, with a stop rule.
- It did not re-read the outside review itself; its text is not in the repository.
