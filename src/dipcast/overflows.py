"""The unified overflow table: live status + annual-return covariates + network snap."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

import numpy as np
import pandas as pd
from shapely.geometry import Point

from dipcast import config
from dipcast.ingest.live import data_states, with_data_states
from dipcast.model.features import fill_covariates
from dipcast.network.names import QUALIFIERS
from dipcast.network.rivers import _TO_BNG, RiverNetwork

log = logging.getLogger(__name__)

NAME = "overflows.parquet"

# Outfalls to the sea or an estuary are outside the inland network by design.
MARINE = re.compile(r"\b(?:sea|channel|solent|estuary|estuarine|harbour|harbor|firth|bay|the wash|coast|coastal|"
                    r"marine|ocean|sound|beach|foreshore|mudflat|saltmarsh|creek|haven|offshore)\b", re.IGNORECASE)

# Scotland (plan section 5.2 and task S5, written 11 Oct 2026). "Loch" names freshwater lochs (Lomond,
# Ness, Leven at Kinross) and sea lochs (Fyne, Long, Ryan) alike, so MARINE leaves it out, and OS Open
# Rivers has no sea: an outfall on a sea loch snaps to the nearest burn, tidal reach or lochan as if it
# discharged inland. SEPA's water-body polygons would settle each one; their licence is not yet
# checked (plan, task S6). Until then marine_scotland reads a receiving water as marine when
#   1. it matches MARINE, or names a kyle, voe, the Minch or a sea loch in so many words, or
#   2. it is one of SEA_LOCHS, or Loch Leven (both a sea loch and a freshwater loch) and the outfall's
#      first snap is a tidal river,
# unless the name says the discharge reaches a burn, drain, ditch or tributary first ("Un-named
# tributary of Firth of Forth", "Findhorn Bay - via tidal reaches of the Mosset Burn"): that is an
# inland watercourse, as the name says. SEA_LOCHS is every loch named as a receiving water in Scottish
# Water's API answer of 4 Oct 2026 that opens to the sea. *Inferred* from where each is (knowledge of
# the map; for most of them the outfall's nearest OS link is a tidal reach, checked 11 Oct 2026), not
# from SEPA's polygons. A loch not on the list stays inland, as England's rule would leave it.
SCOTTISH_MARINE = re.compile(r"\b(?:kyles?|voe|minch|sea loch)\b", re.IGNORECASE)
SEA_LOCHS = frozenset({
    "campbeltown loch", "east loch tarbert", "holy loch", "loch alsh", "loch broom", "loch carron",
    "loch etive", "loch ewe", "loch fyne", "loch gairloch", "loch gilp", "loch indaal", "loch kishorn",
    "loch leodamais", "loch leodamis", "loch leurbost", "loch linnhe", "loch long", "loch nan ceall",
    "loch portree", "loch ryan", "loch sunart", "loch torridon", "loch a'chumhainn"})
BOTH_KINDS = frozenset({"loch leven"})
INLAND_FIRST = re.compile(r"\b(?:tributary|trib|drain|ditch|burn|via)\b", re.IGNORECASE)


def marine_scotland(names: pd.Series, first_form: pd.Series | None = None) -> pd.Series:
    """True where a Scottish receiving water reads as marine (rule above). `first_form` is the form of
    each outfall's first-pass snap (None where it did not snap); without it Loch Leven stays inland."""
    n = names.fillna("").astype(str)
    key = n.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    form = pd.Series(None, index=n.index, dtype=object) if first_form is None else pd.Series(first_form, index=n.index)
    marine = n.str.contains(MARINE) | n.str.contains(SCOTTISH_MARINE) | key.isin(SEA_LOCHS)
    marine |= key.isin(BOTH_KINDS) & form.eq("tidalRiver")
    return marine & ~n.str.contains(INLAND_FIRST)


