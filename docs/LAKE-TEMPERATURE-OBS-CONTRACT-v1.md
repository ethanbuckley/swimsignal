# Measured lake temperatures: the observation contract, version 1

Written 30 October 2026, register row **5 / LAKE-TEMP**, route "public research observations"
(`docs/RESEARCH-WORKFLOW.md`: "public historical temperature observations can precede a forecast"). Produced and
checked by `scripts/export_lake_temperature_obs.py` from the lake temperature test's (#419) cached EA readings; file
`data/research/lake_temperature_obs.v1.json` (about 75 KB gzipped). The product chat owns where and how it is shown.

## What it may and may not say

- **May say:** what water temperatures the Environment Agency measured in a lake, at named sampling points, on dated
  visits between May and September, 2000 to 2026; the typical (median) and middle-half range by month; how many
  readings stand behind each figure; how far a swim spot is from the nearest sampling point.
- **May not say:** today's temperature (no listed lake has an open live sensor: `docs/LAKE-TEMPERATURE-SENSORS-2026-10.md`);
  the temperature at the swim entry; a forecast (the lake temperature model failed its test, #419); anything about
  safety. A month with few readings must show its count.
- `claim.public_wording` goes beside the figures. The months are May to September only, because only those were
  fetched; the page must not suggest winter values.

## Fields

| Field | Meaning |
|---|---|
| `schema`, `version`, `generated_at`, `period` | `"swimsignal.lake-temperature-obs"`, `"1.0.0"`, export time, first and last reading and the months covered |
| `method` | source (determinand 0076), how points were matched to lakes (#419's rows), `spot_link_m` (150), code SHA-256 |
| `sources`, `attribution` | input files and SHA-256; EA (OGL v3), WFD outlines (OGL v3), HydroLAKES depths (CC BY 4.0) |
| `claim` | `public_wording`, `not_claimed` |
| `lakes` | one per WFD lake water body with readings: `wb_id`, `name`, `area_km2`, `depth_m`, `reservoir`, `points`, `spots`, `summary`, `monthly`, `readings` |
| `points` | sampling points: `point` (the Archive's id), `label`, `lat`, `lon`, `readings`, `last` |
| `spots` | listed SwimSignal spots in or within 150 m of the lake: `spot_id`, `name`, `outside_lake_m` (0 when inside), `nearest_point_m` |
| `summary` | readings, first and last date, years with a reading |
| `monthly` | May to September: `n`, `median`, `p25`, `p75` (quartiles only with 4 or more readings) |
| `readings` | every reading as columns in date order: `date`, `temp` (°C, one decimal), `point` (index into `points`) |
| `coverage` | lakes, readings, readings set aside for having no WFD lake id, points, lakes with a linked spot, spots linked |

As exported on 30 October 2026: 210 lakes, 11,502 readings at 368 points; 15 lakes linked to 20 listed spots
(Windermere's two basins, Coniston Water, Derwent Water, Rutland Water, Frensham Great Pond, Bassenthwaite, Loweswater,
Grasmere, Rydal Water, Elter Water, Wast Water, Brothers Water, Crummock Water, Hatch Mere).

## Version 1.1 (31 October 2026): additive, at the product owner's request

- `claim.page_wording`: the claim for a page listing many lakes (`public_wording` says "this lake").
- `method.public_sentence`: one plain sentence on how each monthly figure is made.
- `points[].first`: each sampling point's first reading date, beside `last`.
- `summary.years_list`: the years with a reading (`summary.years` stays the count).
