import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS worlds (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, season TEXT NOT NULL,
            min_x INTEGER NOT NULL, max_x INTEGER NOT NULL,
            min_y INTEGER NOT NULL, max_y INTEGER NOT NULL, wrap INTEGER NOT NULL,
            UNIQUE(name, season)
        );
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY, world_id INTEGER NOT NULL REFERENCES worlds(id),
            kind TEXT NOT NULL, sha256 TEXT NOT NULL, imported_at TEXT NOT NULL,
            observed_at TEXT, complete_snapshot INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES imports(id),
            x INTEGER NOT NULL, y INTEGER NOT NULL, payload TEXT NOT NULL,
            UNIQUE(import_id, x, y)
        );
        CREATE INDEX IF NOT EXISTS observation_coords ON observations(x,y);
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY, world_id INTEGER NOT NULL REFERENCES worlds(id),
            name TEXT NOT NULL, items TEXT NOT NULL DEFAULT '[]'
        );
    ''')
    return db