WIDE_SNAP_M = 1_500.0
GENERIC = {"river", "brook", "beck", "stream", "dyke", "dike", "drain", "water", "burn", "canal", "trib",
           "tributary", "the", "ditch", "cut", "sewer", "main", "new", "unnamed", "culverted", "via",
           "a", "an", "onto", "land", "stw", "cso", "outfall", "ordinary", "watercourse",
           "surface", "freshwater", "controlled", "waters", "mill", "leat", "branch", "arm", "sluice"} | QUALIFIERS


def _tokens(name) -> set[str]:
    if not isinstance(name, str):
        return set()
    name = re.sub(r"\(.*?\)", " ", name.lower())
    return {t for t in re.findall(r"[a-z]{3,}", name) if t not in GENERIC}


# Outfalls to the ground: an infiltration system, a soakaway, land. Their water does not run in a river,
# so they stay off the network. Morestead Road, Winchester ("SEWAGE FARM" live, "GROUNDWATERS VIA 2
# INFILT SYST" in the return) was snapped 1.2 km to the Itchen Navigation and counted for Compton Lock
# until 11 Oct 2026. Only when every name given says so: "RIVER WEY AND GROUNDWATER" reaches the Wey,
# and the Land Yeo is a river.
GROUND = re.compile(r"ground ?waters?|underground|strata|soak ?away|infiltrat|borehole|aquifer|percolat|"
                    r"sewage farm|\b(?:onto|into|to|via)\s+land\b|^\s*land\s*$|land treatment", re.IGNORECASE)
NO_NAME = re.compile(r"^\s*(?:not applicable|n/?a|no details|unknown|none|-)?\s*$", re.IGNORECASE)


def to_ground(*names: pd.Series) -> pd.Series:
    """True where every receiving-water name given reads as the ground, and at least one is given."""
    said, other = None, None
    for n in names:
        n = n.fillna("").astype(str)
        g = n.str.contains(GROUND)
        blank = n.str.match(NO_NAME)
        said = g if said is None else (said | g)
        other = (~g & ~blank) if other is None else (other | (~g & ~blank))
    return said & ~other


POSITION_GAP_M = 300.0    # live position and annual-return outlet further apart than this: pick one
NAMED_NEAR_M = 750.0      # ...by which has a link carrying the receiving water's name this close
POSITION_EXTRA = {"lake", "tarn", "reservoir", "pond", "mere", "via", "sws", "culverted", "pumped", "outlet",
                  "and", "tribs", "various", "sites"}
PLACE_GAP_M = 1000.0      # names decide nothing near either and the two are this far apart: weigh the evidence
PLACE_NEAR_M = 3000.0     # ...within this of each: the water's name, the water body's name, the overflow's place
PLACES = config.RAW / "places.json"
# Words that match unrelated links within PLACE_NEAR_M: regional stream words, the sea, plurals.
EVIDENCE_EXTRA = {"gill", "ghyll", "sike", "syke", "clough", "lode", "rhyne", "goit", "stell", "dean", "dene",
                  "gutter", "fleet", "carr", "sea", "estuary", "channel", "bay", "harbour", "sound", "streams",
                  "brooks", "becks", "burns"}
WATER_BODY_TAIL = re.compile(r"\s(?:from|to|conf)\b.*$", re.IGNORECASE)


@lru_cache(maxsize=1)
def _places() -> dict[str, np.ndarray]:
    """OS Open Names places (data/raw/places.json, to 0.01 degree): lower-case name before any
    comma -> BNG points of every place so called."""
    if not PLACES.exists():
        return {}
    rows = json.loads(PLACES.read_text())["places"]
    xs, ys = _TO_BNG.transform([float(r[2]) for r in rows], [float(r[1]) for r in rows])
    out: dict[str, list] = {}
    for r, x, y in zip(rows, xs, ys, strict=True):
        out.setdefault(re.sub(r",.*$", "", str(r[0])).strip().lower(), []).append((x, y))
    return {k: np.array(v) for k, v in out.items()}


