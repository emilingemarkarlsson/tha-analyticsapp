"""Local SQLite store for user data – watchlists, rosters, notes."""
import sqlite3
import os
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "user.sqlite"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS watchlist (
                player_id   TEXT PRIMARY KEY,
                player_name TEXT NOT NULL,
                team_abbr   TEXT,
                position    TEXT,
                added_at    TEXT DEFAULT (datetime('now')),
                note        TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS rosters (
                roster_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS roster_players (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                roster_id   INTEGER NOT NULL REFERENCES rosters(roster_id) ON DELETE CASCADE,
                player_id   TEXT NOT NULL,
                player_name TEXT NOT NULL,
                team_abbr   TEXT,
                position    TEXT,
                salary_k    INTEGER DEFAULT 0,
                note        TEXT DEFAULT '',
                added_at    TEXT DEFAULT (datetime('now')),
                UNIQUE(roster_id, player_id)
            );
        """)


# ── Watchlist ──────────────────────────────────────────────────────────────────

def watchlist_add(player_id: str, player_name: str, team_abbr: str, position: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO watchlist (player_id, player_name, team_abbr, position) VALUES (?,?,?,?)",
            (player_id, player_name, team_abbr, position),
        )


def watchlist_remove(player_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM watchlist WHERE player_id = ?", (player_id,))


def watchlist_all() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT player_id, player_name, team_abbr, position, added_at, note FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def watchlist_ids() -> set[str]:
    with _conn() as c:
        rows = c.execute("SELECT player_id FROM watchlist").fetchall()
    return {r["player_id"] for r in rows}


def watchlist_note(player_id: str, note: str) -> None:
    with _conn() as c:
        c.execute("UPDATE watchlist SET note = ? WHERE player_id = ?", (note, player_id))


# ── Rosters ────────────────────────────────────────────────────────────────────

def roster_list() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT roster_id, name, created_at FROM rosters ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def roster_create(name: str) -> int:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO rosters (name) VALUES (?)", (name,))
        row = c.execute("SELECT roster_id FROM rosters WHERE name = ?", (name,)).fetchone()
    return row["roster_id"]


def roster_delete(roster_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM rosters WHERE roster_id = ?", (roster_id,))


def roster_add_player(roster_id: int, player_id: str, player_name: str,
                       team_abbr: str, position: str, salary_k: int = 0) -> None:
    with _conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO roster_players
               (roster_id, player_id, player_name, team_abbr, position, salary_k)
               VALUES (?,?,?,?,?,?)""",
            (roster_id, player_id, player_name, team_abbr, position, salary_k),
        )


def roster_remove_player(roster_id: int, player_id: str) -> None:
    with _conn() as c:
        c.execute(
            "DELETE FROM roster_players WHERE roster_id = ? AND player_id = ?",
            (roster_id, player_id),
        )


def roster_set_salary(roster_id: int, player_id: str, salary_k: int) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE roster_players SET salary_k = ? WHERE roster_id = ? AND player_id = ?",
            (salary_k, roster_id, player_id),
        )


def roster_players(roster_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT player_id, player_name, team_abbr, position, salary_k, note, added_at
               FROM roster_players WHERE roster_id = ? ORDER BY position, player_name""",
            (roster_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# Ensure tables exist on import
init()
