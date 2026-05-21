"""Chat with data – natural language to SQL to results."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import re
import streamlit as st
import pandas as pd
import plotly.express as px

from lib.db import query_fresh, query, LEAGUE_LABELS
from lib.litellm_client import text_to_sql, fix_sql, summarise_stream
from lib.sidebar import render as _render_sidebar
from lib.auth import require_login
from lib.entitlements import ai_queries_remaining, record_ai_query, has_feature

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ask AI – THA Analytics",
    page_icon="tha_icon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
_render_sidebar()
require_login()

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# Consume prefill set by "Ask AI about..." buttons on other pages
_prefill_question: str | None = st.session_state.pop("chat_prefill", None)

# ── Constants ──────────────────────────────────────────────────────────────────
BLOCKED_KEYWORDS = [
    "drop", "delete", "insert", "update", "create",
    "alter", "truncate", "grant", "revoke",
]

_STATIC_EXAMPLES_BY_LEAGUE: dict[str, list[str]] = {
    "nhl": [
        "Who are the top 10 scorers this season?",
        "Which teams have the best power play percentage?",
        "Show me Connor McDavid's last 10 games",
        "What goalies have the best save percentage with 20+ games?",
        "Which teams are on a winning streak right now?",
        "Compare Boston and Toronto's goals for vs goals against",
    ],
    "shl": [
        "Who are the top scorers in Sweden this season?",
        "Show the SHL standings",
        "Which Swedish team has scored the most goals?",
        "Top points leaders in SHL",
        "Best goals per game in SHL",
        "Player points per game in SHL",
    ],
    "nor": [
        "Top goal scorers in Eliteserien",
        "Current Eliteserien standings",
        "Most goals scored in the latest season",
        "Which team has the best home record?",
        "Most penalties in Eliteserien this season",
        "Top teams by goal differential",
    ],
    "sui": [
        "Top scorers in Swiss hockey this season",
        "Current Swiss league standings",
        "Best goalie save percentage in Swiss hockey",
        "Which team has scored the most goals?",
        "Most recent Swiss league games",
        "Top teams by power play percentage",
    ],
    "liiga": [
        "Top goal scorers in Liiga",
        "Liiga standings for the current season",
        "Most goals in recent Liiga games",
        "Which teams are at the top of Liiga?",
        "Most goals scored by a team this season",
        "Game results from the last week",
    ],
    "met": [
        "Top scorers in Metal Ligaen",
        "Current Metal Ligaen standings",
        "Best goalie stats in Metal Ligaen",
        "Which team has the most wins?",
        "Recent Metal Ligaen results",
        "Top teams by goal difference",
    ],
}

_GREEN   = "#5a8f4e"
_PALETTE = [_GREEN, "#87ceeb", "#f97316", "#c41e3a", "#a78bfa"]

_CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=28, b=0),
    height=260,
    font=dict(color="#8896a8", size=11),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", showline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.chat-error-card {
    background: rgba(201,62,58,0.12);
    border: 1px solid rgba(201,62,58,0.35);
    border-radius: 6px;
    padding: 12px 16px;
    color: #f87171;
    font-size: 13px;
    line-height: 1.5;
    margin: 4px 0;
}
.chat-quota-badge {
    display: inline-block;
    font-size: 11px;
    color: #8896a8;
    margin-bottom: 14px;
}
.chat-quota-badge.warn { color: #fb923c; }
.row-count {
    color: #8896a8;
    font-size: 11px;
    margin: 2px 0 6px;
}
</style>
""", unsafe_allow_html=True)


# ── Helper functions ───────────────────────────────────────────────────────────

def _safe_sql(sql: str) -> tuple[bool, str]:
    """Validate SQL safety; auto-append LIMIT 200 if missing."""
    stripped = sql.strip()
    if not stripped:
        return False, "Empty SQL returned by model."
    lower = stripped.lower()
    if not re.match(r"^\s*select\b", lower):
        return False, "Only SELECT queries are allowed."
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", lower):
            return False, f"Blocked keyword: '{kw}'. Only read-only queries allowed."
    if "limit" not in lower:
        stripped = stripped.rstrip(";").rstrip() + " LIMIT 200"
    return True, stripped


