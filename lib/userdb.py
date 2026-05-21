"""PostgreSQL store for user data — plans, watchlists, rosters, AI usage."""
import os
import datetime
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def _conn():
    return psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        connect_timeout=5,
    )


# ── User / Plan ──────────────────────────────────────────────────────────────

def upsert_user(user_id: str, plan: str = "free") -> None:
    """No-op: user row is created by sign_up. Kept for API compatibility."""
    pass


def get_user_plan(user_id: str) -> str:
    """Return plan name for user_id, defaulting to 'free'."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.name FROM users u JOIN plans p ON p.id = u.plan_id WHERE u.id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return row[0] if row else "free"


def set_user_plan(user_id: str, plan: str,
                  stripe_customer_id: str = "", stripe_subscription_id: str = "") -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users
                   SET plan_id = (SELECT id FROM plans WHERE name = %s LIMIT 1),
                       plan_updated_at = NOW(),
                       stripe_customer_id = COALESCE(NULLIF(%s, ''), stripe_customer_id),
                       stripe_subscription_id = COALESCE(NULLIF(%s, ''), stripe_subscription_id)
                   WHERE id = %s""",
                (plan, stripe_customer_id, stripe_subscription_id, user_id),
            )


# ── AI Usage ─────────────────────────────────────────────────────────────────

def ai_queries_today(user_id: str) -> int:
    today = datetime.date.today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT query_count FROM ai_usage WHERE user_id = %s AND date = %s",
                (user_id, today),
            )
            row = cur.fetchone()
    return row[0] if row else 0


def increment_ai_query(user_id: str) -> int:
    today = datetime.date.today()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ai_usage (user_id, date, query_count)
                   VALUES (%s, %s, 1)
                   ON CONFLICT (user_id, date) DO UPDATE
                   SET query_count = ai_usage.query_count + 1
                   RETURNING query_count""",
                (user_id, today),
            )
            row = cur.fetchone()
    return row[0] if row else 1


# ── Watchlist ─────────────────────────────────────────────────────────────────

def watchlist_add(player_id: str, player_name: str, team_abbr: str, position: str,
                  user_id: str = "") -> None:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO watchlist (user_id, player_id, player_name, team_abbr, position)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (user_id, player_id) DO NOTHING""",
                    (user_id, player_id, player_name, team_abbr, position),
                )
    except Exception:
        pass


def watchlist_remove(player_id: str, user_id: str = "") -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist WHERE user_id = %s AND player_id = %s",
                (user_id, player_id),
            )


def watchlist_all(user_id: str = "") -> list[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT player_id, player_name, team_abbr, position, added_at, note
                   FROM watchlist WHERE user_id = %s ORDER BY added_at DESC""",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def watchlist_ids(user_id: str = "") -> set[str]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM watchlist WHERE user_id = %s", (user_id,))
            return {r[0] for r in cur.fetchall()}


def watchlist_count(user_id: str = "") -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM watchlist WHERE user_id = %s", (user_id,))
            return cur.fetchone()[0]


def watchlist_note(player_id: str, note: str, user_id: str = "") -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE watchlist SET note = %s WHERE user_id = %s AND player_id = %s",
                (note, user_id, player_id),
            )


# ── Rosters ──────────────────────────────────────────────────────────────────

def roster_list(user_id: str = "") -> list[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT roster_id, name, created_at FROM rosters WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def roster_create(name: str, user_id: str = "") -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT roster_id FROM rosters WHERE user_id = %s AND name = %s",
                (user_id, name),
            )
            existing = cur.fetchone()
            if existing:
                return existing[0]
            cur.execute(
                "INSERT INTO rosters (user_id, name) VALUES (%s, %s) RETURNING roster_id",
                (user_id, name),
            )
            return cur.fetchone()[0]


def roster_delete(roster_id: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rosters WHERE roster_id = %s", (roster_id,))


def roster_add_player(roster_id: int, player_id: str, player_name: str,
                      team_abbr: str, position: str, salary_k: int = 0) -> None:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO roster_players (roster_id, player_id, player_name, team_abbr, position, salary_k)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (roster_id, player_id) DO NOTHING""",
                    (roster_id, player_id, player_name, team_abbr, position, salary_k),
                )
    except Exception:
        pass


def roster_remove_player(roster_id: int, player_id: str) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM roster_players WHERE roster_id = %s AND player_id = %s",
                (roster_id, player_id),
            )


def roster_set_salary(roster_id: int, player_id: str, salary_k: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE roster_players SET salary_k = %s WHERE roster_id = %s AND player_id = %s",
                (salary_k, roster_id, player_id),
            )


def roster_players(roster_id: int) -> list[dict]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT player_id, player_name, team_abbr, position, salary_k, note, added_at
                   FROM roster_players WHERE roster_id = %s ORDER BY position, player_name""",
                (roster_id,),
            )
            return [dict(r) for r in cur.fetchall()]
