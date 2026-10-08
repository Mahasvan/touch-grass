import random

from touch_grass import persona, router, state
from touch_grass.cli import _synthetic_graph


def test_anti_cost_prefers_footway_over_primary():
    rng = random.Random(0)
    foot = [router.anti_cost(100, "footway", rng) for _ in range(50)]
    art = [router.anti_cost(100, "primary", rng) for _ in range(50)]
    assert max(foot) < min(art)


def test_geofence_advances_and_finishes():
    d = state.Derive([(45.5, -122.0), (45.51, -122.0)], ["a", "b"])
    assert d.update(0, 0) is None          # nowhere near
    assert d.update(45.5, -122.0) == "a"   # inside geofence 1
    assert d.update(45.5, -122.0) is None  # already consumed
    assert d.update(45.51, -122.0) == "b"
    assert d.done and d.update(45.51, -122.0) is None


def test_route_reaches_all_waypoints():
    g = router.weighted_graph(_synthetic_graph(seed=1), seed=1)
    rng = random.Random(1)
    pois = rng.sample(list(g.nodes), 8)
    start = rng.choice(list(g.nodes))
    wps = router.pick_waypoints(g, pois, start, k=3)
    route = router.derive_route(g, [start, *wps])
    assert set(wps) <= set(route) and route[0] == start


def test_compass_and_riddle():
    assert persona.compass(0) == "north" and persona.compass(90) == "east"
    r = persona.template_riddle("a fountain", (45.5, -122), (45.51, -122), 0)
    assert "a fountain" in r
