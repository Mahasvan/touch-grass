"""State manager: geofenced waypoints, LLM wakes only on arrival."""

import math
from dataclasses import dataclass, field

GEOFENCE_M = 15.0


def dist_m(lat1, lon1, lat2, lon2) -> float:
    """Equirectangular approx — fine under a few km."""
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6_371_000


@dataclass
class Derive:
    """A walking dérive: ordered waypoint coords + descriptions."""
    waypoints: list[tuple[float, float]]  # (lat, lon)
    descriptions: list[str]
    index: int = 0
    history: list[str] = field(default_factory=list)

    @property
    def target(self):
        return self.waypoints[self.index] if self.index < len(self.waypoints) else None

    @property
    def done(self) -> bool:
        return self.index >= len(self.waypoints)

    def update(self, lat: float, lon: float) -> str | None:
        """Feed a GPS fix. Returns a trigger signal when a geofence is crossed."""
        if self.done:
            return None
        if dist_m(lat, lon, *self.target) <= GEOFENCE_M:
            desc = self.descriptions[self.index]
            self.history.append(desc)
            self.index += 1
            return desc  # caller should now wake the LLM for the next leg
        return None
