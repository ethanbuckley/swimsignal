"""Cycle ordering must not change forecasts when Python's hash seed changes."""
import json
import os
import subprocess
import sys


def test_cyclic_upstream_lengths_do_not_depend_on_process_hash_seed():
    source = """
import json
import networkx as nx
from dipcast.network.rivers import RiverNetwork
net = RiverNetwork.__new__(RiverNetwork)
net.graph = nx.DiGraph()
for a, b, length in [('head', 'alpha', 1000), ('alpha', 'beta', 200),
                     ('beta', 'gamma', 300), ('gamma', 'alpha', 400), ('gamma', 'out', 500)]:
    net.graph.add_edge(a, b, length=length)
print(json.dumps(net._compute_upstream_m(quiet=True), sort_keys=True))
"""
    results = [json.loads(subprocess.check_output([sys.executable, '-c', source],
               env={**os.environ, 'PYTHONHASHSEED': str(seed)}, text=True)) for seed in (1, 2, 13)]
    assert results[0] == results[1] == results[2]
    assert results[0]['out'] >= 1000


def test_lake_snap_and_outlet_do_not_depend_on_process_hash_seed():
    """A pin nearest a node where lake links meet is equally near all of them, and a lake with two
    outlets of equal upstream length has no larger one. Both ties were settled in set order, so
    Windermere, Lakeside YMCA took a different link under PYTHONHASHSEED 1 and 2 (16 Oct 2026)."""
    source = """
import json
import geopandas as gpd
from shapely.geometry import LineString
from dipcast.model import transport
from dipcast.network.rivers import RiverNetwork
# Lake links leave node j to the east, south and south-east, 1000 m each; one comes in from the north.
links = [('Kq', 'n', 'j', [(0, 1000), (0, 0)]), ('Kz', 'j', 'p', [(0, 0), (1000, 0)]),
         ('Ka', 'j', 'q', [(0, 0), (0, -1000)]), ('Km', 'j', 'r', [(0, 0), (600, -800)])]
net = RiverNetwork.from_links(gpd.GeoDataFrame(
    [{'id': i, 'flow_direction': 'in direction', 'form': 'lake', 'fictitious': False,
      'watercourse_name': 'Mere', 'watercourse_name_alternative': None, 'start_node': s, 'end_node': e,
      'geometry': LineString(xy)} for i, s, e, xy in links], crs=27700))
ids = {i for i, *_ in links}
snap = transport._snap_to_links(net, -100.0, 0.0, ids)   # 100 m west of j: all four links tie
print(json.dumps([snap.link_id, snap.dist_m, transport._lake_outlet(net, ids)]))
"""
    results = {tuple(json.loads(subprocess.check_output([sys.executable, '-c', source],
               env={**os.environ, 'PYTHONHASHSEED': str(seed)}, text=True))) for seed in range(1, 9)}
    # The first by link id, and of the three outlets (each 2000 m of lake upstream) the first by node id.
    assert results == {('Ka', 100.0, 'p')}
