"""CLI: `derive` plans a walk, `track` follows live GPS, `demo` simulates."""

import argparse
import pickle
import random
import subprocess
import sys

import networkx as nx

from . import persona, router, spatial, state


def _synthetic_graph(seed: int = 0) -> nx.MultiDiGraph:
    """Grid 'city': arterial spine + winding footways, fake POI nodes."""
    rng = random.Random(seed)
    g = nx.MultiDiGraph()
    n = 20
    scale = 1e-4  # ~11 m per cell
    for i in range(n):
        for j in range(n):
            g.add_node(i * n + j, x=j * scale, y=45.5 - i * scale)
    for i in range(n):
        for j in range(n):
            node = i * n + j
            for di, dj in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                ni, nj = i + di, j + dj
                if 0 <= ni < n and 0 <= nj < n:
                    nbr = ni * n + nj
                    hwy = "primary" if i == 0 else ("footway" if rng.random() < 0.3 else "residential")
                    length = 11.0 * rng.uniform(0.9, 1.6 if hwy == "footway" else 1.1)
                    g.add_edge(node, nbr, length=length, highway=hwy)
    return g


def demo(seed: int | None = None) -> None:
    g = router.weighted_graph(_synthetic_graph(seed))
    nodes = list(g.nodes)
    rng = random.Random(seed)
    poi_nodes = rng.sample(nodes, 12)
    descs = {n: f"landmark-{n}" for n in poi_nodes}

    start = rng.choice(nodes)
    waypoints = router.pick_waypoints(g, poi_nodes, start, k=4)
    route = router.derive_route(g, [start, *waypoints])

    d = state.Derive(
        [(g.nodes[n]["y"], g.nodes[n]["x"]) for n in waypoints],
        [descs[n] for n in waypoints],
    )
    heading = 0.0
    print(f"Dérive begins at node {start}. {len(waypoints)} waypoints, "
          f"route of {len(route)} steps.\n")
    for step, node in enumerate(route):
        lat, lon = g.nodes[node]["y"], g.nodes[node]["x"]
        nxt = route[step + 1] if step + 1 < len(route) else node
        heading = persona.bearing(lat, lon, g.nodes[nxt]["y"], g.nodes[nxt]["x"])
        arrived = d.update(lat, lon)
        if arrived:
            print(f"[gps] reached {arrived}")
            if not d.done:
                tgt = d.target
                nxt_idx = waypoints[d.index]
                clue = persona.riddle(
                    d.descriptions[d.index], (lat, lon), tgt, heading
                )
                print(f"[guide] {clue}\n")
    print("Dérive complete. You touched grass at:", ", ".join(d.history))


SESSION = spatial.CACHE / "session.pkl"


def _route_length(g: nx.MultiDiGraph, route: list[int]) -> float:
    return sum(
        min(e.get("length", 0) for e in g[a][b].values())
        for a, b in zip(route, route[1:])
    )


def derive(place: str, minutes: float, seed: int | None = None) -> None:
    budget = spatial.walk_distance_m(minutes)
    g = spatial.load_graph(place, dist_m=budget * 0.8)
    g = router.weighted_graph(g, seed)
    pois = spatial.extract_pois(place)
    desc_by_node = {}
    for _, r in pois.iterrows():
        if r.geometry.geom_type == "Point":
            desc_by_node[router.nearest_node(g, r.geometry.y, r.geometry.x)] = \
                spatial.describe_poi(r)
    poi_nodes = list(desc_by_node)
    if len(poi_nodes) < 3:
        raise SystemExit(f"Only {len(poi_nodes)} POIs found near {place}; widen the area.")
    center = g.nodes[next(iter(g.nodes))]
    start = router.nearest_node(g, center["y"], center["x"])

    waypoints = router.pick_waypoints(g, poi_nodes, start, k=4)
    route = router.derive_route(g, [start, *waypoints])
    # trim tail until the wander fits the budget; 1.5x slack since the
    # anti-route is deliberately longer than a direct walk would be
    while len(waypoints) > 1 and _route_length(g, route) > budget * 1.5:
        waypoints.pop()
        route = router.derive_route(g, [start, *waypoints])
    dist = _route_length(g, route)

    d = state.Derive(
        [(g.nodes[n]["y"], g.nodes[n]["x"]) for n in waypoints],
        [desc_by_node[n] for n in waypoints],
    )
    SESSION.parent.mkdir(parents=True, exist_ok=True)
    SESSION.write_bytes(pickle.dumps({"derive": d, "route": route}))
    print(f"Dérive: {len(waypoints)} waypoints, ~{dist/1609:.2f} mi "
          f"(budget {budget/1609:.2f} mi).")
    for n in waypoints:
        print(f"  - {desc_by_node[n]} @ ({g.nodes[n]['y']:.5f}, {g.nodes[n]['x']:.5f})")
    print("\nRun `touch-grass track` and feed 'lat,lon' lines on stdin.")


def track() -> None:
    """Follow GPS fixes from stdin ('lat,lon' per line); speak riddles."""
    if not SESSION.exists():
        raise SystemExit("No session — run `touch-grass derive <place>` first.")
    d: state.Derive = pickle.loads(SESSION.read_bytes())["derive"]
    prev = None
    print("Tracking. Feed 'lat,lon' lines; Ctrl-D to stop.", file=sys.stderr)
    for line in sys.stdin:
        try:
            lat, lon = (float(x) for x in line.split(","))
        except ValueError:
            continue
        heading = persona.bearing(*prev, lat, lon) if prev else 0.0
        prev = (lat, lon)
        arrived = d.update(lat, lon)
        if arrived is None:
            continue
        msg = f"You found {arrived}."
        if not d.done:
            msg += " " + persona.riddle(
                d.descriptions[d.index], (lat, lon), d.target, heading)
        print(msg)
        if sys.platform == "darwin":
            subprocess.run(["say", msg], check=False)
        if d.done:
            print("Dérive complete. You touched grass at:", ", ".join(d.history))
            break


def main() -> None:
    p = argparse.ArgumentParser(prog="touch-grass",
                                description="The Anti-Router wanderlust agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("derive", help="plan a dérive for a place (caches OSM data)")
    d.add_argument("place")
    d.add_argument("--minutes", type=float, default=45)
    d.add_argument("--seed", type=int, default=None)
    s = sub.add_parser("demo", help="offline simulation on a synthetic city")
    s.add_argument("--seed", type=int, default=None)
    sub.add_parser("track", help="follow live GPS fixes from stdin")
    args = p.parse_args()
    if args.cmd == "demo":
        demo(args.seed)
    elif args.cmd == "track":
        track()
    else:
        derive(args.place, args.minutes, args.seed)


if __name__ == "__main__":
    main()