def _named_place(site_name) -> np.ndarray | None:
    """Points of the longest place name (up to four words) found in an overflow's site name."""
    if not isinstance(site_name, str):
        return None
    words = re.sub(r"[^a-z ]", " ", site_name.lower()).split()
    places = _places()
    for n in range(4, 0, -1):
        hits = [places[k] for j in range(len(words) - n + 1)
                if len(k := " ".join(words[j:j + n])) > 3 and k in places]
        if hits:
            return np.vstack(hits)
    return None


def _same_water(a, b) -> bool:
    """The live and annual-return receiving waters agree, or one gives no distinctive word."""
    ta, tb = _tokens(a), _tokens(b)
    return not ta or not tb or bool(ta & tb)


def _named_within(net: RiverNetwork, x: float, y: float, want: set[str]) -> bool:
    if not want:
        return False
    cand = net.candidates_xy(x, y, NAMED_NEAR_M)
    alt = cand.get("watercourse_name_alternative", pd.Series(None, index=cand.index, dtype=object))
    return any(want & (_tokens(n) | _tokens(a)) for n, a in zip(cand["watercourse_name"], alt))


def choose_positions(net: RiverNetwork, df: pd.DataFrame) -> pd.DataFrame:
    """Where an overflow's live position and its annual-return outlet (the EA consent's grid
    reference) are over POSITION_GAP_M apart, use the outlet when it alone has a link carrying the
    receiving water's name within NAMED_NEAR_M. The live position is kept otherwise, as before.

    Until 11 Oct 2026 the live position always won. Of the 420 overflows whose two positions
    disagree and whose receiving water has a name, the outlet alone matched it at 40: Buxton STW,
    on the Derbyshire Wye, was live 45 km away; Earl Sterndale STW sits by Hartington in the live
    feed, 6.7 km from the village. The live position alone matched at 55, both at 159, neither at
    166 (11 Oct 2026).

    When names decide nothing within NAMED_NEAR_M and the two are over PLACE_GAP_M apart, the
    evidence within PLACE_NEAR_M of each is weighed (position_evidence): the receiving waters' names,
    the WFD water body's name, and a place the overflow's name gives (OS Open Names). The outlet is
    used when some evidence points to it and none to the live position, provided the two receiving
    waters agree (or one is generic), so both rows describe the same asset, and do not put it in the
    ground. Until 13 Oct 2026 only the place counted (#179). Earl Sterndale STW (Glutton Brook, 35%
    of Dovedale's weight) and Hazeldene Lane, Newick (above Barcombe Mills, live 61 km away) move;
    Holy Island STW does not ("Birkley Burn" live, "NORTH SEA" in the return: two assets under one
    id). KEEP_LIVE lists any move a check contradicts (docs/OVERFLOW-POSITIONS-2026-10.md). Adds
    `position_source`: 'live', 'annual return' or 'join' (overflow_joins)."""
    df = df.copy()
    df["position_source"] = np.where(df["lat"].notna(), "live", "annual return")
    both = df["lat"].notna() & df["ar_lat"].notna()
    if not both.any():
        return df
    lx, ly = _TO_BNG.transform(df.loc[both, "lon"].to_numpy(), df.loc[both, "lat"].to_numpy())
    ax, ay = _TO_BNG.transform(df.loc[both, "ar_lon"].to_numpy(), df.loc[both, "ar_lat"].to_numpy())
    gap = np.hypot(lx - ax, ly - ay)
    moved, by_evidence = [], 0
    for i, lxi, lyi, axi, ayi, g in zip(df.index[both], lx, ly, ax, ay, gap, strict=True):
        if g <= POSITION_GAP_M:
            continue
        rw, rw_ar = df.at[i, "receiving_watercourse"], df.at[i, "receiving_water"]
        want = (_tokens(rw) | _tokens(rw_ar)) - POSITION_EXTRA
        at_outlet, at_live = _named_within(net, axi, ayi, want), _named_within(net, lxi, lyi, want)
        if at_outlet and not at_live:
            moved.append(i)
        elif (not at_outlet and not at_live and g > PLACE_GAP_M and _same_water(rw, rw_ar)
              and not _ground_names(rw, rw_ar)):
            ev = position_evidence(net, df.loc[i], (lxi, lyi), (axi, ayi)).values()
            if "annual return" in ev and "live" not in ev and df.at[i, "site_id"] not in KEEP_LIVE:
                moved.append(i)
                by_evidence += 1
    df.loc[moved, "lat"] = df.loc[moved, "ar_lat"]
    df.loc[moved, "lon"] = df.loc[moved, "ar_lon"]
    df.loc[moved, "position_source"] = "annual return"
    log.info("positions: %d overflows moved to their annual-return outlet: %d by the named water, %d by the "
             "evidence within %.0f km", len(moved), len(moved) - by_evidence, by_evidence, PLACE_NEAR_M / 1000)
    return df


