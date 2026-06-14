"""Shared UI styling + components for the FinFlow dashboards (presentation only).

No engine logic here — just Streamlit rendering helpers used by both app.py
(read-only) and live_app.py (interactive), for a consistent professional look.
"""

from __future__ import annotations

import streamlit as st

FAMILY_COLORS = {
    "prod_incident": "#dc2626",
    "release_delay": "#d97706",
    "milestone_blockage": "#7c3aed",
    "service_ownership": "#2563eb",
    "design_decision": "#059669",
}
ACCENT_V1 = "#64748b"   # slate
ACCENT_V2 = "#2563eb"   # blue
DEMO_STEPS = ["Question", "V1", "Expert", "Gap", "Learning", "V2", "Metrics"]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; max-width: 1180px;}
        .ff-badge {display:inline-block; padding:2px 10px; border-radius:999px;
                   font-size:0.72rem; font-weight:600; color:#fff; margin:0 4px 2px 0;}
        .ff-chip {display:inline-block; padding:3px 11px; margin:2px 0; border-radius:6px;
                  background:#f1f5f9; color:#64748b; font-size:0.74rem; font-weight:600;}
        .ff-chip-on {background:#2563eb; color:#fff;}
        .ff-cite {font-family:ui-monospace,SFMono-Regular,monospace; font-size:0.72rem; color:#64748b;}
        .ff-title {font-weight:700; font-size:0.98rem; margin:0 0 .3rem 0;}
        .ff-muted {color:#64748b; font-size:0.8rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, color: str = "#64748b") -> str:
    return f'<span class="ff-badge" style="background:{color}">{text}</span>'


def family_badge(family: str) -> str:
    return badge(family.replace("_", " "), FAMILY_COLORS.get(family, "#64748b"))


def bool_badge(val: bool, true: str = "yes", false: str = "no") -> str:
    return badge(true if val else false, "#059669" if val else "#94a3b8")


def severity_badge(sev: str) -> str:
    return badge(sev, {"high": "#dc2626", "medium": "#d97706", "low": "#64748b"}.get(sev, "#64748b"))


def passfail(ok: bool) -> str:
    return badge("PASS" if ok else "FAIL", "#059669" if ok else "#dc2626")


def html(*parts: str) -> None:
    st.markdown(" ".join(parts), unsafe_allow_html=True)


def demo_flow(active: str | None = None) -> None:
    chips = [f'<span class="ff-chip {"ff-chip-on" if s == active else ""}">{s}</span>' for s in DEMO_STEPS]
    st.markdown(" &rarr; ".join(chips), unsafe_allow_html=True)


def conf_bar(value: float, label: str | None = None) -> None:
    pct = max(0.0, min(1.0, float(value or 0)))
    color = "#059669" if pct >= 0.7 else "#d97706" if pct >= 0.4 else "#dc2626"
    lab = f'<span class="ff-muted">{label} </span>' if label else ""
    st.markdown(
        f'{lab}<div style="background:#e5e7eb;border-radius:6px;height:7px;width:78%;display:inline-block;'
        f'vertical-align:middle"><div style="background:{color};width:{pct*100:.0f}%;height:7px;'
        f'border-radius:6px"></div></div> <span class="ff-muted">{pct:.2f}</span>',
        unsafe_allow_html=True,
    )


def _step_view(s):
    if isinstance(s, dict):
        return s.get("claim", ""), float(s.get("confidence", 0) or 0), s.get("cited", [])
    return s.claim, float(s.confidence or 0), list(s.cited_source_ids)


def answer_card(label: str, text: str, cited=None, accent: str = ACCENT_V2, steps=None) -> None:
    with st.container(border=True):
        st.markdown(f'<div class="ff-title" style="color:{accent}">{label}</div>', unsafe_allow_html=True)
        st.write(text or "_(empty)_")
        if cited:
            html('<span class="ff-cite">cited: ' + ", ".join(cited) + "</span>")
        if steps:
            with st.expander("reasoning path"):
                for i, s in enumerate(steps, 1):
                    claim, conf, c = _step_view(s)
                    st.markdown(f"**{i}.** {claim}")
                    conf_bar(conf)
                    if c:
                        html('<span class="ff-cite">' + ", ".join(c) + "</span>")
