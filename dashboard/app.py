"""FinFlow — read-only dashboard (single page).

Visualizes persisted artifacts only. Run with:
    PYTHONPATH=. streamlit run dashboard/app.py

It NEVER runs a pipeline/judge/learning step — it only reads the SQLite repository
populated by scripts/run_pipeline.py and scripts/run_evaluation.py.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import data


def _bool(v: bool) -> str:
    return "✅" if v else "—"


def render() -> None:
    st.set_page_config(page_title="FinFlow Reasoning Engine", layout="wide")
    st.title("FinFlow — Expert-Learning Organizational Reasoning Engine")
    st.caption("Read-only view of persisted runs, learning events, and evaluation artifacts.")

    repo = data.open_repo()
    feed = data.question_feed(repo)
    if not feed:
        st.warning("No data yet. Seed and run the pipeline:\n\n"
                   "`PYTHONPATH=. python scripts/seed_db.py`\n\n"
                   "`PYTHONPATH=. python scripts/run_pipeline.py --question P2`\n\n"
                   "`PYTHONPATH=. python scripts/run_evaluation.py`")
        return

    # 1) Question Feed -------------------------------------------------------
    st.header("1 · Question Feed")
    st.dataframe(pd.DataFrame(feed), use_container_width=True, hide_index=True)

    qid = st.selectbox("Inspect a question", [r["id"] for r in feed])
    run = data.latest_run(repo, qid)
    if run is None:
        st.info("No run recorded for this question yet.")
    else:
        detail = data.run_detail(repo, run)
        st.caption(f"run_id `{detail['run_id']}` · phase `{detail['phase']}`")

        # 2) Retrieved Evidence (V1 vs V2) + inspectable trace ---------------
        st.header("2 · Retrieved Evidence — V1 vs V2")
        ec = pd.DataFrame(detail["evidence_comparison"])
        if not ec.empty:
            for col in ("retrieved_v1", "retrieved_v2", "newly_retrieved", "cited_v1", "cited_v2", "newly_cited"):
                ec[col] = ec[col].map(_bool)
            st.dataframe(ec, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        c1.metric("newly retrieved (V2)", len(detail["newly_retrieved_ids"]))
        c2.metric("newly cited (V2)", len(detail["newly_cited_ids"]))
        util = detail["evidence_utilization"]
        st.metric("evidence utilization (V2)", f"{util:.2f}" if util is not None else "n/a")
        with st.expander("Retrieval trace — V1"):
            _retrieval(detail["retrieval_v1"])
        with st.expander("Retrieval trace — V2 (learned expansion/routing + diagnostics)"):
            _retrieval(detail["retrieval_v2"])

        # 3) V1 Answer -------------------------------------------------------
        st.header("3 · V1 Answer (baseline)")
        st.write(detail["v1"] or "_none_")
        _steps("V1 reasoning", detail["v1_steps"])

        # 4) Expert Answer ---------------------------------------------------
        st.header("4 · Expert Answer (ground truth)")
        st.write(detail["expert"] or "_none_")

        # 5) Gap Analysis ----------------------------------------------------
        st.header("5 · Gap Analysis")
        if detail["gap"]:
            g = detail["gap"]
            st.write(f"**Severity:** {g['severity']}")
            st.write(f"**Missed evidence:** {g['missed_evidence_ids']}")
            st.write(f"**Extra evidence:** {g['extra_evidence_ids']}")
            st.write(f"**Missed root causes:** {g['missed_root_causes']}")
            st.write(f"**Reasoning gaps:** {g['reasoning_gaps']}")
        else:
            st.write("_no gap analysis_")

        # 6) Learning Event --------------------------------------------------
        st.header("6 · Learning Event")
        if detail["learning_event"]:
            _learning_event(detail["learning_event"])
        else:
            st.write("_no learning event for this run_")

        # 7) V2 Answer -------------------------------------------------------
        st.header("7 · V2 Answer (memory-augmented)")
        st.write(detail["v2"] or "_none_")
        _steps("V2 reasoning", detail["v2_steps"])
        if detail["judge_results"]:
            with st.expander("Judge results for this run (logged)"):
                st.dataframe(pd.DataFrame([
                    {"metric": j["metric"], "score": j["score"], "prompt_version": j["judge_prompt_version"],
                     "model": j["judge_model"], "reasoning": j["reasoning"][:160]}
                    for j in detail["judge_results"]
                ]), use_container_width=True, hide_index=True)

    # 8) Metrics + 9) Trend + Transfer (evaluation artifacts) ----------------
    st.header("8 · Metrics & Gates")
    ev = data.evaluation_summary(repo)
    if not ev:
        st.info("No evaluation run yet. Run `PYTHONPATH=. python scripts/run_evaluation.py`.")
    else:
        st.caption(f"eval `{ev['eval_id']}` · model `{ev['model']}` · judges {ev['judge_prompt_versions']}")
        cc = "✅ PASS" if ev["central_claim_passed"] else "❌ FAIL"
        vv = "✅ PASS" if ev["verdict"] else "❌ FAIL"
        a, b = st.columns(2)
        a.metric("Central claim (held-out + leakage-free)", cc)
        b.metric("Overall verdict (all gates)", vv)

        st.subheader("Gates")
        st.dataframe(pd.DataFrame([
            {"gate": g["name"], "central": _bool(g["central"]), "passed": _bool(g["passed"]),
             "value": g["value"], "threshold": g["threshold"], "detail": g["detail"]}
            for g in ev["gates"]
        ]), use_container_width=True, hide_index=True)

        st.subheader("Per-question scorecard")
        st.dataframe(pd.DataFrame(ev["scores"]), use_container_width=True, hide_index=True)

        st.subheader("Transfer metrics (held-out twins)")
        from finflow.models import EvaluationRun
        tm = data.transfer_metrics(EvaluationRun.model_validate({
            "eval_id": ev["eval_id"],
            "scores": ev["scores"], "gates": ev["gates"],
        }))
        st.dataframe(pd.DataFrame(tm), use_container_width=True, hide_index=True)

        st.header("9 · Learning Trend — V1 vs V2 blended")
        chart_rows = [
            {"question": s["question_id"], "V1": s["blended_v1"], "V2": s["blended_v2"]}
            for s in ev["scores"]
        ]
        cdf = pd.DataFrame(chart_rows).set_index("question")
        st.bar_chart(cdf)


def _retrieval(trace: dict | None) -> None:
    if not trace:
        st.write("_none_")
        return
    st.caption(f"query: {trace['query']}")
    st.dataframe(pd.DataFrame(trace["items"]), use_container_width=True, hide_index=True)
    notes = trace["diagnostics"].get("notes")
    if notes:
        st.caption("diagnostics: " + " | ".join(notes))


def _steps(label: str, steps: list[dict]) -> None:
    if not steps:
        return
    with st.expander(label):
        st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)


def _learning_event(le: dict) -> None:
    lk = le["leakage"]
    st.write(f"**Leakage gate:** {'✅ PASS' if lk['passed'] else '❌ FAIL'} · "
             f"max n-gram overlap {lk['max_ngram_overlap']} · patterns dropped {lk['redactions']}")
    st.caption("Patterns are generalized hints only — no verbatim expert answers are stored.")
    for ptype, pats in le["patterns_by_type"].items():
        st.write(f"**{ptype}**")
        st.dataframe(pd.DataFrame(pats), use_container_width=True, hide_index=True)


def main() -> None:
    render()


if __name__ == "__main__":
    main()