def _ground_names(*names) -> bool:
    return bool(to_ground(*(pd.Series([n], dtype=object) for n in names)).iloc[0])


def water_body_words(name) -> set[str]:
    """The distinctive words of a WFD water body name, before any "from", "to" or "conf", brackets
    dropped: "Crimple Beck from Source to Park Beck" -> {"crimple"}, "Wey (Shalford to River Thames
    confluence at Weybridge)" -> {"wey"}."""
    if not isinstance(name, str):
        return set()
    return _tokens(WATER_BODY_TAIL.sub("", re.sub(r"\(.*?\)", " ", name)))


def position_evidence(net: RiverNetwork, row, live_xy, ar_xy) -> dict[str, str | None]:
    """Which position each kind of evidence points to ('live', 'annual return' or None), within
    PLACE_NEAR_M of each (BNG points): e1, a link carrying the receiving waters' words; e2, a link
    carrying the WFD water body's words; e3, a place the site name gives (OS Open Names). A kind
    points to a position when that position has it and the other does not."""
    def side(at_live: bool, at_ar: bool) -> str | None:
        return "live" if at_live and not at_ar else "annual return" if at_ar and not at_live else None

    def named(xy, want) -> bool:
        if not want:
            return False
        cand = net.candidates_xy(xy[0], xy[1], PLACE_NEAR_M)
        alt = cand.get("watercourse_name_alternative", pd.Series(None, index=cand.index, dtype=object))
        return any(want & (_tokens(n) | _tokens(a)) for n, a in zip(cand["watercourse_name"], alt))

    drop = POSITION_EXTRA | EVIDENCE_EXTRA
    water = (_tokens(row.get("receiving_watercourse")) | _tokens(row.get("receiving_water"))) - drop
    body = water_body_words(row.get("wfd_waterbody_name")) - drop
    out = {"e1": side(named(live_xy, water), named(ar_xy, water)),
           "e2": side(named(live_xy, body), named(ar_xy, body)), "e3": None}
    pts = _named_place(row.get("site_name"))
    if pts is not None:
        d_live = float(np.hypot(pts[:, 0] - live_xy[0], pts[:, 1] - live_xy[1]).min())
        d_ar = float(np.hypot(pts[:, 0] - ar_xy[0], pts[:, 1] - ar_xy[1]).min())
        out["e3"] = side(d_live <= PLACE_NEAR_M, d_ar <= PLACE_NEAR_M)
    return out


# Overflows the evidence would move to the outlet but a check against another source contradicts:
# id -> why. They keep the live position (docs/OVERFLOW-POSITIONS-2026-10.md, checks K3 and K4).
KEEP_LIVE: dict[str, str] = {
    "SWS00971": "East Worthing CSO: the place points to the outlet, but the live position is 8 m from a storm "
                "overflow in the EA's features for its bathing water (ukj2407-15350) and the outlet 1.2 km from any",
}


