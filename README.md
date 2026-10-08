# touch-grass — the Anti-Router

Offline-first wanderlust agent: plans exploratory pedestrian dérives
(scavenger-hunt walks) from cached OpenStreetMap data, then narrates
navigational riddles instead of turn-by-turn directions.

## Setup

```sh
uv sync                    # core deps (osmnx only — stays light)
```

For LLM riddles, run [Ollama](https://ollama.com) separately and set
`TOUCH_GRASS_MODEL` (e.g. `qwen3:4b`). The daemon holds the weights; this
package only talks HTTP to localhost — no heavy deps, no model in RAM.

## Usage

```sh
uv run touch-grass demo                       # offline sim, synthetic city
uv run touch-grass derive "Portland, Oregon" --minutes 45
```

`derive` downloads the walk graph + POIs once, caches them under
`~/.cache/touch-grass/`, then works fully offline.

## How it works

| Module | Role |
|---|---|
| `spatial.py` | Cached OSMnx walk graph + POI tag extraction; radius from time budget |
| `router.py` | Anti-cost routing: penalizes arterials, rewards footways/alleys + jitter |
| `persona.py` | Turns bearings/POIs into riddles; template by default, GGUF LLM via `TOUCH_GRASS_MODEL` |
| `state.py` | Geofenced waypoint state machine — LLM only wakes on arrival |

On-device sensor polling (CoreLocation/Android), TTS, and model quantization
are platform-layer concerns left to a mobile shell; everything here runs
headless and testable.

## Tests

```sh
uv run pytest
```
