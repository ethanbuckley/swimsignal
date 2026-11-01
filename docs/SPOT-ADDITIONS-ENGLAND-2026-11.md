# English spots added on 1 November 2026, under a relaxed access rule

## 1. The decision

On 1 November 2026 Ethan relaxed rule 4 (`SPOT-ADDITIONS-2026-10.md`) for English spots from OpenStreetMap. Before,
a spot needed the owner's, operator's or authority's own page saying people may swim there. Now it needs only
that no owner, operator or authority says no. Rules 1 to 3 are unchanged: not paid or managed, not under 1 km from
a listed spot on the same water, placed by the river network.

Finding no "no" is not a yes. Each page carries the existing note: "Permission to enter the water at this point has
not been confirmed" (`access.py`, status `unconfirmed`, checked 1 Nov 2026).

## 2. Added: two

| Spot | Overflows upstream | Open-Meteo calls a day, planned most | Access note |
|---|---:|---:|---|
| River Tame, Dosthill, Tamworth (`node/6646996432`) | 148, Severn Trent | 161 | Unconfirmed. Police and Staffordshire Fire have warned teenagers against swimming in the Tame at Tamworth; these are safety warnings, not a ban, and none names Dosthill |
| Blackaton Brook, Shilley Pool, Dartmoor (`node/12305131265`) | 0 | 11 | Dartmoor National Park Authority: "You can swim in Dartmoor’s rivers as long as you access from points" not on private land ([FAQ](https://www.dartmoor.gov.uk/enjoy-dartmoor/planning-your-visit/visiting-faqs), read 1 Nov). Natural England's layer puts the point on Dartmoor commons |

Shilley Pool is 1,082 m from the nearest mapped link, on its own brook. Nothing is upstream on moorland, so its
page says no monitored overflow was found upstream.

**Budget.** Busiest recent day 6,827 calls (31 Oct). With the nine Scottish spots of PR #595 (about 153) and these
two (about 172), the planned most is about 7,150, under the 8,500 rule (`SPOT-ADDITIONS-2026-11.md`).

## 3. Not added

Of the 18 candidates examined on 1 Nov that had no owner page either way:
- **An owner or authority says no, or the land is private:** Pick Mere (no-swimming signs reported), Nunsmere (hotel-owned), Hickling Broad (nature reserve; reported not permitted), Cherry Hinton lakes (private), East Okement, Kate Brook and River Ashburn (Dartmoor's condition fails: not on access or common land), Odiham (canal authority discourages swimming).
- **OpenStreetMap marks the point `access=private` or `no`:** Great Ouse at Godmanchester, River Snail at Chippenham, Wye at Backney Common, Itchen at Gunner's Hole. A tag is a lead, not evidence, but it points to no.
- **Not the river:** the Nene at Peterborough is tagged on a demolished leisure centre (`disused:leisure=fitness_centre`). The Hemingford Grey point is 1,034 m from the Great Ouse and places on an unnamed channel with nothing upstream.
- **Out of scope:** Exe at Countess Wear (tidal), Clevedon Marine Lake (seawater), Burgess Park lake (council lists fishing only).

Of the 36 not examined before, 14 inland ones were checked on 1 Nov by desk research and OpenStreetMap's tags around
each point. None qualifies: most `sport=swimming` tags near a river mark a pool, leisure centre, holiday park,
campsite pond or paid lake, not the river. They were Rothley Brook (school pool), Whitsun Brook (Watersedge, paid),
River Tove and Wilson's Water (small private ponds, inferred), River Bulbourne (Sportspace), Flax Bourton bathing pond
(listed ruin, owner unknown), Camberley Bathing Pool (likely RMA Sandhurst land, inferred), Lancing Brook (Knepp
campsite pond), Dipple Water (wake park), The Brook, Shanklin and River Brit (holiday parks), Gagle Brook (hotel
lake), Worth Abbey (garden pond) and River Leen (Southglade Leisure Centre). The other 22 are coastal, tidal or not
on mapped water.

## 4. What would add more

The OpenStreetMap list is used up. More English spots need positions from elsewhere: a curated point at a place
swimmers name (Hemingford Grey meadow, Peterborough Embankment), with the same rules and the same unconfirmed note.