JOINS = config.RAW / "overflow_joins.csv"


def apply_joins(df: pd.DataFrame, path=None) -> pd.DataFrame:
    """Checked joins (data/raw/overflow_joins.csv): an outfall on a stream OS Open Rivers does not
    draw, placed where that stream meets a river it does draw. Each row says how it was checked."""
    path = JOINS if path is None else path
    if not path.exists():
        return df
    j = pd.read_csv(path, comment="#").set_index("site_id")
    hit = df["site_id"].isin(j.index)
    df.loc[hit, "lat"] = df.loc[hit, "site_id"].map(j["join_lat"]).to_numpy()
    df.loc[hit, "lon"] = df.loc[hit, "site_id"].map(j["join_lon"]).to_numpy()
    df.loc[hit, "position_source"] = "join"
    return df


TRIBUTARY = re.compile(r"\btrib(?:utary|s)?\b", re.IGNORECASE)


def own_water(name) -> set[str]:
    """The distinctive words of the water an outfall discharges into, not of the river that water
    joins: "Harrow Beck, a Tributary of the River Eden" -> {"harrow"}, "TRIB OF CAM BROOK" -> set()."""
    if not isinstance(name, str):
        return set()
    return _tokens(TRIBUTARY.split(name, maxsplit=1)[0])


def on_named(net: RiverNetwork, df: pd.DataFrame) -> pd.Series:
    """Whether each overflow's snapped link carries a distinctive word of its own receiving water
    (own_water). An outfall into "a tributary of the River Eden" snapped onto the Eden is not: the
    tributary meets the Eden somewhere, and that is not known from the name."""
    names = net.links["watercourse_name"]
    alt = net.links.get("watercourse_name_alternative", pd.Series(None, index=net.links.index, dtype=object))

    def one(lid, rw) -> bool:
        if not isinstance(lid, str) or lid not in names.index:
            return False
        return bool(own_water(rw) & (_tokens(names.get(lid)) | _tokens(alt.get(lid))))

    return pd.Series([one(l, r) for l, r in zip(df["link_id"], df["receiving_watercourse"], strict=True)],
                     index=df.index, dtype=bool)


def _second_pass(net: RiverNetwork, df: pd.DataFrame, is_marine=None) -> pd.DataFrame:
    """Try a wider radius for inland outfalls that missed the first pass, preferring
    a link whose name shares a distinctive word with the recorded receiving water.
    `is_marine(rows) -> bool Series` replaces the MARINE name test (Scotland: scottish_shadow).
    Outfalls to the ground (snap_confidence 'ground') stay off the network."""
    todo = df[df["link_id"].isna() & df["snap_confidence"].ne("ground")]
    marine = (todo["receiving_watercourse"].fillna("").str.contains(MARINE) if is_marine is None
              else is_marine(todo).astype(bool))
    df.loc[todo.index[marine], "snap_confidence"] = "marine"
    xs, ys = _TO_BNG.transform(todo.loc[~marine, "lon"].to_numpy(), todo.loc[~marine, "lat"].to_numpy())
    hits = {"medium": 0, "low": 0}
    for (i, row), x, y in zip(todo[~marine].iterrows(), xs, ys, strict=True):
        cand = net.candidates_xy(x, y, WIDE_SNAP_M)
        if cand.empty:
            continue
        want = _tokens(row["receiving_watercourse"])
        pick, conf = None, "low"
        if want:
            named = cand[cand["watercourse_name"].map(lambda n, want=want: bool(_tokens(n) & want))]
            if not named.empty:
                pick, conf = named.iloc[0], "medium"
        if pick is None:
            pick = cand.iloc[0]
        pt = Point(x, y)
        df.loc[i, ["link_id", "frac", "snap_dist_m", "form", "snap_confidence"]] = [
            pick["id"], float(pick.geometry.project(pt, normalized=True)), float(pick["dist_m"]), pick["form"], conf]
        hits[conf] += 1
    log.info("second-pass snapping: %d name-matched (medium), %d nearest-only (low), %d marine excluded",
             hits["medium"], hits["low"], int(marine.sum()))
    return df


