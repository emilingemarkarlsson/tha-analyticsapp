"""Supabase Postgres store for user data – plans, watchlists, rosters, AI usage.

Replaces the local SQLite store so the app works on stateless hosts
(Streamlit Community Cloud, Railway, Render, etc.).

Requires env vars:
    SUPABASE_URL         – project URL (same as for auth)
    SUPABASE_SERVICE_KEY – service role key (Settings → API → service_role)
                           NOT the anon key – service key bypasses RLS.
"""
import os
import datetime
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource(show_spinner=False)
def _sb() -> Client:
    """Return a cached Supabase client using the service role key."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_SERVICE_KEY not set. "
            "Add SUPABASE_SERVICE_KEY to your .env (Settings → API → service_role in Supabase dashboard)."
        )
    return create_client(url, key)


# ── User / Plan ─────────────────────────────────────────────────────────────────

def upsert_user(user_id: str, plan: str = "free") -> None:
    """Ensure a user row exists; insert with default plan if missing."""
    sb = _sb()
    existing = sb.table("users").select("user_id").eq("user_id", user_id).execute()
    if not existing.data:
        sb.table("users").insert({"user_id": user_id, "plan": plan}).execute()


def get_user_plan(user_id: str) -> str:
    """Return plan string for user_id, defaulting to 'free'."""
    result = _sb().table("users").select("plan").eq("user_id", user_id).execute()
    return result.data[0]["plan"] if result.data else "free"


def set_user_plan(user_id: str, plan: str,
                  stripe_customer_id: str = "", stripe_subscription_id: str = "") -> None:
    data: dict = {
        "user_id": user_id,
        "plan": plan,
        "plan_updated_at": datetime.datetime.utcnow().isoformat(),
    }
    if stripe_customer_id:
        data["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id:
        data["stripe_subscription_id"] = stripe_subscription_id
    _sb().table("users").upsert(data, on_conflict="user_id").execute()


# ── AI Usage ────────────────────────────────────────────────────────────────────

def ai_queries_today(user_id: str) -> int:
    """Return how many AI queries the user has made today."""
    today = datetime.date.today().isoformat()
    result = (
        _sb().table("ai_usage")
        .select("query_count")
        .eq("user_id", user_id)
        .eq("date", today)
        .execute()
    )
    return result.data[0]["query_count"] if result.data else 0


def increment_ai_query(user_id: str) -> int:
    """Increment today's AI query count and return new total."""
    today = datetime.date.today().isoformat()
    sb = _sb()
    result = (
        sb.table("ai_usage")
        .select("query_count")
        .eq("user_id", user_id)
        .eq("date", today)
        .execute()
    )
    if result.data:
        new_count = result.data[0]["query_count"] + 1
        sb.table("ai_usage").update({"query_count": new_count}).eq("user_id", user_id).eq("date", today).execute()
    else:
        new_count = 1
        sb.table("ai_usage").insert({"user_id": user_id, "date": today, "query_count": 1}).execute()
    return new_count


# ── Watchlist ───────────────────────────────────────────────────────────────────

def watchlist_add(player_id: str, player_name: str, team_abbr: str, position: str,
                  user_id: str = "") -> None:
    try:
        _sb().table("watchlist").insert({
            "user_id": user_id,
            "player_id": player_id,
            "player_name": player_name,
            "team_abbr": team_abbr,
            "position": position,
        }).execute()
    except Exception:
        pass  # row already exists (unique constraint)


def watchlist_remove(player_id: str, user_id: str = "") -> None:
    _sb().table("watchlist").delete().eq("user_id", user_id).eq("player_id", player_id).execute()


def watchlist_all(user_id: str = "") -> list[dict]:
    result = (
        _sb().table("watchlist")
        .select("player_id,player_name,team_abbr,position,added_at,note")
        .eq("user_id", user_id)
        .order("added_at", desc=True)
        .execute()
    )
    return result.data or []


def watchlist_ids(user_id: str = "") -> set[str]:
    result = (
        _sb().table("watchlist")
        .select("player_id")
        .eq("user_id", user_id)
        .execute()
    )
    return {r["player_id"] for r in (result.data or [])}


def watchlist_count(user_id: str = "") -> int:
    result = (
        _sb().table("watchlist")
        .select("player_id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return result.count or 0


def watchlist_note(player_id: str, note: str, user_id: str = "") -> None:
    (
        _sb().table("watchlist")
        .update({"note": note})
        .eq("user_id", user_id)
        .eq("player_id", player_id)
        .execute()
    )


# ── Rosters ─────────────────────────────────────────────────────────────────────

def roster_list(user_id: str = "") -> list[dict]:
    result = (
        _sb().table("rosters")
        .select("roster_id,name,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def roster_create(name: str, user_id: str = "") -> int:
    sb = _sb()
    existing = (
        sb.table("rosters")
        .select("roster_id")
        .eq("user_id", user_id)
        .eq("name", name)
        .execute()
    )
    if existing.data:
        return existing.data[0]["roster_id"]
    result = sb.table("rosters").insert({"user_id": user_id, "name": name}).execute()
    return result.data[0]["roster_id"]


def roster_delete(roster_id: int) -> None:
    _sb().table("rosters").delete().eq("roster_id", roster_id).execute()


def roster_add_player(roster_id: int, player_id: str, player_name: str,
                       team_abbr: str, position: str, salary_k: int = 0) -> None:
    try:
        _sb().table("roster_players").insert({
            "roster_id": roster_id,
            "player_id": player_id,
            "player_name": player_name,
            "team_abbr": team_abbr,
            "position": position,
            "salary_k": salary_k,
        }).execute()
    except Exception:
        pass  # duplicate


def roster_remove_player(roster_id: int, player_id: str) -> None:
    (
        _sb().table("roster_players")
        .delete()
        .eq("roster_id", roster_id)
        .eq("player_id", player_id)
        .execute()
    )


def roster_set_salary(roster_id: int, player_id: str, salary_k: int) -> None:
    (
        _sb().table("roster_players")
        .update({"salary_k": salary_k})
        .eq("roster_id", roster_id)
        .eq("player_id", player_id)
        .execute()
    )


def roster_players(roster_id: int) -> list[dict]:
    result = (
        _sb().table("roster_players")
        .select("player_id,player_name,team_abbr,position,salary_k,note,added_at")
        .eq("roster_id", roster_id)
        .order("position")
        .order("player_name")
        .execute()
    )
    return result.data or []
