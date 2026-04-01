"""Supabase auth helpers – call require_login() at top of every protected page."""
import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_COOKIE_KEY = "tha_auth"


@st.cache_resource(show_spinner=False)
def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_ANON_KEY not set")
    return create_client(url, key)


def _cc():
    """Return a fresh CookieController each render (component must re-mount per page load)."""
    from streamlit_cookies_controller import CookieController
    return CookieController(key="tha_cc")


def get_user() -> dict | None:
    """Return the logged-in user dict from session_state, or None."""
    return st.session_state.get("sb_user")


def require_login() -> dict:
    """Restore session from cookie if needed, redirect to login if unauthenticated.

    Uses a two-pass pattern: on first render the CookieController component loads
    and st.stop() lets Streamlit wait for the JS round-trip. On the second render
    the cookie value is available.
    """
    if get_user():
        return get_user()

    try:
        cc = _cc()
        token_data = cc.get(_COOKIE_KEY)

        if token_data is None:
            # Component hasn't responded yet (first render after session reset).
            # st.stop() holds this render; Streamlit reruns automatically when
            # the JS component sends back the cookie value.
            if not st.session_state.get("_cc_waited"):
                st.session_state["_cc_waited"] = True
                st.stop()
            # Second render: still None means genuinely no cookie → fall through
        else:
            st.session_state["_cc_waited"] = False
            if "|||" in str(token_data):
                access_token, refresh_token = str(token_data).split("|||", 1)
                res = _get_client().auth.set_session(access_token, refresh_token)
                if res.user:
                    st.session_state["sb_user"] = {
                        "id": res.user.id,
                        "email": res.user.email,
                        "created_at": str(res.user.created_at),
                    }
                    st.rerun()  # Rerender with auth set
    except Exception:
        pass

    st.session_state["_cc_waited"] = False
    st.switch_page("pages/0_Login.py")
    return None


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
        try:
            _cc().set(_COOKIE_KEY,
                      f"{res.session.access_token}|||{res.session.refresh_token}",
                      max_age=60 * 60 * 24 * 30)  # 30 days
        except Exception:
            pass
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
    try:
        _cc().remove(_COOKIE_KEY)
    except Exception:
        pass
    st.session_state.pop("sb_user", None)
    st.session_state.pop("sb_session", None)
    st.session_state.pop("_cc_waited", None)
