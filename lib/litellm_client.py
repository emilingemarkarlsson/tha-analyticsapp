"""LiteLLM client – Text-to-SQL and result summarisation."""
import os
import re
import time
import logging
from openai import OpenAI, APITimeoutError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Timeouts & retries ─────────────────────────────────────────────────────────
_HTTP_TIMEOUT = 30
_MAX_RETRIES = 1
_RETRY_DELAY = 1.5

# ── Per-league SQL system prompts ──────────────────────────────────────────────
SCHEMA_PROMPTS: dict[str, str] = {

"nhl": """You are a DuckDB SQL expert for NHL hockey analytics.

DATABASE: nhl (MotherDuck / DuckDB)

TABLES:
games, team_game_stats, team_game_stats_extended, player_game_stats, game_players,
game_events, game_stories, teams, players, roster, schedule, playoff_brackets,
standings, skater_stats, goalie_stats, team_stats, edge_skaters, edge_goalies,
edge_teams, agent_insights, player_rolling_stats, goalie_rolling_stats,
team_rolling_stats, team_corsi

KEY RULES:
- Always use table names without schema prefix.
- team_abbr values: uppercase 3-letter codes (TOR, BOS, MTL, NYR, EDM, CGY, VAN …).
- season is BIGINT: 20242025 format (not a string).
- game_type = '2' regular season, '3' playoffs (stored as string).
- In team_game_stats game_type may be stored as DOUBLE — use TRY_CAST(game_type AS INTEGER) = 2.
- team_game_stats numeric cols (goals_for, goals_against, etc.) are VARCHAR — wrap with TRY_CAST(col AS DOUBLE).
- toi_seconds / 60 = minutes on ice.
- is_home BOOLEAN: true = home game.
- JOIN key: teams.abbr = team_game_stats.team_abbr (NOT teams.id).
- team_points: 2=win, 1=OT loss, 0=loss.
- player_game_stats has NO season or game_type columns — JOIN games g ON pgs.game_id = g.game_id.
- player_rolling_stats: use WHERE game_recency_rank = 1 for latest snapshot per player.
- Always add LIMIT when not present (default 20, max 200).
- For "recent games" use ORDER BY game_date DESC.
- For standings use: SELECT teamAbbrev, wins, losses, otLosses, points, gamesPlayed FROM standings WHERE season = 20242025 ORDER BY points DESC.
- For AI insights: SELECT headline, body, entity_name, team_abbr, insight_type, zscore, game_date FROM agent_insights ORDER BY generated_at DESC LIMIT 10.

FEATURE STORE SHORTCUTS:
- Current player form: player_rolling_stats WHERE game_recency_rank = 1 AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
- Team form: team_rolling_stats WHERE season = (SELECT MAX(season) FROM games WHERE game_type = '2')
- Corsi outliers: SELECT * FROM team_corsi WHERE corsi_pct < 0.42 OR corsi_pct > 0.58 ORDER BY game_date DESC LIMIT 20

MULTI-TURN INSTRUCTIONS:
- If the conversation history shows a previous query, you may reference the same tables/filters.
- "them", "they", "that team", "the same player" — resolve from context.
- For follow-up filters ("only for Toronto", "last 5 games instead") modify the previous SQL logically.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

"swe": """You are a DuckDB SQL expert for Swedish hockey analytics.

DATABASE: swe (MotherDuck / DuckDB) — covers SHL, Allsvenskan, HockeyEttan 2020–2026

TABLES:
- games (126K rows): game_id, game_date (DATE), season (BIGINT: 20242025), home_team, away_team, home_score, away_score, league ('SHL', 'Allsvenskan', 'HockeyEttan')
- game_player_stats (33K rows): game_id, game_date, player_id, player_name, team, goals, assists, points, pim, toi
- game_goals (22K rows): game_id, game_date, season, scorer, assist1, assist2, period, time, team, goal_type
- game_penalties (21K rows): game_id, game_date, season, player, team, minutes, reason, period
- game_lineups (4.3M rows): game_id, game_date, season, player_id, player_name, team, jersey_number, is_starting
- game_period_scores (259K rows): game_id, game_date, season, period, home_goals, away_goals
- game_goalie_stats (2K rows): game_id, game_date, player_id, player_name, team, shots_against, goals_against, save_pct, toi

KEY RULES:
- Always filter by league: WHERE league = 'SHL' (default) or 'Allsvenskan'
- Team names are Swedish full names: 'Frölunda', 'Djurgårdens IF', 'Luleå HF', 'Skellefteå AIK', 'Linköping HC', 'HV71', 'Rögle BK', 'Örebro HK', 'Brynäs IF', 'Timrå IK', 'Malmö Redhawks', 'Färjestad BK'
- season is BIGINT: 20242025 format
- No schema prefix needed
- Always add LIMIT (default 20, max 200)
- For top scorers: SUM goals/assists/points from game_player_stats GROUP BY player_name
- For standings: aggregate W/L from games (no dedicated standings table)
- For recent games: ORDER BY game_date DESC

MULTI-TURN INSTRUCTIONS: resolve "them", "that team", "same player" from conversation context.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

"shl": """You are a DuckDB SQL expert for SHL Analytics.

DATABASE: shl_analytics (MotherDuck / DuckDB) — Swedish Hockey League per-game data

TABLES (ALWAYS use schema prefix raw. or analytics.):
- raw.players_per_game (1761r): player_name, team, season_name, game_type_name, gp, goals, assists, points, plus_minus, pim, shots, hits, blocks
- raw.goalies_per_game (176r): player_name, team, season_name, game_type_name, gp, toi, goals_against, save_pct, gaa
- raw.teams_per_game (per game rows, Swedish cols): datum (date), game_uuid, season_name, game_type_name, round_number, lag (team), hemma_borta ('hemma'/'borta'), motstandare (opponent), egna_mal (goals for), inslappta_mal (goals against), vann (1=win/0=loss), overtime, shootout, mal (goals), assist, skott (shots), pp_mal (PP goals), pim, hits, avg_toi_min, fo_procent (faceoff%)
- analytics.dim_standings: season_name, game_type_name, lag (team), matcher (GP), vinster (wins), poang (points), gjorda_mal (GF), inslappta_mal (GA), malminus (diff)

KEY RULES:
- ALWAYS prefix tables: raw.players_per_game, raw.teams_per_game, analytics.dim_standings. NEVER use bare names.
- season_name is VARCHAR: '2025/2026' format
- game_type_name: 'Slutspel' = playoffs, 'Grundserie' = regular season (if available)
- raw.teams_per_game uses Swedish column names: lag=team, vann=win, egna_mal=GF, inslappta_mal=GA
- analytics.dim_standings uses: lag=team, vinster=wins, poang=points, gjorda_mal=GF
- No game_date or game_id — data is aggregated
- For standings: SELECT lag AS team, SUM(vann) AS wins FROM raw.teams_per_game GROUP BY lag ORDER BY wins DESC
- For top scorers: SELECT player_name, team, goals, assists, points FROM raw.players_per_game ORDER BY points DESC
- Always add LIMIT (default 20, max 200)

MULTI-TURN INSTRUCTIONS: resolve "them", "that team", "same player" from conversation context.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

"nor": """You are a DuckDB SQL expert for Norwegian Eliteserien hockey analytics.

DATABASE: nor (MotherDuck / DuckDB) — covers 2022–2026

TABLES:
- matches (2664r): match_id, match_date (TIMESTAMP), season_year (INT: 2022–2026), season_phase ('Regular'/'Playoffs'), home_team_name, away_team_name, home_goals, away_goals, tournament_id
- match_lineup (111K rows): match_id, player_id, player_name, team_slug, jersey_number, role ('forward'/'defense'/'goalie')
- goal_events (15K rows): match_id, player_id, player_name, team_slug, period, game_time, assist1_player_id, assist2_player_id, goal_type
- penalty_events (20K rows): match_id, player_id, player_name, team_slug, period, minutes, reason
- skater_summaries (3144r): player_id, team_slug, tournament_id, season_year, season_phase, games_played, goals, assists, points, plus_minus, shots, time_on_ice
- players (824r): player_id, date_of_birth, role, height_cm, weight_kg
- tournaments (112r): tournament_id, team_slug, year, phase, tournament_name

KEY RULES:
- match_date is TIMESTAMP — use match_date::DATE for date operations
- season_year is INT: 2022, 2023, 2024, 2025, 2026
- Team slugs (lowercase): 'valerenga', 'sparta', 'storhamar', 'stavanger', 'lillehammer', 'stjernen', 'ringerike', 'gruner', 'frisk_asker', 'manglerud_star'
- skater_summaries has no player names — JOIN match_lineup on player_id to get names
- For standings: aggregate from matches (no dedicated standings table)
- For top scorers: use skater_summaries JOIN (SELECT player_id, MAX(player_name) AS player_name FROM match_lineup GROUP BY player_id)
- Always add LIMIT (default 20, max 200)

MULTI-TURN INSTRUCTIONS: resolve "them", "that team", "same player" from conversation context.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

"sui": """You are a DuckDB SQL expert for Swiss National League hockey analytics.

DATABASE: sui (MotherDuck / DuckDB) — covers 2025–2026

TABLES:
- games: game_id (VARCHAR), season (VARCHAR: '2025' or '2026'), start_dt (VARCHAR ISO timestamp), home_team, away_team, home_goals (VARCHAR), away_goals (VARCHAR), league_name, ot, so, venue
- game_player_stats: game_id, season, start_dt, team_id, team_name, player_id, player_name, position, goals (VARCHAR), assists (VARCHAR), points (VARCHAR), pim (VARCHAR), plus_minus (VARCHAR), sog, toi_sec
- game_goalie_stats: game_id, season, player_id, player_name, team_id, team_name, goals_against, shots_against, toi_sec
- game_goals: game_id, season, period, scorer_name, team_name, game_time

KEY RULES:
- season is VARCHAR: '2025' or '2026' (just the year the season ends, NOT '2024-25')
- home_goals/away_goals are VARCHAR — use TRY_CAST(home_goals AS INTEGER) for arithmetic
- goals/assists/points in game_player_stats are VARCHAR — use TRY_CAST(goals AS INTEGER)
- team column is team_name (NOT team)
- start_dt is VARCHAR ISO string — use TRY_CAST(start_dt AS DATE) or STRPTIME for date ops
- Team names: 'ZSC Lions', 'HC Davos', 'EV Zug', 'HC Fribourg-Gottéron', 'Lausanne HC', 'SC Bern', 'EHC Biel-Bienne', 'HC Lugano', 'EHC Kloten', 'HC Ajoie', 'HC Ambri-Piotta', 'SCL Tigers', 'Genève-Servette HC'
- For standings: aggregate from games using TRY_CAST(home_goals AS INTEGER) etc.
- Always add LIMIT (default 20, max 200)

MULTI-TURN INSTRUCTIONS: resolve "them", "that team", "same player" from conversation context.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

"liiga": """You are a DuckDB SQL expert for Finnish Liiga hockey analytics.

DATABASE: liiga (MotherDuck / DuckDB) — covers 2003–2026

TABLES:
- games (11191r): game_id, season (INT: year the season ends, e.g. 2024 = 2023-24), serie ('regular'/'playoffs'), start (TIMESTAMP), home_team_id, home_team_name, away_team_name, home_goals, away_goals, home_pp_instances, home_pp_goals, away_pp_instances, away_pp_goals, home_xg, away_xg, finished_type, spectators, game_week
- goal_events (60629r): game_id, season, serie, event_id, team_side ('home'/'away'), scorer_player_id, scorer_name, period, game_time, goal_types (JSON: ['EV','PP','SH','EN','PS']), assistant_1_name, assistant_2_name, home_score, away_score, winning_goal
- standings (943r): season, serie ('season'/'playoffs'/'playout'), team_id, team_name, ranking, games, wins, overtime_wins, losses, ties, overtime_losses, points, points_per_game, goals, goals_against, pp_instances, pp_goals, pp_percentage, pk_instances, pk_percentage, penalty_minutes

KEY RULES:
- start is TIMESTAMP — use start::DATE for date operations
- season is INT: 2024 means the 2023-24 season (the year it ends)
- serie = 'regular' for regular season games, 'playoffs' for playoffs
- For standings use standings table WHERE serie = 'season'
- No per-player stats per game (only goal scorer data in goal_events)
- Finnish team names: 'Tappara', 'HIFK', 'Kärpät', 'TPS', 'Lukko', 'JYP', 'Pelicans', 'Sport', 'SaiPa', 'Ilves', 'HPK', 'Ässät'
- Always add LIMIT (default 20, max 200)

MULTI-TURN INSTRUCTIONS: resolve "them", "that team" from conversation context.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

"met": """You are a DuckDB SQL expert for Danish Metal Ligaen hockey analytics.

DATABASE: met (MotherDuck / DuckDB)

TABLES:
- ih24_results (2861r): match_id, season (VARCHAR: '2024-25'), match_date (VARCHAR: 'YYYY-MM-DD'), round, home_team, away_team, score_home, score_away, overtime, p1_home, p1_away, p2_home, p2_away, p3_home, p3_away
- ih24_standings (252r): season, rank, team, gp, w, otw, otl, l, gf, ga, pts
- ml_player_stats (200r): season, phase, navn (=name), hold (=team), pos, gp, g (goals), a (assists), p (points), pm, plus_per_minus
- ml_goalie_stats (158r): season, phase, navn, hold, gp, toi, sa, ga, svpct, gaa, svs
- ep_player_stats (1875r): name, league, season, phase, url, scraped_at
- ep_goalie_stats (879r): name, league, season, phase, scraped_at

KEY RULES:
- score_home/score_away are VARCHAR — TRY_CAST(score_home AS INTEGER) for arithmetic
- match_date is VARCHAR 'YYYY-MM-DD' (sortable as string, no casting needed)
- season is VARCHAR: '2024-25' format
- Player columns use Danish: navn=name, hold=team, g=goals, a=assists, p=points
- Danish team names: 'Herning Blue Fox', 'Rungsted Seier Capital', 'Aalborg Pirates', 'Odense Bulldogs', 'Esbjerg Energy', 'Frederikshavn White Hawks', 'SønderjyskE', 'Herlev Eagles', 'Gentofte Stars'
- For standings: SELECT * FROM ih24_standings WHERE season = (SELECT MAX(season) FROM ih24_standings) ORDER BY rank
- Always add LIMIT (default 20, max 200)

MULTI-TURN INSTRUCTIONS: resolve "them", "that team" from conversation context.

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks.""",

}

