"""Auto-migration: ensure the PostgreSQL schema exists on startup."""
import os
import psycopg2
from pathlib import Path


def ensure_schema() -> None:
    """Apply pg_schema.sql if the tables don't exist yet. Idempotent."""
    try:
        conn = psycopg2.connect(
            host=os.environ["PG_HOST"],
            port=int(os.environ.get("PG_PORT", "5432")),
            dbname=os.environ["PG_DB"],
            user=os.environ["PG_USER"],
            password=os.environ["PG_PASSWORD"],
            connect_timeout=5,
        )
        with conn:
            with conn.cursor() as cur:
                # Check for the NEW schema by looking for the password_hash column.
                # The old Supabase schema has a 'users' table but no 'password_hash'
                # column, so checking table existence alone is insufficient.
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'users'
                          AND column_name = 'password_hash'
                    )
                """)
                new_schema_present = cur.fetchone()[0]
                if not new_schema_present:
                    # Old Supabase schema detected (or empty DB). Drop stale tables
                    # so CREATE TABLE IF NOT EXISTS in pg_schema.sql recreates them
                    # with the correct columns.
                    cur.execute(
                        "DROP TABLE IF EXISTS roster_players, rosters, watchlist,"
                        " ai_usage, sessions, users, plans CASCADE"
                    )
                    schema_path = Path(__file__).parent.parent / "pg_schema.sql"
                    cur.execute(schema_path.read_text())
                    print("[migrate] schema applied (replaced old Supabase schema)")
                else:
                    print("[migrate] new schema already present")
        conn.close()
    except Exception as e:
        print(f"[migrate] error: {e}")
