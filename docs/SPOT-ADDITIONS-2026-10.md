# Spots added in late October 2026: evidence and provenance

Each spot here passed the four inclusion rules:
1. not a managed or paid venue;
2. not under 1 km from a listed spot on the same water;
3. placed by the river network;
4. evidence of public access from the owner's, operator's or authority's own page. A footpath, common land or a
   swim listing is a lead, never evidence.

Pages were read first-hand on the date given. Nothing is deployed until the branch is merged. Each spot's Open-Meteo
cost is from `scripts/spot_cost.py` (free tier, #416).

## Carding Mill Valley Reservoir, Long Mynd (`carding-mill-reservoir`), 28 October 2026

**Access (rule 4).** [National Trust, "Things to do at Carding Mill Valley on the Long Mynd"](https://www.nationaltrust.org.uk/visit/shropshire-staffordshire/carding-mill-valley-on-the-long-mynd/things-to-do-at-carding-mill-valley-and-the-long-mynd)
says, under "Go wild swimming", "Why not go for a dip in the reservoir?". It asks swimmers to read the information at
the reservoir before going in, and not to swim solo in winter. The Trust owns the land. Swimming is free; parking is
pay and display (rule 1).

**Position.** OS Open Rivers lake link `7713B5C1-B8ED-46B4-AF0F-42EB2BAFD908` (OGL, in the repo's river network).
- 88.3 m long, unnamed, form `lake`.
- The spot is its midpoint: **SO 4362 9456, 52.54602, −2.83282**.
- Cross-check: Geograph photo [2398298](https://www.geograph.org.uk/photo/2398298), titled "Carding Mill Valley Reservoir", at SO 435 945 to 100 m, is 49 m away.
- The Trust's [Reservoir walk](https://www.nationaltrust.org.uk/visit/shropshire-staffordshire/carding-mill-valley-on-the-long-mynd/new-pool-hollow-walk) route agrees: along New Pool Hollow from the Chalet Pavilion, then "within 400 metres" up the reservoir bank.
- That page's own grid ref, SO411949, is on the plateau about 2.5 km west and contradicts its route, so it is not used.
- The reservoir is not a WFD lake: the nearest, Bomere Pool, is 14.7 km away.

**Placement (rule 3),** on the real network with the build's repairs:
- mode `lake`, source `centreline`, on that link, 0.1 m from the pin;
- outlet node `94E7A8FD-913D-469E-99F3-B257409CC025`;
- 0.21 km of stream network above the lake.

This is the small-unmapped-lake rule (`transport._locate_lake`).

**Overflows and words.** No monitored overflow upstream. The page says "No monitored overflow found upstream" and gives no spill forecast (`levels.js`, `FOUND_NONE`). That claims only that none is monitored.

**Cost: 9 calls a day,** the weather point.
- Its rain cell (52.5, −2.8) is already among the listed spots' cells.
- On #416's planned day this takes 8,873 to about 8,882 of 9,000.
- It has no spill forecast, so the ensemble-rain test (D4) does not bear on it.

**Guide.** `guides/carding-mill-reservoir.toml`, desk-checked 28 Oct from the two Trust pages: parking, the path, toilets, and the swimming invitation.

**Tests.** `tests/test_carding_mill.py`.

**For a human:**
- an on-site look at the entry point and the information board;
- whether a fenced upland reservoir suits the product.
