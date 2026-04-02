"""Shared UI components – ensures visual consistency across all pages."""
from __future__ import annotations
import streamlit as st


# ── Design tokens ──────────────────────────────────────────────────────────────
GREEN   = "#5a8f4e"
RED     = "#c41e3a"
ORANGE  = "#f97316"
BLUE    = "#87ceeb"
MUTED   = "#8896a8"
WHITE   = "#fff"
CARD_BG = "rgba(255,255,255,0.03)"
CARD_BR = "rgba(255,255,255,0.08)"


# ── Page headers ───────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str, data_date: str | None = None) -> None:
    """Render a consistent page title + subtitle + optional data freshness tag."""
    date_tag = ""
    if data_date:
        date_tag = (
            f"<span style='margin-left:12px;background:rgba(90,143,78,0.12);"
            f"border:1px solid rgba(90,143,78,0.3);border-radius:3px;"
            f"padding:2px 8px;font-size:10px;color:{GREEN};"
            f"font-family:monospace;letter-spacing:0.04em;'>data: {data_date}</span>"
        )
    st.markdown(
        f"<h1 style='font-size:26px;font-weight:900;letter-spacing:-0.02em;"
        f"margin-bottom:4px;display:flex;align-items:center;gap:0;'>"
        f"{title}{date_tag}</h1>"
        f"<p style='color:{MUTED};font-size:13px;margin-bottom:20px;'>{subtitle}</p>",
        unsafe_allow_html=True,
    )


def section_label(text: str, margin_top: int = 16) -> None:
    """Small uppercase section label used above tables/charts."""
    st.markdown(
        f"<p style='font-size:10px;font-weight:600;text-transform:uppercase;"
        f"letter-spacing:0.08em;color:{MUTED};margin:{margin_top}px 0 8px;'>{text}</p>",
        unsafe_allow_html=True,
    )


# ── Methodology & trust ────────────────────────────────────────────────────────

def methodology_note(text: str) -> None:
    """Small italic footnote explaining a metric or methodology."""
    st.markdown(
        f"<p style='color:{MUTED};font-size:11px;font-style:italic;"
        f"line-height:1.6;margin-top:6px;border-left:2px solid rgba(255,255,255,0.1);"
        f"padding-left:10px;'>{text}</p>",
        unsafe_allow_html=True,
    )


def perf_tier(z: float) -> tuple[str, str]:
    """Return (label, hex_color) for a z-score — used for badges and text."""
    if z >= 1.5:  return ("ELITE",     "#ff6b2b")
    if z >= 0.8:  return ("HOT",       ORANGE)
    if z >= 0.3:  return ("ABOVE AVG", GREEN)
    if z > -0.3:  return ("STEADY",    MUTED)
    if z > -0.8:  return ("BELOW AVG", "#6b8cad")
    if z > -1.5:  return ("COLD",      BLUE)
    return ("SLUMP", "#4a9eda")


def tier_badge_html(z: float, show_z: bool = True) -> str:
    """Render a performance tier badge + optional z-score value."""
    label, color = perf_tier(z)
    z_part = (
        f"<span style='color:{color};font-family:monospace;font-size:11px;"
        f"font-weight:700;margin-left:5px;'>{z:+.2f}σ</span>"
        if show_z else ""
    )
    return (
        f"<span style='background:{color}18;border:1px solid {color}44;"
        f"color:{color};padding:2px 7px;border-radius:3px;font-size:10px;"
        f"font-weight:700;letter-spacing:0.05em;white-space:nowrap;'>{label}</span>"
        f"{z_part}"
    )


def zscore_legend(with_title: bool = True) -> None:
    """Standard z-score colour legend used on Players, Screener, Feed."""
    title = "<p style='font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#8896a8;margin-bottom:6px;'>Momentum legend</p>" if with_title else ""
    st.markdown(
        f"{title}"
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:{MUTED};margin-bottom:12px;'>"
        f"<span><span style='color:{ORANGE};font-weight:700;'>+σ ≥ 1.0</span> Hot streak</span>"
        f"<span><span style='color:{GREEN};font-weight:700;'>+σ ≥ 0.5</span> Above baseline</span>"
        f"<span style='color:{MUTED};'>-0.5 to +0.5 Neutral</span>"
        f"<span><span style='color:{BLUE};font-weight:700;'>−σ ≤ -0.8</span> Slump</span>"
        f"<span style='color:{MUTED};font-style:italic;'>Compares last 5 games vs 20-game rolling average</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


def projection_disclaimer() -> None:
    """Show below any chart that includes a statistical projection."""
    st.markdown(
        f"<p style='color:{MUTED};font-size:10px;margin-top:-4px;'>"
        f"Projection uses polynomial regression (deg-2) on last 6 healthy seasons. "
        f"Confidence band = ±1 RMSE. Past performance does not guarantee future results.</p>",
        unsafe_allow_html=True,
    )


def data_source_footer(note: str = "") -> None:
    """Page footer with data attribution."""
    base = "NHL data via NHL Stats API · Processed daily · MotherDuck cloud database"
    full = f"{base} · {note}" if note else base
    st.markdown(
        f"<div style='margin-top:32px;padding-top:12px;"
        f"border-top:1px solid rgba(255,255,255,0.06);"
        f"color:{MUTED};font-size:10px;'>{full}</div>",
        unsafe_allow_html=True,
    )


# ── Stat cards ─────────────────────────────────────────────────────────────────

def stat_card(label: str, value: str, sub: str = "", color: str = WHITE) -> str:
    """Return HTML for a single stat card (use inside st.html or a row)."""
    return (
        f"<div style='background:{CARD_BG};border:1px solid {CARD_BR};"
        f"border-radius:5px;padding:12px 18px;min-width:110px;'>"
        f"<div style='color:{MUTED};font-size:10px;text-transform:uppercase;"
        f"letter-spacing:0.06em;margin-bottom:4px;'>{label}</div>"
        f"<div style='color:{color};font-weight:800;font-size:22px;"
        f"letter-spacing:-0.02em;line-height:1.1;'>{value}</div>"
        f"{'<div style=color:' + MUTED + ';font-size:10px;margin-top:2px;>' + sub + '</div>' if sub else ''}"
        f"</div>"
    )


def stat_card_row(cards: list[dict]) -> None:
    """Render a flex row of stat cards.
    cards = [{"label": ..., "value": ..., "sub": ..., "color": ...}, ...]
    """
    html = "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;'>"
    for c in cards:
        html += stat_card(
            c["label"], c["value"],
            sub=c.get("sub", ""),
            color=c.get("color", WHITE),
        )
    html += "</div>"
    st.html(html)


# ── Empty / error states ───────────────────────────────────────────────────────

def empty_state(message: str, hint: str = "") -> None:
    """Friendly empty state with optional hint."""
    st.markdown(
        f"<div style='text-align:center;padding:40px 20px;"
        f"border:1px dashed rgba(255,255,255,0.1);border-radius:8px;margin:20px 0;'>"
        f"<p style='color:{MUTED};font-size:14px;margin-bottom:6px;'>{message}</p>"
        f"{'<p style=color:rgba(255,255,255,0.3);font-size:12px;>' + hint + '</p>' if hint else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )


def inline_error(message: str) -> None:
    """Subtle inline error (less alarming than st.error for data misses)."""
    st.markdown(
        f"<div style='background:rgba(196,30,58,0.08);border:1px solid rgba(196,30,58,0.2);"
        f"border-radius:5px;padding:10px 14px;color:#e88;font-size:12px;'>{message}</div>",
        unsafe_allow_html=True,
    )
