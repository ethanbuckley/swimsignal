"""A neural-net challenger to the spill model's layer 1 (docs/NEURAL-CHALLENGER-TEST-2026-10.md).

The network reads the hourly rain itself: a GRU over the 72 hours of d-2 to d, a dense layer over the
daily totals of d-30 to d-3, and the five season and annual-return inputs. It trains on exactly the
nine-company model's 2024 rows (scripts/train.py --nine) and is scored against that model's
candidate on its 2025 rows. Off CI, by hand, with PyTorch from the optional `nn` group:

    uv sync --extra nn
    uv run python scripts/train_nn.py time     # one epoch of seed 0, timed; nothing saved
    uv run python scripts/train_nn.py train    # seeds 0, 1, 2 -> data/processed/nn_challenger/
    uv run python scripts/train_nn.py score    # layer 2, 2025 on ERA5-Land and leads 0-4, conditions

`time` and `train` score nothing on 2025. `score` needs the candidate, spill_model_nine_2024.pkl
(SHA-256 begins 1603678923cc), which is kept off-repo: put it in data/processed/ first. Pass
`--overflows PATH` for condition 6 (default: the built site's site/data/overflows.geojson).
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn

from dipcast import config
from dipcast.model.features import (
    ALL_FEATURES,
    API_DECAY,
    LOCAL_TZ,
    MIN_HOURS_PER_DAY,
    SEASON_FEATURES,
    SITE_FEATURES,
    daily_rain_features,
    spill_days,
)
from dipcast.model.spill_model import EPS, SpillModel
from dipcast.model.training import (
    NINE,
    RAIN_DIRS,
    cells_of,
    ece,
    load_events,
    load_rain,
    site_years,
)
from dipcast.model.verify import reliability_table, scores

sys.path.insert(0, str(Path(__file__).resolve().parent))
# D2's rows, built exactly as D2 built them (scripts/train.py main_nine).
from train import NINE_PATH, _frame

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True)
log = logging.getLogger("train_nn")

STATIC = SEASON_FEATURES + SITE_FEATURES   # doy_sin, doy_cos, log_lta_spills, log_spill_hours, edm_pct
HOURS, DAYS = 72, 28                       # hourly window d-2..d; daily totals d-30..d-3
MIN_FINITE = int(np.ceil(0.9 * HOURS))     # the 90% rule: at least 65 of the 72 hours finite
T0 = pd.Timestamp("2023-12-01", tz="UTC")  # load_rain's start
T_END = pd.Timestamp("2026-01-01", tz="UTC")
NEG_FRAC, SEEDS = 0.25, (0, 1, 2)
LR, BATCH, MAX_EPOCHS, PATIENCE = 1e-3, 1024, 20, 3
PRIOR_STRENGTH, RECENCY = 15.0, 1.0
LEADS = [0, 1, 2, 3, 4]
N_BOOT = 2000
OUT = config.PROCESSED / "nn_challenger"
DOCS = config.ROOT / "docs" / "NEURAL-CHALLENGER-TEST-2026-10"
CANDIDATE_SHA = "1603678923cc"
_T = time.time()


def step(msg: str) -> None:
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9   # bytes on macOS
    log.info("[%6.0fs, peak %5.1f GB] %s", time.time() - _T, rss, msg)


def _key(lat, lon) -> np.ndarray:
    """One integer per 0.1-degree cell."""
    return (np.round(np.asarray(lat, float) * 10).astype(np.int64) * 100_000
            + np.round(np.asarray(lon, float) * 10).astype(np.int64))


# ------------------------------------------------------------------ rain as arrays
class RainGrid:
    """ERA5-Land hourly rain (mm, NaN where missing) as one row per cell, hour 0 = T0, and the
    nine-company model's daily rain total and antecedent index (daily_rain_features) per cell-day."""

    def __init__(self, rain: pd.DataFrame, daily: pd.DataFrame):
        n0 = len(rain)
        r = rain.sort_values(["cell_lat", "cell_lon", "time"])   # the dedup daily_rain_features does
        r = r[~r.duplicated(["cell_lat", "cell_lon", "time"], keep="last")]
        self.n_duplicates = n0 - len(r)
        self.keys = pd.Index(np.unique(_key(r["cell_lat"], r["cell_lon"])))
        self.n_hours = int((T_END - T0) / pd.Timedelta(hours=1))
        self.n_days = self.n_hours // 24
        self.mm = np.full((len(self.keys), self.n_hours), np.nan, np.float32)
        ci = self.keys.get_indexer(_key(r["cell_lat"], r["cell_lon"]))
        hi = ((r["time"] - T0) // pd.Timedelta(hours=1)).to_numpy()
        ok = (hi >= 0) & (hi < self.n_hours)
        self.mm[ci[ok], hi[ok]] = pd.to_numeric(r["precip_mm"], errors="coerce").to_numpy()[ok]
        self.rain_d = np.full((len(self.keys), self.n_days), np.nan, np.float32)
        self.api = np.full((len(self.keys), self.n_days), np.nan, np.float32)
        dci = self.keys.get_indexer(_key(daily["cell_lat"], daily["cell_lon"]))
        ddi = ((daily["day"] - T0) // pd.Timedelta(days=1)).to_numpy()
        ok = (dci >= 0) & (ddi >= 0) & (ddi < self.n_days)
        self.rain_d[dci[ok], ddi[ok]] = daily["rain_d"].to_numpy()[ok]
        self.api[dci[ok], ddi[ok]] = daily["api"].to_numpy()[ok]
        # A day with too few hours has an unknown total (NaN); the boosted model's rolling totals skip
        # it, which is what 0 does here.
        self.daily_log = np.log1p(np.clip(np.nan_to_num(self.rain_d, nan=0.0), 0, None)).astype(np.float32)

    def rows(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        ci = self.keys.get_indexer(_key(frame["cell_lat"], frame["cell_lon"]))
        assert (ci >= 0).all(), "a row's cell has no rain"
        di = ((frame["day"] - T0) // pd.Timedelta(days=1)).to_numpy().astype(np.int64)
        assert di.min() >= 30, "a row's 28 daily totals start before the rain does"
        return ci.astype(np.int64), di

    def window(self, ci: np.ndarray, di: np.ndarray) -> np.ndarray:
        """The 72 hourly values (mm) from 00:00 UTC on d-2 to 23:00 UTC on d; NaN where missing."""
        return self.mm[ci[:, None], (di * 24 - 48)[:, None] + np.arange(HOURS)]

    def days(self, ci: np.ndarray, di: np.ndarray) -> np.ndarray:
        """log(1 + daily total) for d-30 .. d-3, oldest first."""
        return self.daily_log[ci[:, None], di[:, None] + np.arange(-30, -2)]


def encode(mm: np.ndarray) -> np.ndarray:
    """[n, 72] mm with NaN -> [n, 72, 2]: log(1 + mm) with missing hours as 0, and the missing flag."""
    miss = np.isnan(mm)
    return np.stack([np.log1p(np.clip(np.where(miss, 0.0, mm), 0, None)), miss], axis=-1).astype(np.float32)


# ------------------------------------------------------------------ the network
class Net(nn.Module):
    """GRU 32 over the 72 hours (2 channels), a dense layer of 16 over the 28 daily totals, the 5
    static inputs; concatenated, dense 32 with ReLU, one logit."""

    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(2, 32, batch_first=True)
        self.daily = nn.Linear(DAYS, 16)
        self.hidden = nn.Linear(32 + 16 + len(STATIC), 32)
        self.out = nn.Linear(32, 1)

    def forward(self, seq, days, static):
        _, h = self.gru(seq)
        z = torch.cat([h[-1], self.daily(days), static], dim=1)
        return self.out(torch.relu(self.hidden(z))).squeeze(1)


def numpy_logit(sd: dict[str, np.ndarray], seq: np.ndarray, days: np.ndarray, static: np.ndarray) -> np.ndarray:
    """The same forward pass in numpy, from a state_dict (the form production would run)."""
    wi, wh = sd["gru.weight_ih_l0"], sd["gru.weight_hh_l0"]
    bi, bh = sd["gru.bias_ih_l0"], sd["gru.bias_hh_l0"]
    H = wh.shape[1]
    h = np.zeros((len(seq), H), seq.dtype)
    for t in range(seq.shape[1]):
        gi = seq[:, t] @ wi.T + bi
        gh = h @ wh.T + bh
        r = 1 / (1 + np.exp(-(gi[:, :H] + gh[:, :H])))
        z = 1 / (1 + np.exp(-(gi[:, H:2 * H] + gh[:, H:2 * H])))
        n = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
        h = (1 - z) * n + z * h
    x = np.concatenate([h, days @ sd["daily.weight"].T + sd["daily.bias"], static], axis=1)
    x = np.maximum(x @ sd["hidden.weight"].T + sd["hidden.bias"], 0)
    return (x @ sd["out.weight"].T + sd["out.bias"])[:, 0]


class Inputs:
    """Rows as indices into a RainGrid, plus standardized static inputs."""

    def __init__(self, grid: RainGrid, frame: pd.DataFrame, mean: np.ndarray, std: np.ndarray, window=None):
        self.grid = grid
        self.ci, self.di = grid.rows(frame)
        self.static = ((frame[STATIC].to_numpy(np.float32) - mean) / std).astype(np.float32)
        self._window = window or grid.window

    def window(self, idx):
        return self._window(self.ci[idx], self.di[idx])

    def tensors(self, idx, transform=None):
        mm = self.window(idx)
        if transform is not None:
            mm = transform(mm)
        return (torch.from_numpy(encode(mm)), torch.from_numpy(self.grid.days(self.ci[idx], self.di[idx])),
                torch.from_numpy(self.static[idx]))


@torch.inference_mode()
def predict(nets: list[Net], x: Inputs, n: int, transform=None, chunk: int = 1 << 15) -> np.ndarray:
    """Each network's probability, [len(nets), n]."""
    out = np.empty((len(nets), n), np.float32)
    for a in range(0, n, chunk):
        idx = np.arange(a, min(a + chunk, n))
        t = x.tensors(idx, transform)
        for j, net in enumerate(nets):
            out[j, idx] = torch.sigmoid(net(*t)).numpy()
    return out


def weighted_bce(net: Net, x: Inputs, idx: np.ndarray, y: torch.Tensor, w: torch.Tensor) -> float:
    s = sw = 0.0
    with torch.inference_mode():
        for a in range(0, len(idx), 1 << 15):
            b = idx[a:a + (1 << 15)]
            bt = torch.from_numpy(b)
            loss = F.binary_cross_entropy_with_logits(net(*x.tensors(b)), y[bt], reduction="none")
            s += float((loss * w[bt]).sum())
            sw += float(w[bt].sum())
    return s / sw


def fit_seed(seed: int, x: Inputs, y: np.ndarray, w: np.ndarray, fit_idx: np.ndarray, val_idx: np.ndarray,
             max_epochs: int = MAX_EPOCHS) -> tuple[Net, list[dict]]:
    """Weighted BCE, Adam, early stopping on the inner hold-out with PATIENCE; the best epoch is kept."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    yt, wt = torch.from_numpy(y.astype(np.float32)), torch.from_numpy(w.astype(np.float32))
    best, bad, state, hist = np.inf, 0, None, []
    for epoch in range(1, max_epochs + 1):
        t0 = time.time()
        net.train()
        s = sw = 0.0
        perm = fit_idx[rng.permutation(len(fit_idx))]
        for a in range(0, len(perm), BATCH):
            idx = perm[a:a + BATCH]
            bt = torch.from_numpy(idx)
            loss_rows = F.binary_cross_entropy_with_logits(net(*x.tensors(idx)), yt[bt], reduction="none") * wt[bt]
            loss = loss_rows.mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            s += float(loss_rows.sum().detach())
            sw += float(wt[bt].sum())
        t_fit = time.time() - t0
        net.eval()
        val = weighted_bce(net, x, val_idx, yt, wt)
        improved = val < best
        if improved:
            best, bad = val, 0
            state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
        hist.append({"seed": seed, "epoch": epoch, "fit_seconds": round(t_fit, 1),
                     "val_seconds": round(time.time() - t0 - t_fit, 1), "train_loss": s / sw,
                     "val_loss": val, "best": improved})
        step(f"seed {seed} epoch {epoch}: train {s / sw:.5f}, inner hold-out {val:.5f}"
             f"{' (best)' if improved else ''}, {t_fit:.0f}s + {hist[-1]['val_seconds']:.0f}s")
        if bad >= PATIENCE:
            break
    net.load_state_dict(state)
    net.eval()
    return net, hist


# ------------------------------------------------------------------ data
def prepare() -> tuple[RainGrid, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """D2's rows: 2024 training and 2025 verification site-days (scripts/train.py main_nine)."""
    ar = pd.read_parquet(config.PROCESSED / "annual_returns.parquet")
    ev = load_events(NINE)
    labels = spill_days(ev)
    s24, c24 = site_years(ar, ev, NINE, 2024)
    s25, c25 = site_years(ar, ev, NINE, 2025)
    rain = load_rain(cells_of(pd.concat([s24, s25])))
    step(f"rain loaded: {len(rain)} cell-hours")
    daily = daily_rain_features(rain)
    grid = RainGrid(rain, daily)
    del rain
    step(f"rain grid: {len(grid.keys)} cells x {grid.n_hours} hours; {grid.n_duplicates} duplicate hours dropped")
    train = _frame(s24, 2024, daily, labels)
    test = _frame(s25, 2025, daily, labels)
    del daily
    step(f"site-days: train {len(train)}, test {len(test)}")
    assert len(train) == 4_976_868 and len(test) == 5_077_150, "not D2's rows (its Results: 4,976,868 and 5,077,150)"
    return grid, train, test, pd.concat([c24, c25])


def subsample(y: np.ndarray) -> np.ndarray:
    """fit_pooled's subsample: every spill-day, and dry days kept with default_rng(0) at NEG_FRAC."""
    rng = np.random.default_rng(0)
    return (y == 1) | (rng.random(len(y)) < NEG_FRAC)


def training_rows(train: pd.DataFrame):
    y_all = train["y"].to_numpy()
    keep = np.flatnonzero(subsample(y_all))
    assert len(keep) == 1_569_401, "not D2's subsample (its log: 1,569,401 of 4,976,868 rows used)"
    rows = train.iloc[keep]
    y = rows["y"].to_numpy()
    w = np.where(y == 1, 1.0, 1.0 / NEG_FRAC)
    held = rows["day"].dt.isocalendar().week.astype(int).to_numpy() % 4 == 0   # ISO weeks 4, 8, ..., 52
    return rows, y, w, np.flatnonzero(~held), np.flatnonzero(held)


def standardize(rows: pd.DataFrame, fit_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    s = rows[STATIC].to_numpy(np.float64)[fit_idx]
    return s.mean(0).astype(np.float32), s.std(0).astype(np.float32)


# ------------------------------------------------------------------ stages
def stage_time() -> None:
    grid, train, _, _ = prepare()
    rows, y, w, fit_idx, val_idx = training_rows(train)
    mean, std = standardize(rows, fit_idx)
    x = Inputs(grid, rows, mean, std)
    step(f"training rows {len(fit_idx)}, inner hold-out {len(val_idx)}; {len(fit_idx) // BATCH + 1} batches an epoch")
    net, hist = fit_seed(0, x, y, w, fit_idx, val_idx, max_epochs=1)
    e = hist[0]
    per_seed = MAX_EPOCHS * (e["fit_seconds"] + e["val_seconds"])
    t0 = time.time()
    n = 200_000
    predict([net], Inputs(grid, train.iloc[:n], mean, std), n)
    rate = n / (time.time() - t0)
    print(json.dumps({"epoch_fit_seconds": e["fit_seconds"], "epoch_val_seconds": e["val_seconds"],
                      "max_seconds_per_seed": per_seed, "max_hours_per_seed": per_seed / 3600,
                      "inference_rows_per_second_one_net": round(rate), "threads": torch.get_num_threads()},
                     indent=1))


def stage_train() -> None:
    grid, train, _, _ = prepare()
    rows, y, w, fit_idx, val_idx = training_rows(train)
    mean, std = standardize(rows, fit_idx)
    x = Inputs(grid, rows, mean, std)
    short = (np.isfinite(grid.window(x.ci, x.di)).sum(1) < MIN_FINITE)
    step(f"training rows {len(fit_idx)}, inner hold-out {len(val_idx)}; "
         f"{int(short.sum())} subsampled 2024 rows under the 90% rule (kept: the training rows are D2's)")
    OUT.mkdir(parents=True, exist_ok=True)
    hist = []
    for seed in SEEDS:
        net, h = fit_seed(seed, x, y, w, fit_idx, val_idx)
        torch.save(net.state_dict(), OUT / f"seed{seed}.pt")
        hist += h
        pd.DataFrame(hist).to_csv(f"{DOCS}-training.csv", index=False)
    meta = {"static": STATIC, "mean": mean.tolist(), "std": std.tolist(), "seeds": list(SEEDS),
            "fit_rows": len(fit_idx), "inner_holdout_rows": len(val_idx),
            "under_90pct_training_rows": int(short.sum()),
            "weights": int(sum(p.numel() for p in net.parameters())), "torch": torch.__version__}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    step(f"saved {len(SEEDS)} networks -> {OUT}")


class Challenger(SpillModel):
    """Layer 2 on the network: predict_pooled is the ensemble's probability, read from `p_nn`."""

    def predict_pooled(self, df: pd.DataFrame) -> np.ndarray:
        return np.clip(df["p_nn"].to_numpy(np.float64), EPS, 1 - EPS)


def load_nets() -> tuple[list[Net], dict]:
    meta = json.loads((OUT / "meta.json").read_text())
    nets = []
    for s in meta["seeds"]:
        net = Net()
        net.load_state_dict(torch.load(OUT / f"seed{s}.pt"))
        nets.append(net.eval())
    return nets, meta


def day_total(w: np.ndarray) -> np.ndarray:
    t = np.nansum(w, axis=1)
    t[np.isfinite(w).sum(1) < MIN_HOURS_PER_DAY] = np.nan
    return t


def nansum_or_nan(a: np.ndarray) -> np.ndarray:
    t = np.nansum(a, axis=1)
    t[~np.isfinite(a).any(1)] = np.nan
    return t


def boosted_features(grid: RainGrid, x: Inputs, idx: np.ndarray, frame: pd.DataFrame) -> pd.DataFrame:
    """The boosted model's ten rain features for day d, computed from the 72-hour window x gives
    (days d-2..d) and the ERA5-Land daily totals and antecedent index before it, as
    daily_rain_features would compute them from one hourly series."""
    win = x.window(idx)
    ci, di = x.ci[idx], x.di[idx]
    d2, d1, d0 = day_total(win[:, :24]), day_total(win[:, 24:48]), day_total(win[:, 48:])
    short = np.isnan(d0)

    def peak(width):
        r = np.stack([nansum_or_nan(win[:, t - width + 1:t + 1]) for t in range(48, 72)], axis=1)
        with np.errstate(all="ignore"):
            m = np.nanmax(np.where(np.isfinite(r), r, -np.inf), axis=1)
        m[~np.isfinite(m) | short] = np.nan
        return m

    def era(lo, hi):   # ERA5-Land daily totals for d-lo .. d-hi
        return grid.rain_d[ci[:, None], di[:, None] + np.arange(-lo, -hi + 1)]

    last3 = np.stack([d2, d1, d0], axis=1)
    f = frame.iloc[idx][STATIC].copy()
    f["rain_d"], f["rain_d1"], f["rain_d2"] = d0, d1, d2
    f["rain_3d"] = nansum_or_nan(last3)
    f["rain_7d"] = nansum_or_nan(np.concatenate([era(6, 3), last3], axis=1))
    f["rain_30d"] = nansum_or_nan(np.concatenate([era(29, 3), last3], axis=1))
    f["api"] = (API_DECAY ** 3 * grid.api[ci, di - 3] + API_DECAY ** 2 * np.nan_to_num(d2)
                + API_DECAY * np.nan_to_num(d1) + np.nan_to_num(d0))
    f["max1h_d"] = peak(1)
    f["max3h_d"] = peak(3)
    f["max6h_d"] = peak(6)
    return f[ALL_FEATURES].astype(np.float32)


def week_codes(day: pd.Series) -> np.ndarray:
    iso = day.dt.isocalendar()
    return pd.factorize(iso["year"].astype(int) * 100 + iso["week"].astype(int), sort=True)[0]


def boot_interval(diff: np.ndarray, week: np.ndarray, draws: np.ndarray) -> tuple[float, float]:
    W = draws.shape[1]
    s = np.bincount(week, weights=diff, minlength=W)
    n = np.bincount(week, minlength=W).astype(float)
    stat = s[draws].sum(1) / n[draws].sum(1)
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(lo), float(hi)


def stage_score() -> None:
    path = config.PROCESSED / NINE_PATH.name
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha.startswith(CANDIDATE_SHA), f"{path.name} is not D2's candidate ({sha[:12]})"
    boosted = SpillModel.load(path)
    hold = SpillModel.load(config.PROCESSED / "spill_model_holdout_2025.pkl")
    nets, meta = load_nets()
    mean, std = np.array(meta["mean"], np.float32), np.array(meta["std"], np.float32)
    grid, train, test, _ = prepare()

    # Layer 2, fitted on the challenger's own 2024 predictions over every 2024 row, as D2 fitted its own.
    x24 = Inputs(grid, train, mean, std)
    p24 = predict(nets, x24, len(train)).mean(0)
    ch = Challenger(features=[])
    ch.fit_site_offsets(train.assign(p_nn=p24), prior_strength=PRIOR_STRENGTH, recency=RECENCY)
    ch.trained_on = "Neural challenger: nine English water companies 2024 (EA start/stop files)"
    step("2024 predictions and layer 2")
    flat = train.groupby("company")["y"].mean()
    del x24, p24

    # The 90% rule, then every predictor on the same 2025 rows.
    x = Inputs(grid, test, mean, std)
    finite = np.isfinite(grid.window(x.ci, x.di)).sum(1)
    keep = finite >= MIN_FINITE
    dropped = test.loc[~keep, "company"].value_counts().reindex(NINE, fill_value=0)
    print("\n=== 2025 rows dropped by the 90% rule ===", int((~keep).sum()), dropped.to_dict())
    test = test.loc[keep].reset_index(drop=True)
    x = Inputs(grid, test, mean, std)
    seeds = predict(nets, x, len(test))
    p_nn = seeds.mean(0)
    t = test.assign(p_nn=p_nn)
    preds = {
        "challenger": ch.predict(t),
        "boosted": boosted.predict(test),
        "current hold-out": hold.predict(test),
        "company flat rate": test["company"].map(flat).to_numpy(),
        "challenger, layer 1 only": ch.predict_pooled(t),
        "boosted, layer 1 only": boosted.predict_pooled(test),
        **{f"challenger seed {s}, layer 1 only": np.clip(seeds[j], EPS, 1 - EPS) for j, s in enumerate(meta["seeds"])},
    }
    step("2025 predictions")
    y = test["y"].to_numpy()
    company = test["company"].to_numpy()
    week = week_codes(test["day"])
    draws = np.random.default_rng(0).integers(0, week.max() + 1, size=(N_BOOT, week.max() + 1))
    diff = (preds["challenger"] - y) ** 2 - (preds["boosted"] - y) ** 2

    rows, rel, diffs = [], [], []
    for comp in [*NINE, "all nine"]:
        m = np.ones(len(y), bool) if comp == "all nine" else company == comp
        for k, p in preds.items():
            s = scores(y[m], p[m])
            rows.append({"company": comp, "predictor": k, "rows": s["n"], "base_rate": s["base_rate"],
                         "brier": s["brier"], "auc": s["auc"], "ece": ece(y[m], p[m]), "log_loss": s["log_loss"]})
        for k in ("challenger", "boosted", "current hold-out"):
            rel.append(reliability_table(y[m], preds[k][m]).assign(company=comp, predictor=k))
        lo, hi = boot_interval(diff[m], week[m], draws)
        diffs.append({"company": comp, "rows": int(m.sum()),
                      "brier_challenger": float(((preds["challenger"][m] - y[m]) ** 2).mean()),
                      "brier_boosted": float(((preds["boosted"][m] - y[m]) ** 2).mean()),
                      "difference": float(diff[m].mean()), "ci_low": lo, "ci_high": hi})
    res, dif = pd.DataFrame(rows), pd.DataFrame(diffs)
    pd.set_option("display.width", 220)
    print("\n=== 2025, ERA5-Land rain, per company ===")
    print(res.round(5).to_string(index=False))
    print("\n=== Brier difference, challenger minus boosted, 95% week-cluster bootstrap ===")
    print(dif.to_string(index=False, float_format=lambda v: f"{v:.5f}"))

    # Forecast rain: days d, d-1, d-2 from the forecasts issued k, k-1, k-2 days ahead (floored at 0),
    # everything before from ERA5-Land, for both models (verify_leads.py's split).
    lead_files = sorted(f for d in RAIN_DIRS for f in (config.CACHE / d).glob("leads_*_2025.parquet"))
    lf = pd.concat((pd.read_parquet(f) for f in lead_files), ignore_index=True)
    lf = lf.sort_values(["cell_lat", "cell_lon", "lead", "time"])
    lf = lf[~lf.duplicated(["cell_lat", "cell_lon", "lead", "time"], keep="last")]
    lkeys = pd.Index(np.unique(_key(lf["cell_lat"], lf["cell_lon"])))
    L = np.full((len(LEADS), len(lkeys), grid.n_hours), np.nan, np.float32)
    li = lkeys.get_indexer(_key(lf["cell_lat"], lf["cell_lon"]))
    hi = ((lf["time"] - T0) // pd.Timedelta(hours=1)).to_numpy()
    lead = lf["lead"].to_numpy()
    ok = np.isin(lead, LEADS) & (hi >= 0) & (hi < grid.n_hours)
    L[lead[ok], li[ok], hi[ok]] = lf["precip_mm"].to_numpy()[ok]
    del lf
    to_lead = lkeys.get_indexer(grid.keys)          # grid cell -> lead cell, -1 if none
    in_lead = np.flatnonzero(to_lead[x.ci] >= 0)
    print(f"\n=== Lead rows: {len(lead_files)} lead files, {len(lkeys)} cells; "
          f"{len(in_lead)} of the 2025 rows in lead cells, "
          f"{test.iloc[in_lead]['site_id'].nunique()} overflows ===")

    # A check of boosted_features on ERA5-Land: it should give back the rows' own features.
    chk = boosted_features(grid, x, in_lead[:200_000], test)
    ref = test.iloc[in_lead[:200_000]][ALL_FEATURES]
    feat_gap = {c: float(np.nanmax(np.abs(chk[c].to_numpy() - ref[c].to_numpy()))) for c in ALL_FEATURES}
    print("largest gap, recomputed ERA5-Land features vs the rows' own:", {k: round(v, 4) for k, v in feat_gap.items()})

    lead_rows = []
    for k in LEADS:
        def lead_window(ci, di, k=k):
            out = np.empty((len(ci), HOURS), np.float32)
            lc = to_lead[ci]
            for j in (2, 1, 0):                      # day d-j from the forecast issued k-j days ahead
                pos = (2 - j) * 24
                out[:, pos:pos + 24] = L[max(k - j, 0)][lc[:, None], ((di - j) * 24)[:, None] + np.arange(24)]
            return out
        xl = Inputs(grid, test.iloc[in_lead], mean, std, window=lead_window)
        win = xl.window(np.arange(len(in_lead)))
        okk = (np.isfinite(win).sum(1) >= MIN_FINITE) & np.isfinite(day_total(win[:, 48:]))
        sel = np.flatnonzero(okk)
        rows_k = test.iloc[in_lead[sel]].reset_index(drop=True)
        xk = Inputs(grid, rows_k, mean, std, window=lead_window)
        pk_nn = predict(nets, xk, len(sel)).mean(0)
        pc = ch.predict(rows_k.assign(p_nn=pk_nn))
        fb = boosted_features(grid, xk, np.arange(len(sel)), rows_k).fillna(0.0)
        fb["site_id"] = rows_k["site_id"].to_numpy()
        pb = boosted.predict(fb)
        yk = rows_k["y"].to_numpy()
        dk = (pc - yk) ** 2 - (pb - yk) ** 2
        lo, hi = boot_interval(dk, week[in_lead[sel]], draws)
        sc, sb = scores(yk, pc), scores(yk, pb)
        lead_rows.append({"lead": k, "rows": len(sel), "dropped": int((~okk).sum()), "base_rate": float(yk.mean()),
                          "brier_challenger": sc["brier"], "brier_boosted": sb["brier"],
                          "auc_challenger": sc["auc"], "auc_boosted": sb["auc"],
                          "difference": float(dk.mean()), "ci_low": lo, "ci_high": hi,
                          **{f"brier_challenger_{c}": float(((pc - yk) ** 2)[rows_k["company"].to_numpy() == c].mean())
                             for c in NINE if (rows_k["company"] == c).any()},
                          **{f"brier_boosted_{c}": float(((pb - yk) ** 2)[rows_k["company"].to_numpy() == c].mean())
                             for c in NINE if (rows_k["company"] == c).any()}})
        step(f"lead {k}: {len(sel)} rows, challenger {sc['brier']:.5f}, boosted {sb['brier']:.5f}")
    leads = pd.DataFrame(lead_rows)
    print("\n=== Forecast rain, leads 0-4 (all nine) ===")
    print(leads[["lead", "rows", "dropped", "base_rate", "brier_challenger", "brier_boosted", "auc_challenger",
                 "auc_boosted", "difference", "ci_low", "ci_high"]].to_string(index=False, float_format=lambda v: f"{v:.5f}"))


    # Condition 5: more rain in the 72-hour window must not lower the risk.
    p0 = preds["challenger"]
    mono = {}
    for name, fn in (("plus 1 mm every hour", lambda mm: mm + 1.0), ("double every hour", lambda mm: mm * 2.0)):
        p1 = ch.predict(test.assign(p_nn=predict(nets, x, len(test), transform=fn).mean(0)))
        drop = p0 - p1
        mono[name] = {"rows": len(test), "lowered": int((drop > 0).sum()), "lowered_share": float((drop > 0).mean()),
                      "lowered_by_over_1e-6": int((drop > 1e-6).sum()), "largest_drop": float(drop.max()),
                      "pass": bool((drop > 0).mean() < 0.005 and drop.max() <= 0.01)}
        step(f"condition 5, {name}: {mono[name]}")

    # Condition 6: the numpy forward pass for every overflow of the built site, five days.
    ov_path = Path(sys.argv[sys.argv.index("--overflows") + 1]) if "--overflows" in sys.argv \
        else config.ROOT / "site" / "data" / "overflows.geojson"
    n_ov = len(json.loads(ov_path.read_text())["features"])
    n6 = n_ov * 5
    pick = np.random.default_rng(0).integers(0, len(test), n6)
    seq6, days6, st6 = (a.numpy() for a in x.tensors(pick))
    sds = [{k: v.numpy() for k, v in net.state_dict().items()} for net in nets]
    t0 = time.time()
    _ = np.mean([1 / (1 + np.exp(-numpy_logit(sd, seq6, days6, st6))) for sd in sds], axis=0)
    t6 = time.time() - t0
    with torch.inference_mode():
        gap = max(float(np.abs(numpy_logit(sd, seq6[:1000], days6[:1000], st6[:1000])
                               - net(*(torch.from_numpy(a[:1000]) for a in (seq6, days6, st6))).numpy()).max())
                  for sd, net in zip(sds, nets, strict=True))
    speed = {"overflows": n_ov, "rows": n6, "seconds": t6, "pass": t6 < 60,
             "numpy_vs_torch_max_logit_gap_1000_rows": gap, "file": str(ov_path)}
    step(f"condition 6: {speed}")

    # The conditions.
    b = res.set_index(["company", "predictor"])
    d = dif.set_index("company")
    c1 = bool(d.loc["all nine", "difference"] < 0 and d.loc["all nine", "ci_high"] < 0)
    worse = [c for c in NINE if d.loc[c, "difference"] > 0 and d.loc[c, "ci_low"] > 0]
    c3 = [int(r.lead) for r in leads.itertuples() if r.brier_challenger > r.brier_boosted]
    c4 = [c for c in NINE if not (b.loc[(c, "challenger"), "ece"] <= b.loc[(c, "boosted"), "ece"]
                                  or b.loc[(c, "challenger"), "ece"] <= 0.02)]
    cond = {"1 real gain overall": c1, "2 no company clearly worse": not worse,
            "3 not worse with forecast rain": not c3, "4 reliability": not c4,
            "5 more rain does not lower the risk": all(v["pass"] for v in mono.values()),
            "6 cheap to run": speed["pass"]}
    print("\n=== Conditions ===")
    for k, v in cond.items():
        print(f"{k}: {'PASS' if v else 'FAIL'}")
    print("companies clearly worse:", worse, "| leads worse:", c3, "| ECE failures:", c4)
    print("ADOPT" if all(cond.values()) else "DO NOT ADOPT")

    res.to_csv(f"{DOCS}-scores.csv", index=False)
    dif.to_csv(f"{DOCS}-differences.csv", index=False)
    pd.concat(rel).to_csv(f"{DOCS}-reliability.csv", index=False)
    leads.to_csv(f"{DOCS}-leads.csv", index=False)
    Path(f"{DOCS}-checks.json").write_text(json.dumps(
        {"dropped_by_90pct_rule": {"total": int(dropped.sum()), **{k: int(v) for k, v in dropped.items()}},
         "rows_scored": len(test), "era_feature_recompute_gap": feat_gap, "condition_5": mono, "condition_6": speed,
         "layer_2": {"overflows": len(ch.site_offset), "prior_strength": PRIOR_STRENGTH, "recency": RECENCY},
         "conditions": cond, "adopt": all(cond.values())}, indent=1))
    step("tables written")


if __name__ == "__main__":
    if LOCAL_TZ != "UTC":   # its day indices count UTC days from T0; local days would land summer days one early
        sys.exit("train_nn.py indexes UTC days and the model now cuts UK local days (docs/DAY-BOUNDARY-TEST-2026-10.md): "
                 "run it from the commit its record names")
    {"time": stage_time, "train": stage_train, "score": stage_score}[sys.argv[1]]()
