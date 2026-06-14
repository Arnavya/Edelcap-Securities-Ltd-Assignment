"""FinFlow — interactive Live Learning Loop (human-in-the-loop).

Frontend that RUNS the pipeline:
  1) pick/type a question  ->  2) Run V1  ->  3) type the expert answer
  ->  4) Learn & generate V2  ->  compare V1 vs V2 + metrics.

Run THIS file (not app.py, which is the read-only dashboard):
    PYTHONPATH=. streamlit run dashboard/live_app.py

Wiring: every input is a keyed widget; buttons use on_click callbacks that read
st.session_state and write results back, so values are reliably captured across
Streamlit reruns. Needs a working GROQ_API_KEY. Default model llama-3.1-8b-instant.
Core reasoning logic is untouched — this only wires the UI to the orchestrator.
"""

from __future__ import annotations

import streamlit as st

from finflow.config import load_settings
from finflow.evaluation.evidence_overlap import compute_overlap
from finflow.evaluation.improvement import blended
from finflow.evaluation.judge import Judge
from finflow.llm import GroqProvider, MockProvider
from finflow.models import Question, QuestionFamily
from finflow.orchestrator import Orchestrator
from finflow.persistence import SQLiteRepository
from finflow.retrieval import BM25Retriever, KnowledgeStore, load_questions

MODELS = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]


# --- backend wiring (cached where safe) -------------------------------------

@st.cache_resource
def _knowledge():
    store = KnowledgeStore.from_dir()
    return store, BM25Retriever(store.all())


@st.cache_data
def _questions() -> dict:
    return {q.id: q for q in load_questions()}


def _provider(model: str):
    s = load_settings()
    return MockProvider(model=model) if s.provider == "mock" else GroqProvider(api_key=s.groq_api_key, model=model)


def _orchestrator(model: str) -> Orchestrator:
    s = load_settings()
    store, retriever = _knowledge()
    return Orchestrator(_provider(model), store, retriever, SQLiteRepository(s.db_path), retrieval_k=s.retrieval_k)


def _selected_question() -> Question | None:
    """Build the active Question from the keyed inputs."""
    if st.session_state.get("q_source", "Existing").startswith("Existing"):
        qid = st.session_state.get("q_select")
        return _questions().get(qid)
    text = (st.session_state.get("new_q_text") or "").strip()
    if not text:
        return None
    fam = st.session_state.get("new_q_family", QuestionFamily.PROD_INCIDENT.value)
    st.session_state["uctr"] = st.session_state.get("uctr", 0) + 1
    return Question(id=f"U{st.session_state['uctr']}", text=text,
                    family=QuestionFamily(fam), family_id=f"user-{fam}", is_held_out=False)


# --- callbacks (run BEFORE rerender; read keyed widget state reliably) ------

def _cb_run_v1() -> None:
    st.session_state["error"] = None
    st.session_state["run"] = None
    st.session_state["metrics"] = None
    question = _selected_question()
    if question is None:
        st.session_state["error"] = "Please choose or type a question first."
        return
    model = st.session_state.get("model_select", MODELS[0])
    try:
        v1, snap1 = _orchestrator(model).run_v1_only(question)
        st.session_state.update(q=question, v1=v1, snap1=snap1, model=model)
    except Exception as exc:  # surface key/quota errors in the UI
        st.session_state["error"] = f"V1 failed: {type(exc).__name__}: {exc}"
        st.session_state["v1"] = None


def _cb_run_v2() -> None:
    st.session_state["error"] = None
    if st.session_state.get("v1") is None:
        st.session_state["error"] = "Run V1 first."
        return
    expert = (st.session_state.get("expert_text") or "").strip()
    if not expert:
        st.session_state["error"] = "Please type an expert answer."
        return
    model = st.session_state.get("model", MODELS[0])
    q = st.session_state["q"]
    try:
        orch = _orchestrator(model)
        run = orch.learn_and_v2(q, st.session_state["v1"], st.session_state["snap1"], expert)
        st.session_state["run"] = run
        st.session_state["metrics"] = _score(model, q, run)  # compute once, not on every rerun
    except Exception as exc:
        st.session_state["error"] = f"Learn/V2 failed: {type(exc).__name__}: {exc}"


def _score(model: str, q: Question, run) -> dict | None:
    try:
        judge = Judge(_provider(model))
        h = run.human
        m = {
            "sim1": judge.similarity(q, run.v1, h).score,
            "sim2": judge.similarity(q, run.v2, h).score,
            "has_gold": bool(h.key_source_ids),
            "ev1": compute_overlap(run.v1.cited_source_ids, h.key_source_ids).recall,
            "ev2": compute_overlap(run.v2.cited_source_ids, h.key_source_ids).recall,
        }
        if h.root_cause_rubric:
            m["rc1"] = judge.root_cause(q, run.v1, h).score
            m["rc2"] = judge.root_cause(q, run.v2, h).score
        new = set(run.newly_retrieved_ids)
        used = set(run.v2.cited_source_ids)
        for s in run.v2.reasoning_trace.steps:
            used.update(s.cited_source_ids)
        m["util"] = (len(new & used) / len(new)) if new else 0.0
        return m
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


# --- rendering ---------------------------------------------------------------

