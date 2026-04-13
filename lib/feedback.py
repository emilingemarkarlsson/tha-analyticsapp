"""Telegram feedback/support sender."""
import os
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv

load_dotenv()

_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
_THREAD_ID = os.environ.get("TELEGRAM_THREAD_ID", "")


def send_feedback(kind: str, message: str, user_email: str = "") -> tuple[bool, str]:
    """Send a feedback message to the Telegram Contacts topic.

    Returns (success, error_message).
    """
    if not _TOKEN or not _CHAT_ID:
        return False, "Telegram not configured."

    kind_emoji = {"Feedback": "💬", "Bug report": "🐛", "Question": "❓"}.get(kind, "📩")
    sender = user_email or "anonymous"

    text = (
        f"{kind_emoji} <b>{kind}</b>\n"
        f"<i>From: {sender}</i>\n\n"
        f"{message}"
    )

    payload: dict = {
        "chat_id": _CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if _THREAD_ID:
        payload["message_thread_id"] = int(_THREAD_ID)

    try:
        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read())
            if body.get("ok"):
                return True, ""
            return False, body.get("description", "Unknown error")
    except Exception as exc:
        return False, str(exc)
