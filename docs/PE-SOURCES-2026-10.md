# Population equivalent for each overflow: sources looked for, and why the work is parked

Written 15 October 2026. This is a note, not a test: nothing was run and nothing in the model changes.
It closes item 5 of the 14 October list ("length dilution: true population equivalent needs a source
other than the consents register") until a reason to reopen it appears.

## What is already established

- **Four sizes have failed their stated tests:**
  - flow dilution and urban area (#166, #172);
  - a junction rule (#181);
  - spill hours (#197);
  - consented dry weather flow (#210).
- **#210 is the closest to population equivalent (PE).** A works' dry weather flow is set from the
  population it serves. Its sizes did worse than giving every overflow one size. They also did worse
  than 17 to 19 of 20 random reshuffles of the same sizes, on every measure. So the sizes carried
  information, but it pointed the wrong way.
- **The EA's Urban Waste Water Treatment (UWWTD) table** has PE for works over 2,000 p.e. only. In
  #172 those overflows carried 12% of the hazard upstream of the sampled sites
  (`docs/URBAN-DILUTION-DIAGNOSIS-2026-10.md`).

## Sources looked for on 15 October 2026

- **The EA's storm overflow annual returns** (EDM): spill counts, hours, positions, receiving
  water and WFD water body per overflow. No population or PE field.
- **The EA consents register:** no PE field (#210). It is also internal-use only, so nothing from it
  can be published.
- **The companies' Drainage and Wastewater Management Plans (DWMP).** Yorkshire Water's level 3
  PDFs (one per area, a page per treatment works catchment) give a 2020 and 2050 population
  equivalent. The Lower Ouse PDF, 25 MB, opened 15 Oct 2026, gives Barlby 8,771 p.e. in 2020, and
  works as small as 18 p.e. So unlike UWWTD they reach small works. But:
  - they are PDFs, not a table;
  - they give one figure per works, not per overflow;
  - their licence was not checked. United Utilities shows its DWMP through a
  customer portal. No company was found publishing a downloadable table.
- **A web search** for an open per-overflow PE dataset found none.

## Why parked

- No open source gives PE per overflow. The nearest gives it per works catchment, scattered across
  PDFs, with an unchecked licence.
- Inferred, not tested: PE would point the same way as dry weather flow, since both scale with the
  population served. #210's result against random reshuffles suggests a bigger catchment does not mean
  more E. coli at the sampled spot. So a new PE source is unlikely to pass a fair test.

## What would reopen it

- A company or the EA publishing PE per overflow, or per works with overflow ids, under an open
  licence.
- A different question that needs PE, for example reporting a spot's upstream population. That does
  not depend on PE improving the forecast.

Sources:
- [EA storm overflows collection](https://www.data.gov.uk/collections/environment/storm-overflows)
- [EDM annual returns](https://ckan.publishing.service.gov.uk/dataset/19f6064d-7356-466f-844e-d20ea10ae9fd)
- [Yorkshire Water DWMP, Lower Ouse catchment](https://Yorkshirewater.com/media/erbdotvo/yw_level_3_lower_ouse_o.pdf)