def _error_card(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="chat-error-card"><strong>Error:</strong> {safe}</div>'


def _looks_like_date(series: pd.Series) -> bool:
    try:
        sample = series.dropna().iloc[0]
        return bool(re.match(r"\d{4}-\d{2}-\d{2}", str(sample)))
    except Exception:
        return False


def _try_chart(df: pd.DataFrame):
    """Return a Plotly Figure if the DataFrame shape suits a chart, else None."""
    if len(df) < 2 or len(df.columns) < 2:
        return None

    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols:
        return None

    date_col = next(
        (c for c in df.columns if c not in num_cols and (
            "date" in c.lower()
            or pd.api.types.is_datetime64_any_dtype(df[c])
            or (df[c].dtype == object and _looks_like_date(df[c]))
        )),
        None,
    )

    cat_cols = [c for c in df.columns if c not in num_cols and c != date_col]

    if date_col and len(df) >= 3:
        color_by = (
            cat_cols[0]
            if len(cat_cols) == 1 and df[cat_cols[0]].nunique() <= 8
            else None
        )
        fig = px.line(
            df.sort_values(date_col),
            x=date_col,
            y=num_cols[0],
            color=color_by,
            color_discrete_sequence=_PALETTE,
        )
        fig.update_traces(line_width=2)
        fig.update_layout(**_CHART_LAYOUT)
        return fig

    if cat_cols and 2 <= len(df) <= 25 and df[cat_cols[0]].nunique() <= 25:
        fig = px.bar(
            df.sort_values(num_cols[0], ascending=False),
            x=cat_cols[0],
            y=num_cols[0],
            color_discrete_sequence=[_GREEN],
        )
        fig.update_layout(**_CHART_LAYOUT, xaxis_tickangle=-30)
        return fig

    return None


def _build_sql_history() -> list[tuple[str, str]]:
    """Extract the last ≤3 (question, sql) pairs from chat history."""
    pairs = []
    msgs = st.session_state.messages
    i = 0
    while i < len(msgs) - 1:
        u, a = msgs[i], msgs[i + 1]
        if u["role"] == "user" and a["role"] == "assistant" and a.get("sql"):
            pairs.append((u["content"], a["sql"]))
        i += 2
    return pairs[-3:]


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_dynamic_questions(league: str = "nhl") -> list[str]:
    """Generate contextual question suggestions. NHL uses agent_insights; others use static list."""
    static = _STATIC_EXAMPLES_BY_LEAGUE.get(league, _STATIC_EXAMPLES_BY_LEAGUE["nhl"])
    if league != "nhl":
        return static[:6]
    try:
        df = query(
            "SELECT entity_name, team_abbr, insight_type "
            "FROM agent_insights ORDER BY ABS(zscore) DESC LIMIT 8",
            league="nhl",
        )
        questions: list[str] = []
        seen: set[str] = set()
        for _, row in df.iterrows():
            name  = str(row.get("entity_name") or "").strip()
            team  = str(row.get("team_abbr") or "").strip()
            itype = str(row.get("insight_type") or "").lower()
            if not name or name in seen:
                continue
            seen.add(name)
            if "goalie" in itype:
                questions.append(f"What are {name}'s save% stats this season?")
            elif "player" in itype:
                questions.append(f"Show me {name}'s recent game stats")
            elif "team" in itype and team:
                questions.append(f"How has {team} been performing recently?")
            else:
                questions.append(f"Tell me about {name}")
        for q in static:
            if len(questions) >= 6:
                break
            if q not in questions:
                questions.append(q)
        return questions[:6]
    except Exception:
        return static[:6]


def _render_message(msg: dict, key_suffix: str = "0") -> None:
    """Render a stored chat message (used for history replay)."""
    if msg["role"] == "user":
        st.markdown(msg["content"])
        return

    if msg.get("error"):
        st.markdown(_error_card(msg["error"]), unsafe_allow_html=True)
    else:
        if msg.get("content"):
            st.markdown(msg["content"])

        df: pd.DataFrame | None = msg.get("df")
        if df is not None:
            if df.empty:
                st.markdown(
                    "<p style='color:#8896a8;font-size:13px;font-style:italic;'>"
                    "No data found for that query.</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<p class='row-count'>{len(df):,} row{'s' if len(df) != 1 else ''} returned</p>",
                    unsafe_allow_html=True,
                )
                fig = _try_chart(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.dataframe(df, use_container_width=True, hide_index=True)
                if has_feature("export_csv"):
                    st.download_button(
                        "Download CSV",
                        df.to_csv(index=False).encode(),
                        "results.csv",
                        "text/csv",
                        key=f"dl_{key_suffix}",
                    )

    if msg.get("sql"):
        with st.expander("Show SQL", expanded=False):
            st.code(msg["sql"], language="sql")


def _ask(question: str) -> None:
    """Core pipeline: question → SQL → execute → stream summary → store."""
    active_league = st.session_state.get("active_league", "nhl")

    # ── Quota gate ─────────────────────────────────────────────────────────────
    remaining = ai_queries_remaining()
    if remaining <= 0:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            st.markdown(
                '<div class="chat-error-card">'
                "<strong>Daily limit reached.</strong> "
                'Upgrade to Plus for unlimited AI queries. '
                '<a href="/Account" style="color:#fb923c;text-decoration:none;">Upgrade →</a>'
                "</div>",
                unsafe_allow_html=True,
            )
        st.session_state.messages.append({
            "role": "assistant", "content": "", "sql": "", "df": None,
            "error": "Daily AI query limit reached. Upgrade for unlimited access.",
        })
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        sql     = ""
        df: pd.DataFrame | None = None
        summary = ""
        error: str | None = None

        # ── Phase 1: Generate SQL ──────────────────────────────────────────────
        with st.spinner("Generating SQL…"):
            try:
                history = _build_sql_history()
                sql = text_to_sql(question, history, league=active_league)
            except Exception as exc:
                error = f"SQL generation failed: {exc}"

        # ── Phase 2: Validate ──────────────────────────────────────────────────
        if not error:
            ok, result = _safe_sql(sql)
            if not ok:
                error = result
            else:
                sql = result

        # ── Phase 3: Execute ───────────────────────────────────────────────────
        if not error:
            record_ai_query()
            with st.spinner("Running query…"):
                try:
                    df = query_fresh(sql, league=active_league)
                except Exception as exec_err:
                    with st.spinner("Auto-fixing SQL…"):
                        try:
                            fixed = fix_sql(question, sql, str(exec_err), league=active_league)
                            ok2, r2 = _safe_sql(fixed)
                            if not ok2:
                                error = f"Auto-fix produced unsafe SQL: {r2}"
                            else:
                                df = query_fresh(r2, league=active_league)
                                sql = r2
                        except Exception as fix_err:
                            error = (
                                f"Query failed: {exec_err}\n"
                                f"Auto-fix also failed: {fix_err}"
                            )

        # ── Phase 4: Render ────────────────────────────────────────────────────
        if error:
            st.markdown(_error_card(error), unsafe_allow_html=True)
        elif df is not None:
            if df.empty:
                st.markdown(
                    "<p style='color:#8896a8;font-size:13px;font-style:italic;'>"
                    "No data found. Try rephrasing or broadening the filters.</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<p class='row-count'>{len(df):,} row{'s' if len(df) != 1 else ''} returned</p>",
                    unsafe_allow_html=True,
                )
                gen = summarise_stream(question, df.head(10).to_dict("records"), league=active_league)
                summary = st.write_stream(gen) or ""

                fig = _try_chart(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                st.dataframe(df, use_container_width=True, hide_index=True)

                if has_feature("export_csv"):
                    st.download_button(
                        "Download CSV",
                        df.to_csv(index=False).encode(),
                        "results.csv",
                        "text/csv",
                        key="dl_live",
                    )

        if sql:
            with st.expander("Show SQL", expanded=False):
                st.code(sql, language="sql")

        st.session_state.messages.append({
            "role": "assistant",
            "content": summary,
            "sql": sql,
            "df": df,
            "error": error,
        })


# ── Page header ────────────────────────────────────────────────────────────────
active_league = st.session_state.get("active_league", "nhl")
league_label  = LEAGUE_LABELS.get(active_league, "NHL")

header_col, clear_col = st.columns([6, 1])
with header_col:
    st.markdown(
        f"<h1 style='font-size:26px;font-weight:900;letter-spacing:-0.02em;margin-bottom:4px;'>"
        f"Ask AI</h1>"
        f"<p style='color:#8896a8;font-size:13px;margin-bottom:6px;'>"
        f"Ask anything about {league_label} data in natural language</p>",
        unsafe_allow_html=True,
    )
    _remaining = ai_queries_remaining()
    if _remaining < 9999:
        _cls = "chat-quota-badge warn" if _remaining <= 3 else "chat-quota-badge"
        _label = f"{_remaining} AI quer{'y' if _remaining == 1 else 'ies'} remaining today"
        st.markdown(f'<span class="{_cls}">{_label}</span>', unsafe_allow_html=True)
    else:
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

with clear_col:
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    if st.button("Clear chat", key="clear_chat", type="secondary"):
        st.session_state.messages = []
        st.rerun()

# ── Empty state: dynamic question chips ────────────────────────────────────────
clicked_example: str | None = None

if not st.session_state.messages:
    example_questions = _fetch_dynamic_questions(active_league)
    st.markdown(
        "<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
        "letter-spacing:0.08em;color:#8896a8;margin-bottom:10px;'>Try these</p>",
        unsafe_allow_html=True,
    )
    row1 = st.columns(3)
    row2 = st.columns(3)
    for i, q in enumerate(example_questions):
        col = (row1 if i < 3 else row2)[i % 3]
        with col:
            if st.button(q, key=f"chip_{i}", use_container_width=True, type="secondary"):
                clicked_example = q
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ── Chat history ───────────────────────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        _render_message(msg, key_suffix=str(i))

# ── Chat input ─────────────────────────────────────────────────────────────────
question = st.chat_input(f"Ask a question about {league_label} data…") or clicked_example or _prefill_question

if question:
    _ask(question)