def _show_answer(ans) -> None:
    st.write(ans.answer_text or "_(empty)_")
    if ans.cited_source_ids:
        st.caption("cited: " + ", ".join(ans.cited_source_ids))
    with st.expander("reasoning steps"):
        for i, s in enumerate(ans.reasoning_trace.steps, 1):
            st.write(f"{i}. ({s.confidence:.2f}) {s.claim}  ·  {s.cited_source_ids}")


def render() -> None:
    st.set_page_config(page_title="FinFlow — Live Learning Loop", layout="wide")
    st.title("FinFlow — Live Learning Loop (human-in-the-loop)")
    st.caption("Ask → V1 → your expert answer → the system learns → V2. V2 is *attempted* to be better, not guaranteed.")

    st.sidebar.selectbox("Model", MODELS, index=0, key="model_select")
    st.sidebar.info("Default `llama-3.1-8b-instant` works now. `llama-3.3-70b-versatile` is higher quality but often daily-quota-blocked.")

    # 1 — question (keyed inputs)
    st.header("1 · Question")
    st.radio("Source", ["Existing (P1–H3)", "New (type your own)"], horizontal=True, key="q_source")
    if st.session_state.get("q_source", "Existing").startswith("Existing"):
        qs = _questions()
        st.selectbox("Question", list(qs), format_func=lambda i: f"{i} — {qs[i].text}", key="q_select")
    else:
        st.text_input("Your question", key="new_q_text", placeholder="Why did the … incident happen?")
        st.selectbox("Category (helps match learned patterns)", [f.value for f in QuestionFamily], key="new_q_family")

    st.button("▶ Run V1 investigation", type="primary", on_click=_cb_run_v1)

    if st.session_state.get("error"):
        st.error(st.session_state["error"])

    if st.session_state.get("v1") is None:
        st.info("Enter a question and click **Run V1** to begin.")
        return

    q = st.session_state["q"]
    st.header("2 · V1 answer (baseline)")
    st.caption(f"question: {q.text}")
    _show_answer(st.session_state["v1"])
    st.caption(f"retrieved: {st.session_state['snap1'].source_ids}")

    # 3 — expert answer (keyed)
    st.header("3 · Your expert answer (ground truth)")
    stored = _orchestrator(st.session_state.get("model", MODELS[0])).repo.get_human_answer(q.id)
    if stored:
        with st.expander("curated expert answer (reference, optional)"):
            st.write(stored.answer_text)
    st.text_area("Type the correct expert answer", height=140, key="expert_text")
    st.button("✦ Learn & generate V2", type="primary", on_click=_cb_run_v2)

    run = st.session_state.get("run")
    if not run:
        return

    # 4 — comparison + metrics (from session, computed once in the callback)
    st.header("4 · V1 → V2 comparison")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("V1"); _show_answer(run.v1)
    with c2:
        st.subheader("V2 (after learning)"); _show_answer(run.v2)

    st.subheader("What the learning changed")
    a, b, c = st.columns(3)
    a.metric("newly retrieved (V2)", len(run.newly_retrieved_ids))
    b.metric("newly cited (V2)", len(run.newly_cited_ids))
    m = st.session_state.get("metrics") or {}
    if "util" in m:
        c.metric("evidence utilization", f"{m['util']:.2f}")
    if run.newly_retrieved_ids:
        st.caption("newly retrieved: " + ", ".join(run.newly_retrieved_ids))

    if m and "error" not in m:
        cols = st.columns(3)
        cols[0].metric("similarity V1→V2", f"{m['sim2']:.2f}", f"{m['sim2'] - m['sim1']:+.2f}")
        if m.get("has_gold"):
            cols[1].metric("evidence recall V1→V2", f"{m['ev2']:.2f}", f"{m['ev2'] - m['ev1']:+.2f}")
        if "rc2" in m:
            cols[2].metric("rubric coverage V1→V2", f"{m['rc2']:.2f}", f"{m['rc2'] - m['rc1']:+.2f}")
            st.metric("blended V1→V2", f"{blended(m['sim2'], m['rc2']):.2f}",
                      f"{blended(m['sim2'], m['rc2']) - blended(m['sim1'], m['rc1']):+.2f}")
        if m["sim2"] < m["sim1"]:
            st.warning("V2 did not score higher than V1 here — shown honestly. Learning is generalizable and stochastic; it doesn't guarantee a win every time.")
    elif m.get("error"):
        st.caption(f"(judge scoring skipped: {m['error']})")

    with st.expander("Gap analysis"):
        st.write(run.gap.model_dump() if run.gap else "_none_")
    with st.expander("Learning event (generalized hints only — leakage-free)"):
        if run.learning_event:
            lk = run.learning_event.sanitization
            st.write(f"leakage gate: {'PASS' if lk.leakage_check_passed else 'FAIL'} · max n-gram overlap {lk.max_ngram_overlap} · patterns dropped {lk.redactions}")
            for p in run.learning_event.patterns:
                sig = (" · signals=" + str(p.retrieval_signals)) if p.retrieval_signals else ""
                st.write(f"- **{p.pattern_type.value}**: {p.hint_text}{sig}")
    st.success(f"Persisted run `{run.run_id}` — also visible in the read-only dashboard.")


def main() -> None:
    render()


if __name__ == "__main__":
    main()
