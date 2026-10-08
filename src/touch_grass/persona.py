"""Persona agent: turn route segments + telemetry into navigational riddles.

Templates run with zero deps. If Ollama is running locally
(OLLAMA_HOST, default http://localhost:11434) and TOUCH_GRASS_MODEL names a
pulled model, riddles go through it instead — daemon holds weights between
calls, so nothing heavy lives in this process.
"""

import json
import math
import os
import urllib.request

SYSTEM = (
    "You are a wanderlust guide. Give one short navigational riddle that "
    "forces the walker to observe their surroundings. Never name distances "
    "in meters or say 'turn left in X feet' — use landmarks, sun, treelines."
)

COMPASS = ["north", "north-east", "east", "south-east",
           "south", "south-west", "west", "north-west"]


def compass(heading_deg: float) -> str:
    return COMPASS[round(heading_deg / 45) % 8]


def bearing(lat1, lon1, lat2, lon2) -> float:
    """Initial bearing degrees between two coords."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def template_riddle(target_desc: str, from_xy, to_xy, heading_deg: float) -> str:
    b = bearing(from_xy[0], from_xy[1], to_xy[0], to_xy[1])
    turn = "keep walking" if abs(b - heading_deg) < 45 else f"turn toward the {compass(b)}"
    return (
        f"Face {compass(heading_deg)}. Somewhere {compass(b)} of here waits "
        f"{target_desc} — {turn}, follow the quietest path you can find, "
        f"and let me know when you arrive."
    )


def _ollama_riddle(target_desc: str, from_xy, to_xy, heading_deg: float) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    body = json.dumps({
        "model": os.environ["TOUCH_GRASS_MODEL"],
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": (
                f"Walker is facing {compass(heading_deg)}. Next landmark: "
                f"{target_desc}, which lies "
                f"{compass(bearing(*from_xy, *to_xy))}. Give them the riddle."
            )},
        ],
        "stream": False,
        "keep_alive": "5m",  # drop weights between waypoints to save battery/RAM
    }).encode()
    req = urllib.request.Request(
        f"{host}/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["message"]["content"].strip()


def riddle(target_desc: str, from_xy, to_xy, heading_deg: float) -> str:
    """Ollama riddle if a model is configured and reachable, else template."""
    if not os.environ.get("TOUCH_GRASS_MODEL"):
        return template_riddle(target_desc, from_xy, to_xy, heading_deg)
    try:
        return _ollama_riddle(target_desc, from_xy, to_xy, heading_deg)
    except OSError:
        return template_riddle(target_desc, from_xy, to_xy, heading_deg)
