"""Smoke test: verify PostgreSQL schema is compatible with auth.py and userdb.py expectations."""
import os
import sys
import psycopg2
import psycopg2.extras


def _conn():
    return psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        connect_timeout=5,
    )


EXPECTED_USERS_COLS = {
    "id", "email", "password_hash", "full_name", "plan_id",
    "stripe_customer_id", "stripe_subscription_id", "plan_updated_at",
    "is_active", "last_login_at", "created_at",
}
EXPECTED_SESSIONS_COLS = {"id", "user_id", "token_hash", "expires_at", "created_at"}
EXPECTED_PLANS_COLS = {"id", "name"}
EXPECTED_AI_USAGE_COLS = {"user_id", "date", "query_count"}


def test_schema():
    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check each table exists and has expected columns
            for table, expected in [
                ("users", EXPECTED_USERS_COLS),
                ("sessions", EXPECTED_SESSIONS_COLS),
                ("plans", EXPECTED_PLANS_COLS),
                ("ai_usage", EXPECTED_AI_USAGE_COLS),
                ("watchlist", {"user_id", "player_id", "player_name"}),
                ("rosters", {"roster_id", "user_id", "name"}),
                ("roster_players", {"roster_id", "player_id", "player_name"}),
            ]:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table,),
                )
                actual = {row["column_name"] for row in cur.fetchall()}
                missing = expected - actual
                assert not missing, f"Table `{table}` missing columns: {missing}"
                print(f"  ✓ {table}: all expected columns present")

            # Check plans table has required entries
            cur.execute("SELECT name FROM plans ORDER BY name")
            plans = {r["name"] for r in cur.fetchall()}
            assert {"free", "base", "plus"} <= plans, f"Plans table missing entries: {plans}"
            print("  ✓ plans: free/base/plus entries present")

    print("Schema OK — all tables and columns verified.")


if __name__ == "__main__":
    try:
        test_schema()
    except AssertionError as e:
        print(f"SCHEMA ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"CONNECTION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

