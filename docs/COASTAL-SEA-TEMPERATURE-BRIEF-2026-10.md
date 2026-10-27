# Coastal sea temperature: brief before any build (27 October 2026)

This is research only. Nothing is built, nothing on the site changes, and no build makes a new request.

**Where it comes from.** The expansion plan Ethan approved on 27 Oct puts water temperature first. Rivers passed and are built (#418, held until the May re-check), and lakes failed twice (#414, #419). The plan's remaining piece is the coast: "Coastal spots take Open-Meteo Marine sea temperature directly, labelled as modelled". On the site that means the English coastal directory on the coverage page: 426 coastal and estuary bathing waters in `data/coastal.json`.

**In short: it does not fit the free budget as it stands, and one measurement decides whether a reduced version can.**
- Each beach costs at least one Open-Meteo call per refresh.
- The site has about 127 calls a day spare under its own 9,000 ration (#416). That is a hard limit: no paid plan yet.

## What was checked, 27 Oct 2026

| Question | Answer | How it was established |
|---|---|---|
| Does the Marine API give sea temperature at English beaches? | Yes: `sea_surface_temperature`, °C, as `current` or `hourly`. | Calls: Ainsdale returned 11.7 °C; Spittal and Seaton Carew together returned 11.8 and 12.1 °C. |
| Which model, how coarse, how often? | MeteoFrance SST, global, **0.08° (about 8 km)**, 6-hourly values, **updated every 24 h**. Generated using E.U. Copernicus Marine Service information (DOIs 10.48670/moi-00017 and moi-00016). | [Marine API docs](https://open-meteo.com/en/docs/marine-weather-api), read 27 Oct. |
| Terms | Free API, **non-commercial only**, CC BY 4.0 data with attribution to Open-Meteo and the source. A commercial launch needs a paid plan. | [Terms](https://open-meteo.com/en/terms) and [pricing](https://open-meteo.com/en/pricing), read 27 Oct (#416). |
| How is a multi-location request counted? | Each location costs **at least 1 call**; in the doc's words, multiple locations in one request do "not make them count as one location". Weight per location: max(1, V/10 × max(1, D/14)). One variable over a few days is 1. | Open-Meteo's own [rate-limiting doc](https://github.com/open-meteo/open-meteo/blob/main/docs/api-rate-limiting.md), read 27 Oct; the same rule as `rainfall.call_weight`. |
| Largest batch per request on the free API | **Not stated.** The doc gives 10,000 locations per request for the customer API only. | Same doc. |
| Can the charge be read from the response? | The doc says responses carry `X-RateLimit-Cost`. **The Marine endpoint returned no rate-limit headers** to a 2-location request on 27 Oct. | `curl -D -` on that request. |
| Official coordinates for each site? | **Yes, all 426.** The EA bathing-water API gives each site's `samplingPoint` with `lat` and `long`. No Water Quality Archive sample point is needed, or substituted. | `environment.data.gov.uk/doc/bathing-water.json`, 2 pages, 464 items, from this Mac. GitHub's runners are refused by this service, so the coordinates would be read once off CI and committed, as `coastal_catalogue.json` is. |
| Where does the API's value come from for a beach? | **The nearest sea cell with data, not the cell holding the beach.** Spittal (55.757, −1.989) was answered from 55.875, −1.875, about 15 km away. Seaton Carew (54.665, −1.186) was answered from 54.792, −1.125, about 14 km away. The grid is 1/12° (cell centres at (k + 0.5)/12), matching 0.08°. | The 2-location call. Two sites only: how far the cells are across all 426 is **not known**. |

## Cost against the budget

- **All 426 sites at one location-weighted call each:** at least 426 calls a refresh, however few HTTP requests carry them. A daily refresh is 426 a day, more than three times the 127 spare.
- **De-duplicated by the cell the API actually answers from:** unknown. Many neighbouring beaches probably share a sea cell (inferred), but the shared cells can only be found by asking each beach once. An earlier count of 212 cells assumed each beach's own cell. It is wrong, because the API answers from a different, offshore cell.
- **What would fit, if the measurement allows it:**
  1. **Distinct sea cells at or under about 120:** refresh once a day, booked in the ledger as its own user, on spare calls only.
  2. **More than about 120:** rotate. Ask about 120 cells a day, so each beach's value is 1 to N days old, always shown with its date. The field itself updates only once a day.
  3. **Neither acceptable:** leave it until a paid plan exists.
- **Clash with the rain-ensemble study (D4).** The ensemble also runs on spare calls. A new spare-call user could starve it and change its window. The window's dates are recorded in `docs/ENSEMBLE-RAIN-TEST-2026-11.md`: target days 23 Oct to 19 Nov 2026, read on or after 21 Nov. Its read fetches ERA5-Land for the window's days, about one call per cell. **If its minimum data falls short, the window extends to 3 Dec, read on or after 5 Dec.** So any build makes no sea-temperature request before **22 November 2026**, or before **6 December 2026** if D4 extends. In either case that is after the D4 read.

## Accuracy limits, to state wherever a value is shown

- **Modelled, not measured.** A forecast-model field, not a thermometer at the beach.
- **Coarse.** One value covers about 8 × 8 km of sea.
- **Offshore.** The value is from the nearest sea cell with data. In the two cases checked, that was about 14 to 15 km from the beach's sampling point. Shallow water, estuaries, harbours and sunny days near the shore can differ from it by several degrees (inferred; not measured here).
- **Estuaries.** Of the 426 sites, the transitional (estuary) waters are the least likely to match an open-sea cell (inferred).
- **Not safety advice.** It would be a note about the sea nearby, beside the EA's own information. It is not a reading of the water at a beach, or a statement that it is safe to swim.

## The next step, and what it costs

**Not scheduled, and not authorised by the session that wrote this brief.** Ethan decided on 27 Oct that the check below is not run that night, nor before 22 November 2026 (6 December if D4's window extends). It runs only after the D4 window and its read, and only once it has a confirmed budget allocation within the site's 9,000-calls-a-day cap.

1. **The deciding check (not scheduled).**
   - What it asks: the Marine API's `current=sea_surface_temperature` at the 426 official sampling points.
   - **Requests and calls are different things.** Locations go comma-separated in one batched request, or a few if the free API limits batch size (undocumented). Open-Meteo weights each location as at least 1 call. So it is **one or a few HTTP requests, weighted as at least 426 calls**: about 4.7% of the 9,000-a-day cap, or more than three days of today's 127 spare.
   - What it records: each beach's answering cell and its distance from the sampling point, then the count of distinct cells.
2. **Decide by the count, before writing code:** daily, rotating, or wait for a paid plan (above). Distances over a stated limit (for example 20 km) mean no value is shown for that beach.
3. **Only then build:**
   - commit the official coordinates;
   - add a spare-calls fetch with its own daily cap, from 22 Nov at the earliest (6 Dec if D4 extends);
   - add the directory line, worded as above;
   - credit Copernicus Marine and Open-Meteo on the terms page, and document the field on the data page;
   - add tests, including the ration rule.

Nothing in steps 1 to 3 is started.

**Calls used for this brief:** three location-weighted Marine calls from this Mac on 27 Oct, in two requests: Ainsdale (1), then Spittal and Seaton Carew (2). No other Open-Meteo calls were made for it.
