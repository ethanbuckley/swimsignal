# Smoke-test forecast

Three spots from the published forecast of 5 November 2026, 20:48 UTC: River Thames at Henley (a river, live status
partly reporting), Swale above Richmond Falls (very high right now after recent spills, a rated bathing water) and
Cotswold Country Park (an isolated lake, no forecast days). `data/spots-lite.json` and `data/spots.json` keep only those
three, with the published credits; `data/spot/` and `data/upstream/` are their own files as published.

`tests/browser_smoke.mjs` serves `src/dipcast/site` with this folder as `data/` and fixes the clock two hours after
`generated_at`. To refresh it, download the same files from https://swimsignal.co.uk/data/ and keep the same three ids;
the clock follows the new `generated_at`.