# ── Analyst context per league (for summarisation) ────────────────────────────
_ANALYST_CONTEXT: dict[str, str] = {
    "nhl":   "NHL hockey",
    "swe":   "Swedish SHL/Allsvenskan hockey",
    "shl":   "Swedish Hockey League (SHL)",
    "nor":   "Norwegian Eliteserien hockey",
    "sui":   "Swiss National League hockey",
    "liiga": "Finnish Liiga hockey",
    "met":   "Danish Metal Ligaen hockey",
}


def get_sql_prompt(league: str) -> str:
    """Return the correct SQL system prompt for the given league."""
    return SCHEMA_PROMPTS.get(league, SCHEMA_PROMPTS["nhl"])


# ── Client factory ─────────────────────────────────────────────────────────────

def _client() -> OpenAI:
    base = os.environ.get("LITELLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LITELLM_API_KEY", "")
    if not base:
        raise RuntimeError("LITELLM_BASE_URL is not set")
    if not key:
        raise RuntimeError("LITELLM_API_KEY is not set")
    return OpenAI(
        base_url=f"{base}/v1",
        api_key=key,
        timeout=_HTTP_TIMEOUT,
    )


def _clean_sql(text: str) -> str:
    """Strip markdown code fences and surrounding whitespace from model output."""
    text = text.strip()
    m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    return (m.group(1) if m else text).strip()


