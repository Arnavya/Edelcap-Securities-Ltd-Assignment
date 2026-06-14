# DEMO_SCRIPT — FinFlow Reasoning Engine (≤3 minutes)

> **Current state (origin/main):** `judge_similarity_v3` (calibrated similarity judge), an **incident-only soft service-scope** on V2 retrieval, and the **interactive HITL dashboard** (`dashboard/live_app.py`) are shipped; the suite is **90 tests**. See `README.md` for current truth.
>
> **Add your recorded video link here before submitting:** _<paste link>_

Goal: show the **learning loop** (V1 → expert → learn → V2) live in the interactive
dashboard, plus the trends/gates, honestly framed: a working mechanism with directional
evidence on the 8B model, canonical 70B run pending. ~420 spoken words ≈ ~2:50 at ~150 wpm.

---

## Pre-record setup (off-camera, once)
```bash
cp .env.example .env                 # add GROQ_API_KEY
PYTHONPATH=. python scripts/seed_db.py
PYTHONPATH=. python scripts/run_pipeline.py --question P2   # safety-net run for read-only view
PYTHONPATH=. streamlit run dashboard/live_app.py                      # interactive  :8501
PYTHONPATH=. streamlit run dashboard/app.py --server.port 8502        # read-only    :8502
```
Copy the **expert answer** to clipboard (you'll paste it on camera):
> "A retry storm from Risk Engine scoring timeouts hit a payment path whose idempotency
> guard had been disabled; fixed by restoring the guard."

---

## The script (timed)

### 0:00–0:20 · Problem
**SHOW:** README top / one-pager slide.
**SAY:**
> "Teams keep critical knowledge scattered across Slack, tickets, wikis, and code. AI
> assistants retrieve facts but miss the *causal reasoning* a senior engineer applies.
> FinFlow is an engine that **learns how experts reason** — and proves it generalizes."

### 0:20–0:35 · What it does
**SHOW:** interactive dashboard header + the demo-flow stepper.
**SAY:**
> "It drafts a first answer, takes an expert's correction, distills a *generalizable,
> leakage-free* lesson, and re-answers — V1 to V2. Here's the live loop."

### 0:35–1:20 · V1
**SHOW:** in `live_app`, select **P2** → click **Run V1**.
**SAY (while it runs):**
> "I'm asking: *what caused the June 3 duplicate-charge incident?* The real cause spans
> services — a Risk-Engine retry storm hitting a payment path whose idempotency guard was
> disabled. No single document says it."
**SAY (when V1 appears):**
> "V1 gets the gist but stops at the proximate cause — and notice it shows its **reasoning
> path with confidence** and **cited evidence**: explainability first."

### 1:20–1:40 · Expert answer
**SHOW:** paste the expert answer into the expert box → click **Learn & generate V2**.
**SAY:**
> "Now a human expert gives the ground truth. The system runs gap analysis, distills a
> learning event, and re-investigates."

### 1:40–2:20 · V2 + learning
**SHOW:** V1↔V2 comparison cards, gap analysis, learning event (leakage PASS), metric deltas.
**SAY:**
> "V2 now names the **disabled idempotency guard** and the retry storm — it pulled in the
> commit V1 missed. The **gap analysis** shows what was missing; the **learning event**
> stores only *generalized hints* — the **leakage gate is PASS**, so no verbatim answer is
> memorized. And the metrics: **similarity up**, with newly-retrieved evidence actually used."

### 2:20–2:40 · Rigor / trends
**SHOW:** read-only dashboard (:8502) → **Metrics & Gates** + **Learning Trend**.
**SAY:**
> "Across questions we track V1-vs-V2 trends and four gates — including a **held-out twin**
> the system never got feedback on, to prove it learned a *method*, not an answer."

### 2:40–2:55 · Honest close
**SAY:**
> "Straight about results: the mechanisms are verified by **90 automated tests**, and on a
> held-out incident the learning improves reasoning **directionally on the 8B model**. The
> canonical 70B run is pending on API quota. Next: that run, and tighter retrieval scoping.
> That's FinFlow — learning to reason like an expert, transparently."

---

## Fallback (if a live Groq call rate-limits mid-take)
Switch to the **read-only dashboard** (`app.py`, :8502), which shows the pre-seeded P2 run
(V1, V2, gap, learning event, metrics) — narrate the same beats over persisted artifacts.
This is why a run was pre-seeded in setup.

## Tips
- Default model is `llama-3.1-8b-instant` (fast, separate quota) — don't switch to 70B on camera.
- If V2 doesn't beat V1 on a take, that's fine — the UI flags it honestly; re-run or use the seeded run.
- Trim the 2:20–2:40 trends beat first if you run over time.
- Read it aloud once with a timer before recording; dry-run the click path (P2 → Run V1 → paste → Learn & V2).

---

### Command cheat-sheet
```bash
docker compose --profile tests run --rm tests      # 90 tests, offline
PYTHONPATH=. streamlit run dashboard/live_app.py    # interactive HITL demo
PYTHONPATH=. streamlit run dashboard/app.py         # read-only trends
docker compose --profile eval run --rm eval         # full eval (key + quota)
```

### Honesty guardrails (do not say)
- ❌ "We proved the system learns to reason." → ✅ "We verified the mechanism and have directional evidence; canonical 70B proof is pending."
- ❌ Present 8B numbers as the 70B result. → ✅ Always label the 8B run as directional / non-canonical.
