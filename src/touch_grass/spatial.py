"""Spatial data engine: offline walk graph + POI extraction via OSMnx."""

from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd

CACHE = Path.home() / ".cache" / "touch-grass"

# POI tags worth wandering toward
POI_TAGS = {
    "historic": True,
    "leisure": ["park", "garden", "nature_reserve"],
    "natural": ["water", "tree", "wood"],
    "amenity": ["fountain", "arts_centre"],
    "tourism": ["artwork", "attraction"],
}

WALK_SPEED_MPH = 3.0


def walk_radius_m(minutes: float) -> float:
    """Max reachable distance at 3 mph for a round-ish derive."""
    return walk_distance_m(minutes) / 2


def walk_distance_m(minutes: float) -> float:
    """Total distance walkable in the time budget at 3 mph."""
    return minutes / 60 * WALK_SPEED_MPH * 1609.34


def load_graph(place: str, dist_m: float | None = None, point=None) -> nx.MultiDiGraph:
    """Load a cached pedestrian graph, or download and cache it (needs net once)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = place.lower().replace(" ", "_").replace(",", "")[:60]
    path = CACHE / f"{key}.graphml"
    if path.exists():
        return ox.load_graphml(path)
    if point is not None and dist_m:
        g = ox.graph_from_point(point, dist=dist_m, network_type="walk")
    else:
        g = ox.graph_from_place(place, network_type="walk")
    ox.save_graphml(g, path)
    return g


def extract_pois(place: str) -> pd.DataFrame:
    """Pull POI features for a place. Cached to parquet after first fetch."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = place.lower().replace(" ", "_").replace(",", "")[:60]
    path = CACHE / f"{key}_pois.pkl"
    if path.exists():
        return pd.read_pickle(path)
    pois = ox.features_from_place(place, POI_TAGS)
    pois.to_pickle(path)
    return pois


def describe_poi(row: pd.Series) -> str:
    """Human-readable POI description from OSM tags."""
    name = row.get("name")
    if isinstance(name, str) and name:
        return name
    for k in ("historic", "natural", "amenity", "tourism", "leisure"):
        v = row.get(k)
        if isinstance(v, str):
            return f"a {v.replace('_', ' ')}" if k != "leisure" else f"a {v}"
    return "an unmarked landmark"
