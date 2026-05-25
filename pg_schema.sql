-- THA Analytics – PostgreSQL schema (Coolify deployment)
-- Replaced Supabase 2026-05-21. Apply via Coolify container exec or direct psql.
-- psql -h <PG_HOST> -p 54330 -U <PG_USER> -d <PG_DB> -f pg_schema.sql

-- ── Plans (enum-like lookup) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS plans (
    id    SERIAL PRIMARY KEY,
    name  TEXT UNIQUE NOT NULL
);

INSERT INTO plans (name) VALUES
    ('free'), ('base'), ('plus')
ON CONFLICT (name) DO NOTHING;

-- ── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                  TEXT UNIQUE NOT NULL,
    password_hash          TEXT NOT NULL,
    full_name              TEXT,
    plan_id                INTEGER REFERENCES plans(id) DEFAULT (SELECT id FROM plans WHERE name = 'free'),
    stripe_customer_id     TEXT DEFAULT '',
    stripe_subscription_id TEXT DEFAULT '',
    plan_updated_at        TIMESTAMPTZ DEFAULT NOW(),
    is_active              BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at          TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ── Sessions ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sessions_token_hash_idx ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);

-- ── AI usage quota (one row per user per day) ────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_usage (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date        DATE NOT NULL,
    query_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

-- ── Watchlist ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlist (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    player_id   TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team_abbr   TEXT,
    position    TEXT,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    note        TEXT DEFAULT '',
    PRIMARY KEY (user_id, player_id)
);

-- ── Rosters ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rosters (
    roster_id  SERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS roster_players (
    id          SERIAL PRIMARY KEY,
    roster_id   INTEGER NOT NULL REFERENCES rosters(roster_id) ON DELETE CASCADE,
    player_id   TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team_abbr   TEXT,
    position    TEXT,
    salary_k    INTEGER DEFAULT 0,
    note        TEXT DEFAULT '',
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (roster_id, player_id)
);

-- ── Cleanup expired sessions (run via cron or manually) ─────────────────────
-- DELETE FROM sessions WHERE expires_at < NOW();

