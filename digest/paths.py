from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOALS_JSON = ROOT / "goals.json"
VALUES_JSON = ROOT / "values.json"
CHECKINS_JSON = ROOT / "checkins.json"
GOALS_EXAMPLE_JSON = ROOT / "goals.json.example"
VALUES_EXAMPLE_JSON = ROOT / "values.json.example"
CHECKINS_EXAMPLE_JSON = ROOT / "checkins.json.example"
PREFS_JSON = ROOT / "prefs.json"
DB_PATH = ROOT / "digest.db"

