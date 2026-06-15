"""FinFlow — read-only dashboard (single page, tabbed).

Visualizes persisted artifacts only. Run with:
    PYTHONPATH=. streamlit run dashboard/app.py

It NEVER runs a pipeline/judge/learning step — it only reads the SQLite repository
populated by scripts/run_pipeline.py and scripts/run_evaluation.py. Styling lives in
dashboard/ui.py; data access in dashboard/data.py.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import data, ui


def _yn(v: bool) -> str:
    return "Yes" if v else "—"


def _sidebar(feed) -> None:
    st.sidebar.markdown("## FinFlow")
    st.sidebar.caption("Expert-Learning Organizational Reasoning Engine")
    st.sidebar.markdown("**Read-only** view of persisted artifacts.")
    st.sidebar.metric("Questions", len(feed))
    st.sidebar.markdown("**Families**")
    ui.html(*[ui.family_badge(f) for f in ui.FAMILY_COLORS])


def render() -> None:
    st.set_page_config(page_title="FinFlow Reasoning Engine", layout="wide")
    ui.inject_css()
    st.title("FinFlow — Reasoning Engine")
    st.caption("Question → V1 → Expert → Gap → Learning → V2 → Metrics · read-only over SQLite")

    repo = data.open_repo()
    feed = data.question_feed(repo)
    if not feed:
        st.warning("No data yet. Populate it first:")
        st.code("PYTHONPATH=. python scripts/seed_db.py\n"
                "PYTHONPATH=. python scripts/run_pipeline.py --question P2\n"
                "PYTHONPATH=. python scripts/run_evaluation.py", language="bash")
        return
    _sidebar(feed)

    # --- Question feed ------------------------------------------------------
    st.subheader("Question feed")
    fdf = pd.DataFrame([{
        "id": r["id"], "family": r["family"], "held-out": _yn(r["held_out"]),
        "has V2": _yn(r["has_v2"]), "runs": r["n_runs"], "question": r["text"],
    } for r in feed])
    st.dataframe(fdf, use_container_width=True, hide_index=True,
                 column_config={"question": st.column_config.TextColumn(width="large")})

    qid = st.selectbox("Inspect a question", [r["id"] for r in feed])
    q_meta = next(r for r in feed if r["id"] == qid)
    run = data.latest_run(repo, qid)
    ui.demo_flow()
    ui.html(ui.family_badge(q_meta["family"]),
            ui.badge("held-out", "#7c3aed") if q_meta["held_out"] else "",
            f'&nbsp; <b>{q_meta["text"]}</b>')

    tab_inv, tab_gap, tab_eval = st.tabs(["Investigation", "Gap & Learning", "Evaluation"])

    # --- Investigation -----------------------------------------------------
    with tab_inv:
        if run is None:
            st.info("No run recorded for this question yet.")
        else:
            d = data.run_detail(repo, run)
            st.caption(f"run `{d['run_id']}` · phase `{d['phase']}`")
            c1, c2 = st.columns(2)
            with c1:
                ui.answer_card("V1 — baseline", d["v1"], cited=run.v1.cited_source_ids if run.v1 else None,
                               accent=ui.ACCENT_V1, steps=d["v1_steps"])
            with c2:
                ui.answer_card("V2 — after learning", d["v2"], cited=run.v2.cited_source_ids if run.v2 else None,
                               accent=ui.ACCENT_V2, steps=d["v2_steps"])

            k1, k2, k3 = st.columns(3)
            k1.metric("newly retrieved (V2)", len(d["newly_retrieved_ids"]))
            k2.metric("newly cited (V2)", len(d["newly_cited_ids"]))
            util = d["evidence_utilization"]
            k3.metric("evidence utilization", f"{util:.2f}" if util is not None else "n/a")

            with st.container(border=True):
                st.markdown('<div class="ff-title">Evidence — V1 vs V2</div>', unsafe_allow_html=True)
                ec = pd.DataFrame(d["evidence_comparison"])
                if not ec.empty:
                    for col in ("retrieved_v1", "retrieved_v2", "newly_retrieved", "cited_v1", "cited_v2", "newly_cited"):
                        ec[col] = ec[col].map(_yn)
                    st.dataframe(ec, use_container_width=True, hide_index=True)
                with st.expander("Retrieval trace — V1"):
                    _trace(d["retrieval_v1"])
                with st.expander("Retrieval trace — V2 (learned expansion / routing)"):
                    _trace(d["retrieval_v2"])

            ui.answer_card("Expert answer (ground truth)", d["expert"], accent="#0f766e")

    # --- Gap & Learning ----------------------------------------------------
    with tab_gap:
        if run is None or not data.run_detail(repo, run)["gap"]:
            st.info("No gap analysis / learning event for this run.")
        else:
            d = data.run_detail(repo, run)
            g = d["gap"]
            with st.container(border=True):
                ui.html('<span class="ff-title">Gap analysis</span> &nbsp;', ui.severity_badge(g["severity"]))
                st.markdown(f"**Missed evidence:** {g['missed_evidence_ids'] or '—'}")
                st.markdown(f"**Extra evidence:** {g['extra_evidence_ids'] or '—'}")
                st.markdown(f"**Missed root causes:** {g['missed_root_causes'] or '—'}")
                st.markdown(f"**Reasoning gaps:** {g['reasoning_gaps'] or '—'}")
            if d["learning_event"]:
                _learning_event(d["learning_event"])

    # --- Evaluation --------------------------------------------------------
    with tab_eval:
        ev = data.evaluation_summary(repo)
        if not ev:
            st.info("No evaluation run yet. Run `scripts/run_evaluation.py`.")
        else:
            st.caption(f"eval `{ev['eval_id']}` · model `{ev['model']}` · judges {ev['judge_prompt_versions']}")
            a, b = st.columns(2)
            a.metric("Central claim (held-out + leakage-free)", "PASS" if ev["central_claim_passed"] else "FAIL")
            b.metric("Overall verdict (all gates)", "PASS" if ev["verdict"] else "FAIL")
            st.markdown("**Gates**")
            st.dataframe(pd.DataFrame([
                {"gate": g["name"], "central": _yn(g["central"]), "passed": _yn(g["passed"]),
                 "value": g["value"], "threshold": g["threshold"], "detail": g["detail"]}
                for g in ev["gates"]
            ]), use_container_width=True, hide_index=True)
            st.markdown("**Per-question scorecard**")
            st.dataframe(pd.DataFrame(ev["scores"]), use_container_width=True, hide_index=True)

            from finflow.models import EvaluationRun
            tm = data.transfer_metrics(EvaluationRun.model_validate(
                {"eval_id": ev["eval_id"], "scores": ev["scores"], "gates": ev["gates"]}))
            if tm:
                st.markdown("**Transfer metrics (held-out twins)**")
                st.dataframe(pd.DataFrame(tm), use_container_width=True, hide_index=True)

            st.markdown("**Learning trend — V1 vs V2 blended**")
            cdf = pd.DataFrame([{"question": s["question_id"], "V1": s["blended_v1"], "V2": s["blended_v2"]}
                                for s in ev["scores"]]).set_index("question")
            st.bar_chart(cdf)


def _trace(trace: dict | None) -> None:
    if not trace:
        st.write("_none_")
        return
    st.caption(f"query: {trace['query']}")
    st.dataframe(pd.DataFrame(trace["items"]), use_container_width=True, hide_index=True)
    notes = trace["diagnostics"].get("notes")
    if notes:
        st.caption("diagnostics: " + " | ".join(notes))


def _learning_event(le: dict) -> None:
    with st.container(border=True):
        lk = le["leakage"]
        ui.html('<span class="ff-title">Learning event</span> &nbsp;', ui.passfail(lk["passed"]),
                f'<span class="ff-muted">max n-gram overlap {lk["max_ngram_overlap"]} · '
                f'patterns dropped {lk["redactions"]}</span>')
        st.caption("Generalized hints only — no verbatim expert answers stored.")
        for ptype, pats in le["patterns_by_type"].items():
            st.markdown(f"**{ptype}**")
            st.dataframe(pd.DataFrame(pats), use_container_width=True, hide_index=True)


def main() -> None:
    render()


if __name__ == "__main__":
    main()