def latest_annual_returns(ar: pd.DataFrame) -> pd.DataFrame:
    a = ar.dropna(subset=["site_id"]).sort_values("year")
    a = a.groupby("site_id", as_index=False).last()
    return a[["site_id", "company", "site_name", "asset_type", "lat", "lon", "lta_spills",
              "spill_hours", "edm_operational_pct", "wfd_waterbody_name", "receiving_water",
              "bathing_water", "year"]].rename(columns={"lat": "ar_lat", "lon": "ar_lon",
                                                        "year": "ar_year", "company": "ar_company"})


def duplicate_site_ids(df: pd.DataFrame) -> list[str]:
    """The overflow ids on more than one row of `df`, sorted."""
    return sorted(df.loc[df["site_id"].duplicated(), "site_id"].astype(str).unique())


def one_row_per_overflow(live: pd.DataFrame) -> pd.DataFrame:
    """The live snapshot with one row per site_id: the row with the latest `fetched_at`, then the
    latest `last_updated`, then the last listed. The table keys on site_id, and a repeated id
    upstream of a spot failed its forecast in the 3 Oct 2026 12:06 UTC build. The 02:59 poll
    that day listed Anglian Water's AWS00528 twice. fetch_live has dropped repeats since PR #57,
    so this guards snapshots and cached tables written before that."""
    dups = duplicate_site_ids(live)
    if not dups:
        return live
    more = f" and {len(dups) - 20} more" if len(dups) > 20 else ""
    log.warning("live snapshot lists %d overflow id%s more than once; keeping the most recent row of each: %s%s",
                len(dups), "" if len(dups) == 1 else "s", ", ".join(dups[:20]), more)
    keys = [c for c in ("fetched_at", "last_updated") if c in live]
    ranked = live.assign(_pos=np.arange(len(live))).sort_values([*keys, "_pos"], na_position="first")
    return ranked.drop_duplicates("site_id", keep="last").sort_values("_pos").drop(columns="_pos")


def build_overflows(net: RiverNetwork) -> pd.DataFrame:
    live = one_row_per_overflow(pd.read_parquet(config.state_read("live_latest.parquet")))
    ar = latest_annual_returns(pd.read_parquet(config.PROCESSED / "annual_returns.parquet"))
    df = live.merge(ar, on="site_id", how="outer")
    df["company"] = df["company"].fillna(df["ar_company"])
    df = choose_positions(net, df)
    df["lat"] = df["lat"].fillna(df["ar_lat"])
    df["lon"] = df["lon"].fillna(df["ar_lon"])
    df = apply_joins(df)
    ground = to_ground(df["receiving_watercourse"], df["receiving_water"])
    df["receiving_watercourse"] = df["receiving_watercourse"].fillna(df["receiving_water"])
    df["has_live"] = df["status"].notna()
    df["status"] = df["status"].fillna(-2).astype(int)   # -2 = no live feed
    df = pd.concat([df.drop(columns=["data_state", "feed_updated_at", "record_stale", "feed_on_change"], errors="ignore"), data_states(df)], axis=1)
    df = df.assign(_ground=ground).dropna(subset=["lat", "lon"]).drop(columns=["ar_lat", "ar_lon", "ar_company", "receiving_water"])
    df = df[(df.lat.between(49, 61)) & (df.lon.between(-9, 3))].reset_index(drop=True)
    # The spill model's covariates, filled once over the whole table (company-wide medians) for the
    # overflows with no annual return or a gap in it; the raw columns stay as they are.
    df = fill_covariates(df)

    snap = net.snap_many(df["lon"].to_numpy(), df["lat"].to_numpy(), max_m=config.SNAP_MAX_M)
    df["link_id"] = snap["link_id"].to_numpy()
    df["frac"] = snap["frac"].to_numpy()
    df["snap_dist_m"] = snap["dist_m"].to_numpy()
    df["form"] = snap["form"].to_numpy()
    df["snap_confidence"] = np.where(df["link_id"].notna(), "high", None)
    g = df.pop("_ground").astype(bool).to_numpy()
    df.loc[g, ["link_id", "frac", "snap_dist_m", "form"]] = np.nan
    df.loc[g, "snap_confidence"] = "ground"
    df = _second_pass(net, df)
    snapped = df["link_id"].notna()
    df.loc[snapped, "start_node"] = net.links.loc[df.loc[snapped, "link_id"], "start_node"].to_numpy()
    df.loc[snapped, "end_node"] = net.links.loc[df.loc[snapped, "link_id"], "end_node"].to_numpy()
    df.loc[snapped, "link_length"] = net.links.loc[df.loc[snapped, "link_id"], "length"].to_numpy()
    df["on_named"] = on_named(net, df)
    log.info("overflows: %d total, %d with live feed, %d snapped to network (%.0f%%); confidence %s; data states %s",
             len(df), int(df.has_live.sum()), int(snapped.sum()), 100 * snapped.mean(),
             df["snap_confidence"].value_counts(dropna=False).to_dict(), df["data_state"].value_counts().to_dict())
    df[NETWORK_KEY] = net.topology_key()
    df.to_parquet(config.state_write(NAME), index=False)
    return df


