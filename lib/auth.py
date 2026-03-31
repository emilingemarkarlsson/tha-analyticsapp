"""Supabase auth helpers – call require_login() at top of every protected page."""
import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource(show_spinner=False)
def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_ANON_KEY not set")
    return create_client(url, key)


def get_user() -> dict | None:
    """Return the logged-in user dict from session_state, or None."""
    return st.session_state.get("sb_user")


def require_login() -> dict:
    """Redirect to login page if not authenticated. Returns user dict if ok."""
    user = get_user()
    if not user:
        st.switch_page("pages/0_Login.py")
    return user


def sign_in(email: str, password: str) -> tuple[bool, str]:
    """Sign in with email + password. Returns (success, error_message)."""
    try:
        sb = _get_client()
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["sb_user"] = {
            "id": res.user.id,
            "email": res.user.email,
            "created_at": str(res.user.created_at),
        }
        st.session_state["sb_session"] = res.session.access_token
        return True, ""
    except Exception as e:
        msg = str(e)
        if "Invalid login" in msg or "invalid_credentials" in msg:
            return False, "Invalid email or password."
        return False, f"Sign-in error: {msg}"


def sign_up(email: str, password: str) -> tuple[bool, str]:
    """Create a new account. Returns (success, error_message)."""
    try:
        sb = _get_client()
        res = sb.auth.sign_up({"email": email, "password": password})
        if res.user and res.user.identities == []:
            return False, "That email address is already registered."
        return True, ""
    except Exception as e:
        msg = str(e)
        if "Password should be" in msg:
            return False, "Password must be at least 6 characters."
        return False, f"Sign-up error: {msg}"


def sign_out() -> None:
    """Sign out and clear session."""
    try:
        _get_client().auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("sb_user", None)
    st.session_state.pop("sb_session", None)
