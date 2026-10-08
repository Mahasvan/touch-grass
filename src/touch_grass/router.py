"""The Anti-Router: penalize arterials, reward winding footways."""

import math
import random

import networkx as nx

# cost multiplier per OSM highway class
HIGHWAY_PENALTY = {
    "motorway": 50, "trunk": 30, "primary": 12, "secondary": 6,
    "tertiary": 3, "unclassified": 1.5, "residential": 1.2,
    "living_street": 0.9, "cycleway": 0.8, "footway": 0.5,
    "path": 0.4, "pedestrian": 0.4, "steps": 0.6, "track": 0.7,
    "service": 1.0, "alley": 0.3,
}


def anti_cost(length: float, highway, rng: random.Random) -> float:
    """Wandering cost: short-but-boring is expensive, winding is cheap."""
    if isinstance(highway, list):
        highway = highway[0] if highway else "residential"
    penalty = HIGHWAY_PENALTY.get(highway, 1.0)
    # ponytail: tortuosity proxy — long unbroken edges are usually straight
    # arterials; upgrade to real curvature scoring if geometry available.
    if length > 80:
        penalty *= 1.5
    jitter = rng.uniform(0.85, 1.15)  # keeps runs unpredictable
    return length * penalty * jitter


def weighted_graph(g: nx.MultiDiGraph, seed: int | None = None) -> nx.MultiDiGraph:
    rng = random.Random(seed)
    for _, _, _, data in g.edges(keys=True, data=True):
        data["anti_cost"] = anti_cost(
            data.get("length", 1.0), data.get("highway"), rng
        )
    return g


def nearest_node(g: nx.MultiDiGraph, lat: float, lon: float) -> int:
    """Closest node by equirectangular distance. Fine for walk-scale graphs."""
    cos = math.cos(math.radians(lat))
    return min(g.nodes, key=lambda n:
               ((g.nodes[n]["y"] - lat) ** 2 + ((g.nodes[n]["x"] - lon) * cos) ** 2))


def pick_waypoints(g: nx.MultiDiGraph, poi_nodes: list[int], start: int,
                   k: int = 4) -> list[int]:
    """Greedy max-min spread: each next POI is farthest from those chosen."""
    chosen = [start]
    pool = list(dict.fromkeys(poi_nodes))
    while pool and len(chosen) <= k:
        best = max(
            pool,
            key=lambda n: min(
                nx.shortest_path_length(g, c, n, weight="anti_cost",
                                        method="dijkstra") if nx.has_path(g, c, n) else -1
                for c in chosen
            ),
        )
        chosen.append(best)
        pool.remove(best)
    return chosen[1:]


def derive_route(g: nx.MultiDiGraph, waypoints: list[int]) -> list[int]:
    """Concatenate anti-cost shortest paths through the waypoints."""
    route = []
    for a, b in zip(waypoints, waypoints[1:]):
        seg = nx.shortest_path(g, a, b, weight="anti_cost")
        route.extend(seg if not route else seg[1:])
    return route
