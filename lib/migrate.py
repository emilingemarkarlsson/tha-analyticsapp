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
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'users'
                    )
                """)
                exists = cur.fetchone()[0]
                if not exists:
                    schema_path = Path(__file__).parent.parent / "pg_schema.sql"
                    cur.execute(schema_path.read_text())
                    print("[migrate] schema applied")
                else:
                    print("[migrate] schema already present")
        conn.close()
    except Exception as e:
        print(f"[migrate] error: {e}")
