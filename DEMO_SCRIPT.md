# DEMO_SCRIPT — FinFlow Reasoning Engine (2–3 minutes)

Goal: show the **learning loop** (V1 → expert → learn → V2) and the **dashboard**,
honestly framed: a working mechanism with directional evidence, not a proven claim.

Prep (before recording):
```bash
cp .env.example .env        # GROQ_API_KEY set
docker compose build
docker compose up app        # dashboard at http://localhost:8501 (seeded)
```
Have a terminal + the browser open.

---

## 0:00–0:25 · Problem (talking points)
> "Teams scatter knowledge across Slack, tickets, wikis, and commits. AI tools
> retrieve facts but miss the *causal reasoning* a senior engineer applies. FinFlow
> tries to **learn how experts reason** — and prove it generalizes, not memorizes."

Screen: README top / one-pager.

## 0:25–0:55 · The data & a question
> "Synthetic fintech org: Payment, Ledger, Risk Engine, Notification. 54 interlinked
> evidence items. Take P2 — *'What caused the June 3 duplicate-charge incident?'* The
> real cause needs connecting a Risk-timeout retry storm with a commit that disabled
> an idempotency guard — no single document says it."

Screen: dashboard **Question Feed**; click P2.

## 0:55–1:30 · V1 vs V2 + the learning loop
Run (or show persisted) a learning cycle:
```bash
PYTHONPATH=. python scripts/run_pipeline.py --question P2
```
> "V1 retrieves the obvious evidence and stops at the proximate cause. Gap analysis
> against the expert shows it **missed the commit**. The system distills a
> **generalizable heuristic** — 'for incidents, check recent commits for removed
> safeguards' — plus generic retrieval signals. Crucially, the leakage gate stores
> **no verbatim expert text**."

Screen: dashboard sections **Gap Analysis** → **Learning Event** (point at "generalized
hints only / leakage PASS").

## 1:30–2:10 · Generalization (the real test)
> "Now the held-out twin H2 — June 9 *duplicate-notification* incident — which never
> got feedback. Using the heuristic learned from P2, V2 **newly retrieves a4** (the
> refactor that dropped dedup) that V1 missed, **reasons about it**, and names the
> correct root cause."

Screen: **Retrieved Evidence** (newly-retrieved flag on the commit) → **V2 Answer**.
> "Directional run on the 8B model: held-out blended **+0.325**, ablation **+0.125**,
> rubric coverage **0.50 → 0.75**."

## 2:10–2:40 · Metrics & honesty
Screen: **Metrics & Gates** + **Learning Trend** chart.
> "Four gates: held-out generalization, ablation attribution, leakage-free learning,
> same-question improvement. **Be clear:** mechanisms are verified by 83 tests, the
> 8B transfer is positive and directional, but the **canonical 70B evaluation hasn't
> completed** due to API quota — so the central claim is **not yet canonically
> validated**. The harness is ready; it's one quota-unblocked run away."

## 2:40–3:00 · Close
> "End-to-end: investigate, learn leakage-free, generalize, measure — fully dockerized,
> read-only dashboard, 83 tests. Next: the canonical run, more families, and tighter
> retrieval signals."

---

### Command cheat-sheet
```bash
docker compose --profile tests run --rm tests     # 83 tests
docker compose up app                              # dashboard
PYTHONPATH=. python scripts/run_pipeline.py --question P2
docker compose --profile eval run --rm eval        # full eval (key + quota)
```

### Honesty guardrails (do not say)
- ❌ "We proved the system learns to reason." → ✅ "We verified the mechanism and have directional evidence; canonical proof is pending."
- ❌ Present 8B numbers as the 70B result. → ✅ Always label the 8B run as directional/non-canonical.
