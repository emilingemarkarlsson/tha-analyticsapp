"""Entitlement system – plan tiers, feature gates, and paywall rendering.

Usage:
    from lib.entitlements import gate, has_feature, get_plan, ai_queries_remaining

    # Hard gate: stops rendering and shows paywall if not allowed
    gate("deep_dive_career", "Career & Splits")

    # Soft check: returns bool
    if has_feature("watchlist"):
        ...

    # AI quota check
    remaining = ai_queries_remaining()
    if remaining <= 0:
        gate("ai_chat_unlimited", "Unlimited AI")
"""
from __future__ import annotations
import streamlit as st

# ── Plan hierarchy ─────────────────────────────────────────────────────────────
PLANS: dict[str, int] = {
    "free": 0,
    "base": 1,
    "plus": 2,
    "club": 3,
}

PLAN_LABELS: dict[str, str] = {
    "free": "Free",
    "base": "Base",
    "plus": "Plus",
    "club": "Club",
}

PLAN_PRICES: dict[str, str] = {
    "free": "Gratis",
    "base": "9 SEK/mån",
    "plus": "39 SEK/mån",
    "club": "På förfrågan",
}

PLAN_COLORS: dict[str, str] = {
    "free": "#8896a8",
    "base": "#5a8f4e",
    "plus": "#f97316",
    "club": "#87ceeb",
}

# ── Feature matrix ─────────────────────────────────────────────────────────────
# Maps feature_key → minimum plan required
FEATURES: dict[str, str] = {
    # Deep Dive
    "deep_dive_career":         "base",
    "deep_dive_splits":         "base",
    "deep_dive_goalies":        "free",
    # Watchlist
    "watchlist":                "base",
    "watchlist_unlimited":      "plus",   # >10 players
    # Player Finder
    "screener_full":            "base",   # all filters
    # History depth
    "history_5seasons":         "base",
    "history_full":             "plus",   # all 16 seasons
    # AI Chat
    "ai_chat":                  "free",   # limited by AI_QUERY_LIMITS
    "ai_chat_unlimited":        "plus",
    # Export
    "export_csv":               "plus",
    # Leagues
    "league_shl":               "plus",
    # API / Club
    "api_access":               "club",
    "scouting_notes":           "club",
}

# ── Usage limits ───────────────────────────────────────────────────────────────
AI_QUERY_LIMITS: dict[str, int] = {
    "free": 5,
    "base": 30,
    "plus": 9999,
    "club": 9999,
}

WATCHLIST_LIMITS: dict[str, int] = {
    "free": 0,
    "base": 10,
    "plus": 9999,
    "club": 9999,
}

HISTORY_SEASON_LIMITS: dict[str, int] = {
    "free": 1,
    "base": 5,
    "plus": 16,
    "club": 16,
}


# ── Plan helpers ───────────────────────────────────────────────────────────────

def _current_user_id() -> str:
    """Return Supabase user_id from session, or '' if not logged in."""
    user = st.session_state.get("sb_user")
    return user["id"] if user else ""


def get_plan(user_id: str | None = None) -> str:
    """Return plan string for the current (or given) user."""
    if user_id is None:
        user_id = _current_user_id()
    if not user_id:
        return "free"
    from lib import userdb
    return userdb.get_user_plan(user_id)


def plan_level(user_id: str | None = None) -> int:
    """Return numeric plan level (0=free, 1=base, 2=plus, 3=club)."""
    return PLANS.get(get_plan(user_id), 0)


def has_feature(feature_key: str, user_id: str | None = None) -> bool:
    """Return True if the current user's plan grants access to feature_key."""
    required = FEATURES.get(feature_key, "free")
    return plan_level(user_id) >= PLANS.get(required, 0)


# ── AI quota ───────────────────────────────────────────────────────────────────

