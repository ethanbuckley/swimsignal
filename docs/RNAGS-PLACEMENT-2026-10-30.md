# RNAG lake placements, 30 October 2026

The four additions to the spot catalogue were checked using `scripts/make_rnags.py`'s existing lake placement rule and the cached Environment Agency WFD Cycle 3 lake polygons. The polygon file SHA-256 was `c355d810bc2a76669822aa9b240925dcc30b6d82da70838d229c01cd9f1bb287`; the pre-change RNAG registry SHA-256 was `e416907b100fd640df39ec539683789e20a02e4636cd544f41b0d9cebc17fe89`. The existing RNAG dataset remains the 18 October 2026 snapshot; this does not claim a fresh download of its pressure records.

| Spot | Checked placement |
|---|---|
| Brothers Water | GB30229116, polygon contains the spot |
| Loweswater | GB31228986, polygon contains the spot |
| Bassenthwaite Lake | GB31228847, polygon contains the spot |
| Carding Mill Valley Reservoir | No WFD lake polygon matched within the existing placement rule; recorded as null. This is not evidence that there are no pressures. |

The three identifiers and names also occur in the existing RNAG registry. Pressure context remains exactly what that snapshot records; a null placement adds no water-body or agricultural-pressure claim. Geometry was copied to a scratch root for this check, and the source geometry and original registry fingerprints were unchanged by the run. Re-run the placement and refresh the source snapshot when the data are next updated.

A scratch application of `attach_water_body` to the four public spot records returned three enriched records and no unknown IDs. Brothers Water receives its body name without an agricultural flag; Loweswater and Bassenthwaite receive the existing snapshot's confirmed and probable rural-pollution flags respectively. Carding Mill receives no water-body field. This is a preview of the enrichment, not a claim that the public site has already updated.
