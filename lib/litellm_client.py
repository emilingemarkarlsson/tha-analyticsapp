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
_HTTP_TIMEOUT = 30          # seconds per request
_MAX_RETRIES = 1            # one retry on timeout or 5xx
_RETRY_DELAY = 1.5          # seconds before retry

# ── System prompt ──────────────────────────────────────────────────────────────
SQL_SYSTEM_PROMPT = """You are a DuckDB SQL expert for NHL hockey analytics. Generate valid DuckDB SQL queries.

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

Return ONLY the SQL query — no explanation, no markdown fences, no code blocks."""


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

def text_to_sql(question: str, history: list[tuple[str, str]] | None = None) -> str:
    """Convert a natural language question to a DuckDB SQL query.

    history: optional list of (question, sql) pairs from previous turns
    for multi-turn context (max 3 pairs used).

    Raises RuntimeError on LLM/network failure.
    """
    messages: list[dict] = [{"role": "system", "content": SQL_SYSTEM_PROMPT}]

    # Inject the last ≤3 turns as conversation context
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


def fix_sql(question: str, previous_sql: str, error: str) -> str:
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
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0,
    )
    sql = _clean_sql(raw)
    if not sql:
        raise RuntimeError("Model returned an empty response during SQL fix.")
    return sql


def summarise(question: str, rows: list[dict]) -> str:
    """Summarise query results in natural language (non-streaming).

    Returns a short summary string. Falls back to row count on empty data or error.
    """
    if not rows:
        return "The query returned no results."

    try:
        raw = _call_with_retry(
            model="groq-llama-fast",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an NHL analytics expert. Given a user question and query results, "
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


def summarise_stream(question: str, rows: list[dict]):
    """Generator that yields summary text chunks for use with st.write_stream().

    Always yields at least one chunk (fallback string on error/empty).
    Never raises — exceptions are caught and converted to a fallback yield.
    """
    if not rows:
        yield "The query returned no results."
        return

    try:
        client = _client()
        stream = client.chat.completions.create(
            model="groq-llama-fast",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an NHL analytics expert. Given a user question and query results, "
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