# The network a table was built on (RiverNetwork.topology_key): each overflow's link, frac and start node
# are measured on it. Since 11 Oct 2026 the network is mended as it loads, and 59 links are turned round,
# so a table cached before then, or built with other fixes, places some overflows from the wrong end of
# their link. The live pipeline rebuilds the table on every run; offline scripts read the cache.
NETWORK_KEY = "network_key"


class StaleOverflowTable(RuntimeError):
    """The cached overflow table was built on another river network."""


def load_overflows(net: RiverNetwork | None = None, rebuild: bool = False) -> pd.DataFrame:
    """The cached overflow table, or a new one. With `net`, a cached table must have been built on that
    network: one built on another (or before 12 Oct 2026, with no key) raises StaleOverflowTable rather
    than be read, and is not rebuilt in its place, since that would overwrite a shared copy (set
    DIPCAST_STATE to a scratch folder and pass rebuild=True). Without `net` nothing is checked."""
    path = config.state_read(NAME)
    if path.exists() and not rebuild:
        df = pd.read_parquet(path)
        if net is not None:
            key = df[NETWORK_KEY].iloc[0] if NETWORK_KEY in df and len(df) else None
            if key != net.topology_key():
                raise StaleOverflowTable(
                    f"{path} was built on {'another river network' if key else 'a network before 12 Oct 2026'} "
                    f"({key or 'no key'}, this one is {net.topology_key()}): rebuild it with "
                    "load_overflows(net, rebuild=True), with DIPCAST_STATE set to a scratch folder")
        # A table cached before build_overflows dropped repeats can still list an id twice
        # (AWS00528 in the 3 Oct 2026 02:59 state); its weight would then count twice upstream of a spot.
        # One cached before 4 Oct 2026 has no data states: they are worked out from its live columns.
        return with_data_states(one_row_per_overflow(df))
    assert net is not None
    return build_overflows(net)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    net = RiverNetwork.load()
    df = build_overflows(net)
    print(df.groupby("company").agg(n=("site_id", "size"), live=("has_live", "sum"),
                                    snapped=("link_id", lambda s: s.notna().sum()),
                                    lake=("form", lambda s: (s == "lake").sum())))
    print("snap distance quantiles (m):", df.snap_dist_m.quantile([.5, .9, .99]).round(0).to_dict())
    print(df.groupby("snap_confidence", dropna=False).size())
