"""Local SQLite store for user data – plans, watchlists, rosters, AI usage."""
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
            CREATE TABLE IF NOT EXISTS users (
                user_id                TEXT PRIMARY KEY,
                plan                   TEXT NOT NULL DEFAULT 'free',
                stripe_customer_id     TEXT DEFAULT '',
                stripe_subscription_id TEXT DEFAULT '',
                plan_updated_at        TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS ai_usage (
                user_id     TEXT NOT NULL,
                date        TEXT NOT NULL,
                query_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                user_id     TEXT NOT NULL DEFAULT '',
                player_id   TEXT NOT NULL,
                player_name TEXT NOT NULL,
                team_abbr   TEXT,
                position    TEXT,
                added_at    TEXT DEFAULT (datetime('now')),
                note        TEXT DEFAULT '',
                PRIMARY KEY (user_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS rosters (
                roster_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL DEFAULT '',
                name       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, name)
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
        # Migrate legacy watchlist rows that lack user_id column (no-op if already migrated)
        try:
            c.execute("ALTER TABLE watchlist ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass


# ── User / Plan ────────────────────────────────────────────────────────────────

def upsert_user(user_id: str, plan: str = "free") -> None:
    """Ensure a user row exists; insert if missing."""
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO users (user_id, plan) VALUES (?, ?)",
            (user_id, plan),
        )


def get_user_plan(user_id: str) -> str:
    """Return plan string for user_id, defaulting to 'free'."""
    with _conn() as c:
        row = c.execute("SELECT plan FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return row["plan"] if row else "free"


def set_user_plan(user_id: str, plan: str,
                  stripe_customer_id: str = "", stripe_subscription_id: str = "") -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO users (user_id, plan, stripe_customer_id, stripe_subscription_id, plan_updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET
                   plan                   = excluded.plan,
                   stripe_customer_id     = CASE WHEN excluded.stripe_customer_id != ''
                                                 THEN excluded.stripe_customer_id
                                                 ELSE stripe_customer_id END,
                   stripe_subscription_id = CASE WHEN excluded.stripe_subscription_id != ''
                                                 THEN excluded.stripe_subscription_id
                                                 ELSE stripe_subscription_id END,
                   plan_updated_at        = excluded.plan_updated_at""",
            (user_id, plan, stripe_customer_id, stripe_subscription_id),
        )


# ── AI Usage ───────────────────────────────────────────────────────────────────

def ai_queries_today(user_id: str) -> int:
    """Return how many AI queries the user has made today."""
    import datetime
    today = datetime.date.today().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT query_count FROM ai_usage WHERE user_id = ? AND date = ?",
            (user_id, today),
        ).fetchone()
    return row["query_count"] if row else 0


def increment_ai_query(user_id: str) -> int:
    """Increment today's AI query count and return new total."""
    import datetime
    today = datetime.date.today().isoformat()
    with _conn() as c:
        c.execute(
            """INSERT INTO ai_usage (user_id, date, query_count) VALUES (?, ?, 1)
               ON CONFLICT(user_id, date) DO UPDATE SET query_count = query_count + 1""",
            (user_id, today),
        )
        row = c.execute(
            "SELECT query_count FROM ai_usage WHERE user_id = ? AND date = ?",
            (user_id, today),
        ).fetchone()
    return row["query_count"] if row else 1


# ── Watchlist ──────────────────────────────────────────────────────────────────

def watchlist_add(player_id: str, player_name: str, team_abbr: str, position: str,
                  user_id: str = "") -> None:
    with _conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO watchlist (user_id, player_id, player_name, team_abbr, position)
               VALUES (?,?,?,?,?)""",
            (user_id, player_id, player_name, team_abbr, position),
        )


def watchlist_remove(player_id: str, user_id: str = "") -> None:
    with _conn() as c:
        c.execute("DELETE FROM watchlist WHERE user_id = ? AND player_id = ?", (user_id, player_id))


def watchlist_all(user_id: str = "") -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT player_id, player_name, team_abbr, position, added_at, note
               FROM watchlist WHERE user_id = ? ORDER BY added_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def watchlist_ids(user_id: str = "") -> set[str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT player_id FROM watchlist WHERE user_id = ?", (user_id,)
        ).fetchall()
    return {r["player_id"] for r in rows}


def watchlist_count(user_id: str = "") -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM watchlist WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["n"] if row else 0


def watchlist_note(player_id: str, note: str, user_id: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE watchlist SET note = ? WHERE user_id = ? AND player_id = ?",
            (note, user_id, player_id),
        )


# ── Rosters ────────────────────────────────────────────────────────────────────

def roster_list(user_id: str = "") -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT roster_id, name, created_at FROM rosters WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def roster_create(name: str, user_id: str = "") -> int:
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO rosters (user_id, name) VALUES (?,?)", (user_id, name))
        row = c.execute(
            "SELECT roster_id FROM rosters WHERE user_id = ? AND name = ?", (user_id, name)
        ).fetchone()
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
