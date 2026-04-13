-- THA Analytics – Supabase migration
-- Run this in: Supabase dashboard → SQL Editor → New query
-- https://supabase.com/dashboard/project/<your-project>/sql

-- ── Users & plans ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id                TEXT PRIMARY KEY,
    plan                   TEXT NOT NULL DEFAULT 'free',
    stripe_customer_id     TEXT DEFAULT '',
    stripe_subscription_id TEXT DEFAULT '',
    plan_updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── AI usage quota (one row per user per day) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_usage (
    user_id     TEXT NOT NULL,
    date        DATE NOT NULL,
    query_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

-- ── Watchlist ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlist (
    user_id     TEXT NOT NULL DEFAULT '',
    player_id   TEXT NOT NULL,
    player_name TEXT NOT NULL,
    team_abbr   TEXT,
    position    TEXT,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    note        TEXT DEFAULT '',
    PRIMARY KEY (user_id, player_id)
);

-- ── Rosters ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rosters (
    roster_id  SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL DEFAULT '',
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

-- ── Row Level Security (disabled – app uses service key) ───────────────────────
-- Tables are accessed only via the service role key from the backend,
-- so RLS is not needed. Enable and add policies if you ever expose these
-- tables directly to the Supabase JS client in a frontend.
ALTER TABLE users          DISABLE ROW LEVEL SECURITY;
ALTER TABLE ai_usage       DISABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist      DISABLE ROW LEVEL SECURITY;
ALTER TABLE rosters        DISABLE ROW LEVEL SECURITY;
ALTER TABLE roster_players DISABLE ROW LEVEL SECURITY;
