"""Bounded exploratory shore-margin band comparison; see docs/SATELLITE-SHORE-BANDS-2026-11.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lake_algae_sat_eval'))
import protocol as pr  # noqa: E402
import stac  # noqa: E402
from net import Capped  # noqa: E402
from satellite_shore_margin import kept, site_tiles  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / 'Documents/GitHub/swimsignal-private/lake-algae-sat/out'


def digest(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(CACHE)).encode())
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
    return h.hexdigest()


def input_files():
    return [CACHE / 'features.parquet', *CACHE.glob('cores/*.npz'), *CACHE.glob('items/*.json'),
            *CACHE.glob('scl/*/*.npz')]


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    fingerprint = digest(input_files())
    candidates = defaultdict(list)
    sites = pr.lake_sites(ROOT / 'data/raw/bathing_waters_inland.json').set_index('bw_id')
    for core_path in sorted((CACHE / 'cores').glob('*.npz')):
        sid = core_path.stem
        if sid not in sites.index:
            raise ValueError(f'Unknown site {sid}')
        items = {it['id']: it for it in json.loads((CACHE / 'items' / f'{sid}.json').read_text())}
        with np.load(core_path) as saved:
            for tile, wins in site_tiles(CACHE, sid):
                piece, site = pr.site_water(pr.water_mask(np.stack([w for _, w, _ in wins])), wins[0][2])
                one, two = kept(piece, site, 1), kept(piece, site, 2)
                key = tile.replace('-', '_')
                if key not in saved or not np.array_equal(one, saved[key]):
                    raise ValueError(f'Mask mismatch {sid} {tile}')
                if not pr.passes_size_rule(one) or not pr.passes_size_rule(two):
                    continue
                for item_id, scl, _ in wins:
                    if pr.scene_clear(scl, one)[1] and pr.scene_clear(scl, two)[1]:
                        it = items[item_id]
                        candidates[sid].append({'site': sid, 'tile': tile, 'id': item_id,
                                                'date': it['properties']['datetime'],
                                                'lat': float(sites.loc[sid, 'lat']), 'lon': float(sites.loc[sid, 'lon'])})
    ids = sorted(candidates)
    counts = {sid: 0 for sid in ids}
    while sum(counts.values()) < 50:
        progress = False
        for sid in ids:
            if counts[sid] < len(candidates[sid]) and sum(counts.values()) < 50:
                counts[sid] += 1
                progress = True
        if not progress:
            break
    selected = []
    for sid in ids:
        choices = sorted(candidates[sid], key=lambda x: (x['date'], x['id']))
        n = counts[sid]
        for i in range(n):
            selected.append(choices[((2 * i + 1) * len(choices)) // (2 * n)])
    if fingerprint != digest(input_files()):
        raise ValueError('Inputs changed during selection')
    result = {'fingerprint_sha256': fingerprint, 'input_file_count': len(input_files()), 'selected': selected,
              'eligible_counts': {sid: len(candidates[sid]) for sid in ids}}
    (out / 'selection.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f"Selected {len(selected)} scenes across {len(ids)} sites; inputs unchanged; selection frozen at {out / 'selection.json'}")


def read_bands(out):
    selection = json.loads((out / 'selection.json').read_text())
    before = digest(input_files())
    if before != selection['fingerprint_sha256']:
        raise ValueError('Inputs changed since selection')
    ledger = out / 'network.jsonl'
    if ledger.exists():
        raise ValueError('A network run already exists; no retry under this protocol')
    net = Capped(ledger=ledger, max_requests=300, max_requests_total=300,
                 max_bytes=150 * 1024**2, max_bytes_total=150 * 1024**2)
    rows = []
    try:
        for rec in selection['selected']:
            sid, tile, item_id = rec['site'], rec['tile'], rec['id']
            items = {it['id']: it for it in json.loads((CACHE / 'items' / f'{sid}.json').read_text())}
            it = items[item_id]
            wins = next(wins for t, wins in site_tiles(CACHE, sid) if t == tile)
            piece, site = pr.site_water(pr.water_mask(np.stack([w for _, w, _ in wins])), wins[0][2])
            one, two = kept(piece, site, 1), kept(piece, site, 2)
            with np.load(CACHE / 'cores' / f'{sid}.npz') as saved:
                if not np.array_equal(one, saved[tile.replace('-', '_')]):
                    raise ValueError(f'Mask mismatch {sid} {tile}')
            scl = next(w for i, w, _ in wins if i == item_id)
            # Check metadata before a network request.
            for asset in ('red', 'rededge1'):
                b = it['assets'][asset]['raster:bands'][0]
                if 'scale' not in b or 'offset' not in b:
                    raise ValueError(f'Missing scale or offset: {item_id} {asset}')
            b4, b5 = stac.site_bands(net, it, rec['lon'], rec['lat'])
            index = pr.ndci(pr.b4_to_20m(pr.reflectance(b4, it['assets']['red']['raster:bands'][0])),
                            pr.reflectance(b5, it['assets']['rededge1']['raster:bands'][0]))
            a = pr.scene_reading(scl, one, index)[2]
            b = pr.scene_reading(scl, two, index)[2]
            rows.append({**rec, 'one': None if not np.isfinite(a) else float(a),
                         'two': None if not np.isfinite(b) else float(b)})
            (out / 'partial.json').write_text(json.dumps(rows, indent=2) + '\n')
            print(f"{len(rows)}/{len(selection['selected'])} {sid} {item_id}", flush=True)
    finally:
        after = digest(input_files())
        (out / 'run.json').write_text(json.dumps({'network': net.summary(), 'before': before, 'after': after,
                                                 'completed_scenes': len(rows)}, indent=2) + '\n')
        if after != before:
            raise ValueError('Inputs changed during network run')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['prepare', 'read'])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.step == 'prepare' else read_bands)(args.out)
