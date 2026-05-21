"""PostgreSQL auth helpers — bcrypt + session tokens. Call require_login() at top of every protected page."""
import os
import secrets
import hashlib
import datetime
import streamlit as st
import psycopg2
import psycopg2.extras
import bcrypt
from dotenv import load_dotenv

load_dotenv()

_COOKIE_KEY = "tha_auth"


def _conn():
    return psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        connect_timeout=5,
    )


def _cc():
    from streamlit_cookies_controller import CookieController
    return CookieController(key="tha_cc")


def get_user() -> dict | None:
    """Return the logged-in user dict from session_state, or None."""
    return st.session_state.get("sb_user")


def _verify_session_token(raw_token: str) -> dict | None:
    """Validate token against sessions table; return user dict or None."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT u.id, u.email, u.full_name, u.created_at
                    FROM sessions s
                    JOIN users u ON u.id = s.user_id
                    WHERE s.token_hash = %s AND s.expires_at > NOW() AND u.is_active = TRUE
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE users SET last_login_at = NOW() WHERE id = %s",
                        (str(row["id"]),),
                    )
                return dict(row) if row else None
    except Exception:
        return None


def _create_session(user_id: str) -> str:
    """Insert a session row; return the raw token to store in cookie."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                (user_id, token_hash, expires),
            )
    return raw_token


def require_login() -> dict:
    """Restore session from cookie if needed; redirect to login if unauthenticated.

    Uses the two-pass pattern: first render the CookieController component loads
    (st.stop()), second render the cookie value is available.
    """
    if get_user():
        return get_user()

    try:
        cc = _cc()
        raw_token = cc.get(_COOKIE_KEY)

        if raw_token is None:
            if not st.session_state.get("_cc_waited"):
                st.session_state["_cc_waited"] = True
                st.stop()
            # Second render — genuinely no cookie → fall through to redirect
        else:
            st.session_state["_cc_waited"] = False
            user = _verify_session_token(str(raw_token))
            if user:
                st.session_state["sb_user"] = {
                    "id": str(user["id"]),
                    "email": user["email"],
                    "full_name": user.get("full_name") or "",
                    "created_at": str(user["created_at"]),
                }
                st.rerun()
    except Exception:
        pass

    st.session_state["_cc_waited"] = False
    st.switch_page("pages/0_Login.py")
    return None


def sign_in(email: str, password: str) -> tuple[bool, str]:
    """Sign in with email + password. Returns (success, error_message)."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, email, password_hash, full_name, is_active, created_at FROM users WHERE email = %s",
                    (email.lower().strip(),),
                )
                row = cur.fetchone()

        if not row:
            return False, "Invalid email or password."
        if not row["is_active"]:
            return False, "Account is disabled."
        if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return False, "Invalid email or password."

        user_id = str(row["id"])
        raw_token = _create_session(user_id)

        st.session_state["sb_user"] = {
            "id": user_id,
            "email": row["email"],
            "full_name": row.get("full_name") or "",
            "created_at": str(row["created_at"]),
        }
        try:
            _cc().set(_COOKIE_KEY, raw_token, max_age=60 * 60 * 24 * 30)
        except Exception:
            pass
        return True, ""
    except Exception as e:
        return False, f"Sign-in error: {e}"


def sign_up(email: str, password: str, full_name: str = "") -> tuple[bool, str]:
    """Create a new account. Returns (success, error_message)."""
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    try:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s)",
                    (email.lower().strip(), pw_hash, full_name or None),
                )
        return True, ""
    except psycopg2.errors.UniqueViolation:
        return False, "That email address is already registered."
    except Exception as e:
        return False, f"Sign-up error: {e}"


def change_password(user_id: str, new_password: str) -> tuple[bool, str]:
    """Update password for an authenticated user."""
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters."
    try:
        pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (pw_hash, user_id),
                )
        return True, ""
    except Exception as e:
        return False, f"Error: {e}"


def sign_out() -> None:
    """Sign out, delete session from DB, clear cookie and session_state."""
    raw_token = None
    try:
        cc = _cc()
        raw_token = cc.get(_COOKIE_KEY)
        cc.remove(_COOKIE_KEY)
    except Exception:
        pass

    if raw_token:
        try:
            token_hash = hashlib.sha256(str(raw_token).encode()).hexdigest()
            with _conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
        except Exception:
            pass

    st.session_state.pop("sb_user", None)
    st.session_state.pop("_cc_waited", None)