def _call_with_retry(model: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
    """Call LiteLLM with one retry on timeout or 5xx errors."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = resp.choices[0].message.content or ""
            return content
        except APITimeoutError as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                logger.warning("LiteLLM timeout (attempt %d), retrying in %.1fs…", attempt + 1, _RETRY_DELAY)
                time.sleep(_RETRY_DELAY)
        except APIStatusError as exc:
            last_error = exc
            if exc.status_code >= 500 and attempt < _MAX_RETRIES:
                logger.warning("LiteLLM %d error (attempt %d), retrying…", exc.status_code, attempt + 1)
                time.sleep(_RETRY_DELAY)
            else:
                raise
        except Exception:
            raise

    raise RuntimeError(f"LiteLLM request failed after {_MAX_RETRIES + 1} attempts: {last_error}") from last_error


# ── Public API ─────────────────────────────────────────────────────────────────

def text_to_sql(
    question: str,
    history: list[tuple[str, str]] | None = None,
    league: str = "nhl",
) -> str:
    """Convert a natural language question to a DuckDB SQL query.

    history: optional list of (question, sql) pairs from previous turns (max 3 used).
    league: target database/league — selects the correct schema prompt.

    Raises RuntimeError on LLM/network failure.
    """
    system_prompt = get_sql_prompt(league)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if history:
        for prev_q, prev_sql in history[-3:]:
            messages.append({"role": "user", "content": prev_q})
            messages.append({"role": "assistant", "content": prev_sql})

    messages.append({"role": "user", "content": question})

    raw = _call_with_retry(
        model="gemini-flash",
        messages=messages,
        max_tokens=600,
        temperature=0,
    )
    sql = _clean_sql(raw)
    if not sql:
        raise RuntimeError("Model returned an empty response for SQL generation.")
    return sql


def fix_sql(question: str, previous_sql: str, error: str, league: str = "nhl") -> str:
    """Ask the model to fix a failing SQL query given the original error.

    Raises RuntimeError on LLM/network failure.
    """
    prompt = (
        f"Original user question:\n{question}\n\n"
        f"Previous SQL (failed):\n{previous_sql}\n\n"
        f"DuckDB execution error:\n{error}\n\n"
        "Fix the SQL so it runs successfully in DuckDB. "
        "Return corrected SQL only — no explanation, no markdown fences."
    )
    raw = _call_with_retry(
        model="gemini-flash",
        messages=[
            {"role": "system", "content": get_sql_prompt(league)},
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0,
    )
    sql = _clean_sql(raw)
    if not sql:
        raise RuntimeError("Model returned an empty response during SQL fix.")
    return sql


def summarise(question: str, rows: list[dict], league: str = "nhl") -> str:
    """Summarise query results in natural language (non-streaming).

    Returns a short summary string. Falls back to row count on empty data or error.
    """
    if not rows:
        return "The query returned no results."

    context = _ANALYST_CONTEXT.get(league, "hockey")
    try:
        raw = _call_with_retry(
            model="groq-llama-fast",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a {context} analytics expert. Given a user question and query results, "
                        "write a concise 2–3 sentence summary in English. "
                        "Use specific numbers from the data. Be direct, no filler phrases."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nResults (up to 10 rows):\n{rows[:10]}",
                },
            ],
            max_tokens=200,
            temperature=0.3,
        )
        return raw.strip() or f"{len(rows):,} rows returned."
    except Exception as exc:
        logger.warning("summarise() failed: %s", exc)
        return f"{len(rows):,} rows returned."


def summarise_stream(question: str, rows: list[dict], league: str = "nhl"):
    """Generator that yields summary text chunks for use with st.write_stream().

    Always yields at least one chunk (fallback string on error/empty).
    Never raises — exceptions are caught and converted to a fallback yield.
    """
    if not rows:
        yield "The query returned no results."
        return

    context = _ANALYST_CONTEXT.get(league, "hockey")
    try:
        client = _client()
        stream = client.chat.completions.create(
            model="groq-llama-fast",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a {context} analytics expert. Given a user question and query results, "
                        "write a concise 2–3 sentence summary in English. "
                        "Use specific numbers from the data. Be direct, no filler phrases."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nResults (up to 10 rows):\n{rows[:10]}",
                },
            ],
            max_tokens=200,
            temperature=0.3,
            stream=True,
        )
        yielded_any = False
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yielded_any = True
                yield delta
        if not yielded_any:
            yield f"{len(rows):,} rows returned."
    except Exception as exc:
        logger.warning("summarise_stream() failed: %s", exc)
        yield f"{len(rows):,} rows returned."