def ai_queries_remaining(user_id: str | None = None) -> int:
    """Return how many AI queries the user has left today."""
    if user_id is None:
        user_id = _current_user_id()
    plan = get_plan(user_id)
    limit = AI_QUERY_LIMITS.get(plan, 5)
    if limit >= 9999:
        return 9999
    from lib import userdb
    used = userdb.ai_queries_today(user_id)
    return max(0, limit - used)


def record_ai_query(user_id: str | None = None) -> int:
    """Increment AI query counter and return remaining queries."""
    if user_id is None:
        user_id = _current_user_id()
    if not user_id:
        return 0
    from lib import userdb
    userdb.increment_ai_query(user_id)
    return ai_queries_remaining(user_id)


# ── Watchlist helpers ──────────────────────────────────────────────────────────

def watchlist_slots_remaining(user_id: str | None = None) -> int:
    """Return how many more watchlist slots the user has."""
    if user_id is None:
        user_id = _current_user_id()
    plan = get_plan(user_id)
    limit = WATCHLIST_LIMITS.get(plan, 0)
    if limit >= 9999:
        return 9999
    from lib import userdb
    used = userdb.watchlist_count(user_id)
    return max(0, limit - used)


# ── HTML helpers ───────────────────────────────────────────────────────────────

def plan_badge_html(plan: str | None = None) -> str:
    """Return a colored plan badge <span>."""
    if plan is None:
        plan = get_plan()
    color = PLAN_COLORS.get(plan, "#8896a8")
    label = PLAN_LABELS.get(plan, plan.title())
    return (
        f'<span style="background:{color}22;border:1px solid {color}55;color:{color};'
        f'font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;'
        f'text-transform:uppercase;letter-spacing:0.06em;">{label}</span>'
    )


def _paywall_html(feature_name: str, min_plan: str, description: str = "") -> str:
    color      = PLAN_COLORS.get(min_plan, "#5a8f4e")
    label      = PLAN_LABELS.get(min_plan, min_plan.title())
    price      = PLAN_PRICES.get(min_plan, "")
    desc_html  = (
        f'<p style="color:#8896a8;font-size:11px;margin:6px 0 0;line-height:1.5;">{description}</p>'
        if description else ""
    )
    return f"""
    <div style="background:{color}0d;border:1px solid {color}33;border-radius:8px;
                padding:20px 24px;text-align:center;margin:12px 0;">
      <div style="font-size:20px;margin-bottom:8px;">🔒</div>
      <div style="color:#fff;font-weight:700;font-size:14px;margin-bottom:4px;">{feature_name}</div>
      <div style="color:#8896a8;font-size:11px;margin-bottom:12px;">
        Kräver <span style="color:{color};font-weight:700;">{label}-plan</span>
        {f'· {price}' if price else ''}
      </div>
      {desc_html}
      <a href="/Account" target="_self"
         style="display:inline-block;margin-top:12px;background:{color};color:#fff;
                font-size:11px;font-weight:700;padding:7px 18px;border-radius:4px;
                text-decoration:none;letter-spacing:0.04em;">
        Uppgradera →
      </a>
    </div>"""


def gate(feature_key: str, feature_name: str = "", description: str = "") -> None:
    """Check feature access; render paywall and call st.stop() if not allowed.

    Call at the start of a tab or section to hard-block access:
        gate("deep_dive_career", "Career & Splits")
    """
    if has_feature(feature_key):
        return
    min_plan = FEATURES.get(feature_key, "base")
    display  = feature_name or feature_key.replace("_", " ").title()
    st.html(_paywall_html(display, min_plan, description))
    st.stop()


def soft_gate(feature_key: str, feature_name: str = "", description: str = "") -> bool:
    """Return True if user has access; render paywall block (without stopping) if not.

    Use when you want to show a paywall inline without halting the whole page.
    """
    if has_feature(feature_key):
        return True
    min_plan = FEATURES.get(feature_key, "base")
    display  = feature_name or feature_key.replace("_", " ").title()
    st.html(_paywall_html(display, min_plan, description))
    return False
