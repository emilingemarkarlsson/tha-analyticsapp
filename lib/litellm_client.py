"""LiteLLM client – Text-to-SQL and result summarisation."""
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SQL_SYSTEM_PROMPT = """You are a DuckDB SQL expert for NHL hockey analytics. Generate valid DuckDB SQL queries.

DATABASE: nhl (MotherDuck / DuckDB)

KEY RULES:
- Always use table names without schema prefix (just: games, team_game_stats, player_game_stats, etc.)
- team_abbr values are uppercase 3-letter codes: TOR, BOS, MTL, NYR, EDM, CGY, VAN, etc.
- season format is BIGINT like 20242025 (year the season starts + year it ends)
- game_type = '2' for regular season, '3' for playoffs
- For player trends: use player_game_stats (has names). For raw: use game_players + JOIN players.
- For team trends: use team_game_stats (one row per team per game). For game level: use games.
- toi_seconds: divide by 60 for minutes
- is_home BOOLEAN: true = home game
- Always add LIMIT (default 20, max 500) unless aggregating
- For "recent games" use ORDER BY game_date DESC
- For standings points use team_points (2=win, 1=OT loss, 0=loss)
- JOIN key: teams.abbr = team_game_stats.team_abbr (NOT teams.id)
- For current form use player_rolling_stats WHERE game_recency_rank = 1
- For AI insights use agent_insights ORDER BY generated_at DESC

TABLES AVAILABLE:
games, team_game_stats, team_game_stats_extended, player_game_stats, game_players,
game_events, game_stories, teams, players, roster, schedule, playoff_brackets,
standings, skater_stats, goalie_stats, team_stats, edge_skaters, edge_goalies, edge_teams,
agent_insights, player_rolling_stats, goalie_rolling_stats, team_rolling_stats, team_corsi

FEATURE STORE:
- Current player form: player_rolling_stats WHERE game_recency_rank = 1 AND season = (SELECT MAX(season) FROM games WHERE game_type = '2')
- AI insights: SELECT headline, body, entity_name, team_abbr, insight_type, zscore, game_date FROM agent_insights ORDER BY generated_at DESC LIMIT 10
- Corsi outliers: SELECT * FROM team_corsi WHERE corsi_pct < 0.42 OR corsi_pct > 0.58 ORDER BY game_date DESC LIMIT 20

Return ONLY the SQL query, no explanation, no markdown code blocks."""


def _client() -> OpenAI:
    base = os.environ.get("LITELLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LITELLM_API_KEY", "")
    return OpenAI(base_url=f"{base}/v1", api_key=key)


def _clean_sql(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    return (m.group(1) if m else text).strip()


def text_to_sql(question: str) -> str:
    resp = _client().chat.completions.create(
        model="gemini-flash",
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        max_tokens=500,
        temperature=0,
    )
    return _clean_sql(resp.choices[0].message.content or "")


def fix_sql(question: str, previous_sql: str, error: str) -> str:
    resp = _client().chat.completions.create(
        model="gemini-flash",
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original question:\n{question}\n\n"
                    f"Previous SQL (failed):\n{previous_sql}\n\n"
                    f"Execution error:\n{error}\n\n"
                    "Return corrected DuckDB SQL only. Must be SELECT and include LIMIT."
                ),
            },
        ],
        max_tokens=500,
        temperature=0,
    )
    return _clean_sql(resp.choices[0].message.content or "")


def summarise(question: str, rows: list[dict]) -> str:
    resp = _client().chat.completions.create(
        model="groq-llama-fast",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an NHL analytics expert. Given a user question and query results, "
                    "write a concise 2-3 sentence summary in English. Use specific numbers. No fluff."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nResults (first 10 rows):\n{rows[:10]}",
            },
        ],
        max_tokens=200,
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()
