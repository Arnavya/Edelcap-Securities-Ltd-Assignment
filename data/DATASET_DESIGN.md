# FinFlow Dataset Design (review checkpoint — P2)

> Design only. No JSON corpus authored yet. **54 evidence items** = 47 answer-chain
> items (12 slack / 12 tickets / 8 wiki / 15 commits) + **7 distractors** (2 slack /
> 2 tickets / 3 commits), deliberately interlinked so answers require cross-source
> traversal. Final corpus distribution: 14 slack / 14 tickets / 8 wiki / 18 commits.
> Stable IDs are final.

## Cast & ownership
| Service | Team | Lead | Notes |
|---|---|---|---|
| Payment | Pay | Maya Chen | Charges, retries, settlement orchestration |
| Ledger | Books | Raj Patel | Records transactions; async settlement |
| Risk Engine | Sentinel | Sofia Alvarez | Inline fraud scoring; **owned by Pay until Feb 2026** |
| Notification | Comms | Tom Nguyen | Event-driven receipts/alerts |

## Timeline
Jan — async settlement ships (ADR-001/a6) · Feb — Risk Engine ownership Pay→Sentinel (OWN-100) · Apr — Risk model v4 deploy (a13) · May — v2.5 settlement release slips 2 wks (LED-412) · **Jun 3** — duplicate-charge incident (a1 + RISK-220/a3) · **Jun 9** — duplicate-notification incident (ADR-003 + a4) · Jun — Q3 planning: fraud-scoring blocked on LED-430, reconciliation blocked on unassigned boundary (LED-450).

---

## 1–2. Evidence inventory (47 items)

### Wiki (8)
| ID | Title | Summary | Entities | Relationships |
|---|---|---|---|---|
| `wiki:ownership-matrix` | Service Ownership Matrix | Maps each service→team→lead. Risk Engine current owner = Team Sentinel (since Feb 2026). The Payment↔Ledger reconciliation boundary is listed **TBD/shared** (no owner). | All services/teams | Updated by OWN-100; cited by recon-boundary, standup-ledger; basis for P4, P6 |
| `wiki:service-architecture` | Service Architecture | Request flow Payment→Risk→Ledger→Notification; Risk reads Ledger history; Notification is event-driven. | All | Context for all incidents; referenced by design threads |
| `wiki:adr-001-async-settlement` | ADR-001 Async Settlement | Chose async settlement over synchronous for throughput; tradeoff = eventual-consistency window, to be mitigated by idempotency keys. | Ledger | Implemented by a6; debated in design-async-settlement; basis for P5; linked to ADR-004 |
| `wiki:adr-002-inline-risk` | ADR-002 Inline Risk Scoring | Risk scoring runs inline in the payment path (200ms budget) to block fraud before charge; tradeoff = payment latency exposed to Risk timeouts. | Payment, Risk | Implemented by a7; relevant to Jun3 (RISK-220 timeouts) |
| `wiki:adr-003-notif-eventbus` | ADR-003 Notification Event Bus | Notifications delivered via an **at-least-once** event bus; consumers MUST deduplicate. | Notification | Implemented by a8; root context for Jun9/H2; cited by NOT-310, notif-dedup-debug |
| `wiki:adr-004-ledger-idempotency` | ADR-004 Ledger Idempotency Keys | Adds idempotency keys to settlement to prevent double-posting; mitigates ADR-001's window. | Ledger, Payment | Implemented by a2; LED-412 is the bug when this was incomplete; basis for P5 mitigation |
| `wiki:q3-roadmap` | Q3 Engineering Roadmap | Lists milestones with explicit **depends-on** links: fraud-scoring depends-on LED-430; settlement-reconciliation depends-on reconciliation-boundary ownership. | All | Drives P3, H3; references RISK-240, LED-450, LED-430 |
| `wiki:incident-runbook` | Incident Response Runbook | RCA process: check recent deploys/commits, correlate monitoring, open an RCA ticket. Encodes (but does not enforce) the "check recent commits" practice. | All | Supporting context for P2, H2 incidents |

### Tickets (12)
| ID | Title | Summary | Entities | Relationships |
|---|---|---|---|---|
| `ticket:LED-412` | Settlement double-posting under retry | Settlement can double-post on retry because idempotency keys aren't fully enforced; found in staging during v2.5 testing. | Ledger, Payment | **Blocks** PAY-501; fixed by a9 (+a2); references ADR-004 |
| `ticket:PAY-501` | Payment v2.5 settlement release | Release tracker for May v2.5; target slipped ~2 weeks. | Payment, Ledger | **Blocked-by** LED-412; prep commit a10; discussed in rel-may-settlement (P1) |
| `ticket:PAY-530` | RCA: Jun 3 duplicate-charge | Post-incident RCA: duplicate charges from a retry storm hitting a path without the idempotency guard. | Payment, Risk | Caused by a1 + RISK-220/a3; fix child PAY-540; incident inc-jun3-charge (P2) |
| `ticket:RISK-220` | Risk timeouts; add retry | Risk scoring times out under load; added a client retry in the payment path. | Risk, Payment | Implemented by a3; references ADR-002; debugged in risk-timeout-debug; feeds Jun3 (P2) |
| `ticket:NOT-310` | RCA: Jun 9 duplicate-notification | Customers got duplicate receipts; consumer stopped deduping at-least-once events. | Notification | Caused by a4; references ADR-003; fix child NOT-320; incident inc-jun9-notif (H2) |
| `ticket:NOT-300` | Notification batching release (June) | Batching feature; release behind schedule after the team was pulled onto the Jun9 dedup fix. | Notification | Implemented by a11; deprioritized for NOT-320; discussed rel-jun-notif-batch (H1) |
| `ticket:RISK-240` | Q3 fraud-scoring milestone | Improved fraud scoring; blocked. | Risk, Ledger | **Depends-on** LED-430; roadmap W7; standup-risk, q3-planning (P3) |
| `ticket:LED-450` | Q3 settlement-reconciliation milestone | Reconciliation between Payment and Ledger; stalled. | Ledger, Payment | **Depends-on** reconciliation-boundary ownership (unassigned); stub a14; roadmap W7 (H3, P6) |
| `ticket:LED-430` | Ledger historical export job | Export historical ledger data needed by fraud scoring; in progress, not done. | Ledger, Risk | Implemented by a12; **blocks** RISK-240; cited in standup-risk (P3) |
| `ticket:PAY-540` | Revert recent settlement hot-path change | Follow-up to Jun3: revert the implicated perf change on the settlement hot path. Wording kept implicit — the *mechanism* (idempotency guard) lives only in commits a1/a15, which V1 doesn't retrieve. | Payment | Reverts a1 via a15; child of PAY-530 (P2) |
| `ticket:NOT-320` | Re-add consumer dedup | Follow-up to Jun9: restore dedup dropped in the refactor. | Notification | Fixed by a5; child of NOT-310; consumed NOT-300's resources (H1, H2) |
| `ticket:OWN-100` | Transfer Risk Engine ownership | Ownership transfer Team Pay→Team Sentinel, effective Feb 2026, new lead Sofia Alvarez. | Risk, teams | Updates ownership-matrix; discussed ownership-risk-transfer (P4) |

### Slack threads (12)
| ID | Title | Summary | Entities | Relationships |
|---|---|---|---|---|
| `slack:rel-may-settlement` | v2.5 settlement slipping | Team notes v2.5 will slip ~2 weeks; points at LED-412 found in staging; decision to hold release until the fix is verified. | Payment, Ledger | → PAY-501, LED-412 (P1) |
| `slack:inc-jun3-charge` | Duplicate charges in prod (Jun 3) | War-room: customers double-charged; suspect Risk timeouts; someone asks "what changed recently?". | Payment, Risk | → PAY-530, RISK-220; points toward a1 (P2) |
| `slack:inc-jun9-notif` | Duplicate notifications (Jun 9) | War-room: duplicate receipts; bus is at-least-once so the consumer must dedup; a recent refactor is suspected. | Notification | → NOT-310, ADR-003; points toward a4 (H2) |
| `slack:rel-jun-notif-batch` | Batching behind schedule | Batching (NOT-300) is behind because the team was pulled onto the Jun9 dedup fix (NOT-320). | Notification | → NOT-300, NOT-320 (H1) |
| `slack:design-async-settlement` | Async vs sync settlement | Design debate behind ADR-001; consistency concerns; agreement to add idempotency keys (→ADR-004). | Ledger | → ADR-001, ADR-004 (P5) |
| `slack:ownership-risk-transfer` | Risk Engine → Team Sentinel | Announcement/discussion of the ownership transfer; Sofia takes over from Maya's team. | Risk, teams | → OWN-100; updates ownership-matrix (P4) |
| `slack:q3-planning` | Q3 milestones & blockers | Enumerates milestones; flags fraud-scoring blocked on Ledger export and reconciliation blocked on ownership. | All | → RISK-240, LED-450, LED-430, W7 (P3, H3) |
| `slack:standup-risk` | Team Sentinel standup | Fraud-scoring (RISK-240) blocked waiting on LED-430 export from Books. | Risk, Ledger | → RISK-240, LED-430 (P3) |
| `slack:standup-ledger` | Team Books standup | Reconciliation (LED-450) stalled because boundary ownership is unclear. | Ledger, Payment | → LED-450, recon-boundary (H3) |
| `slack:recon-boundary` | Who owns reconciliation? | Debate where no team claims the Payment↔Ledger reconciliation boundary; left unresolved/TBD. | Payment, Ledger | → ownership-matrix (TBD), LED-450 (P6, H3) |
| `slack:risk-timeout-debug` | Debugging Risk timeouts | Engineers add retries (RISK-220) and note retries can cause duplicate downstream calls **if the caller isn't idempotent**. | Risk, Payment | → RISK-220, a3; foreshadows Jun3 (P2) |
| `slack:notif-dedup-debug` | Dedup missing after refactor | Engineers realize the refactor (a4) removed dedup; at-least-once delivery then yields duplicates. | Notification | → a4, ADR-003, NOT-310 (H2) |

### Commits (15)
| ID | Message | Summary | Entities | Relationships |
|---|---|---|---|---|
| `commit:a1` | perf: disable idempotency check in payment settlement hot path | Removes the idempotency guard for latency — the latent seed of Jun3. | Payment | Cited by PAY-530; **reverted by a15** |
| `commit:a2` | feat(ledger): add idempotency keys to settlement (ADR-004) | Implements ADR-004. | Ledger | → ADR-004; part of LED-412 fix |
| `commit:a3` | feat(risk): retry on timeout in scoring client (RISK-220) | Adds retries to the scoring client. | Risk, Payment | → RISK-220; contributes to Jun3 retry storm |
| `commit:a4` | refactor(notif): simplify consumer | Refactor that inadvertently drops dedup. | Notification | Cited by NOT-310, notif-dedup-debug; fixed by a5 |
| `commit:a5` | fix(notif): re-add idempotent dedup (NOT-320) | Restores consumer dedup. | Notification | → NOT-320; fixes a4 (H2, H1) |
| `commit:a6` | feat(ledger): async settlement migration (ADR-001) | Implements async settlement. | Ledger | → ADR-001 (P5) |
| `commit:a7` | feat(payment): inline risk scoring (ADR-002) | Implements inline scoring. | Payment, Risk | → ADR-002 (context P2) |
| `commit:a8` | feat(notif): event-bus delivery (ADR-003) | Implements the event bus. | Notification | → ADR-003 (context H2) |
| `commit:a9` | fix(ledger): prevent settlement double-post (LED-412) | The fix that unblocked v2.5. | Ledger | → LED-412; unblocks PAY-501 (P1) |
| `commit:a10` | chore(payment): v2.5 release prep (PAY-501) | Release prep. | Payment | → PAY-501 (P1) |
| `commit:a11` | feat(notif): notification batching (NOT-300) | Batching feature, WIP/behind. | Notification | → NOT-300 (H1) |
| `commit:a12` | feat(ledger): historical export job (LED-430) | Historical export, WIP. | Ledger | → LED-430; blocks RISK-240 (P3) |
| `commit:a13` | chore(risk): deploy scoring model v4 | April model deploy. **Distractor** for Jun3 (earlier, not the cause). | Risk | No ticket; standalone |
| `commit:a14` | feat(ledger): reconciliation boundary stub (LED-450) | Incomplete stub; blocked on ownership. | Ledger, Payment | → LED-450 (P6, H3) |
| `commit:a15` | revert: re-enable idempotency check (PAY-540) | Reverts a1. | Payment | → PAY-540; reverts a1 (P2) |

### Distractors (7) — in the corpus, in NO answer chain
Semantically near the real chains (same services/keywords) so retrieval and learning are non-trivial, but never gold evidence for any question. Their job is to be plausibly retrieved and then *correctly ignored*.

| ID | Title | Summary | Entities | Why it's a trap (and why it's not the answer) |
|---|---|---|---|---|
| `slack:inc-may-latency` | Payment latency blip (May) | A brief May latency incident in Payment, auto-resolved after a cache warm-up; no charges affected. | Payment | Matches "payment + incident" for P2 retrieval, but predates Jun3 and has no duplicate-charge link |
| `slack:risk-model-v4-rollout` | Risk model v4 rollout notes | Discussion of the April model-v4 deploy (commit a13): metrics, canary, sign-off. | Risk | Reinforces the a13 distractor for P2 — a recent-ish Risk change that is *not* the cause |
| `ticket:PAY-505` | Payment receipt UI copy tweak | Cosmetic change to receipt wording; closed. | Payment | Shares the "payment" surface; irrelevant to any release/incident chain |
| `ticket:RISK-260` | Risk Engine structured logging | Add structured logs to the scoring service; unrelated to timeouts/retries. | Risk | Near RISK-220 lexically ("Risk Engine") but not part of the Jun3 chain |
| `commit:b1` | docs: update Payment service README | Documentation-only change. | Payment | Pure noise on the "payment/settlement" surface |
| `commit:b2` | test: add Ledger settlement unit tests | Test-only addition around settlement. | Ledger | Matches "settlement/idempotency" terms (P1/P5) but changes no behavior |
| `commit:b3` | chore: bump Notification deps | Dependency version bump. | Notification | Near the notification chains (H1/H2) but touches no dedup/batching logic |

---

## 3. Primary questions (P1–P6)

### P1 · release_delay · "Why did the May payment-settlement release (v2.5) slip two weeks?"
- **Evidence chain:** `slack:rel-may-settlement` → `ticket:PAY-501` (blocked-by) → `ticket:LED-412` (the bug) → `commit:a9` (the fix) [+a10, a2].
- **Why multi-source:** the Slack thread says it slipped; the *reason* lives in the ticket (LED-412); the *resolution* is in the commit. No single doc has slip + cause + fix.
- **Likely V1 failure:** blames generic "scope creep"/"testing delays" or just summarizes the thread; never names LED-412 or the fixing commit.
- **Expected learning pattern:** routing `release_delay → [release slack, blocked-by ticket, fixing commit]`; heuristic *"a release slip has a specific blocking ticket — find it and its fix."*

### P2 · prod_incident · "What caused the June 3 duplicate-charge incident?"
- **Evidence chain:** `slack:inc-jun3-charge` → `ticket:PAY-530` (RCA) → `ticket:RISK-220` + `slack:risk-timeout-debug` + `commit:a3` (retry storm) → **`commit:a1`** (idempotency guard disabled — the true root) → `ticket:PAY-540`/`commit:a15` (fix). Distractor: `commit:a13`.
- **Why multi-source:** symptom in Slack, retry mechanism across ticket+slack+commit, but the actual root cause (removed guard) exists **only** in commit a1, surfaced by the RCA. Requires joining Risk's retry behavior with Payment's removed guard.
- **Likely V1 failure:** blames Risk timeouts alone (proximate cause) or the April model deploy (a13); never inspects recent Payment commits → misses a1.
- **Expected learning pattern:** heuristic *"for incident RCA, check recent commits to the affected service for disabled/removed safeguards before blaming an upstream dependency"*; missed-evidence `commit:a1` with retrieval_signals `idempotency, guard, disable, revert`; routing `prod_incident → [incident slack, RCA ticket, recent commits]`.

### P3 · milestone_blockage · "What's blocking the Q3 fraud-scoring milestone?"
- **Evidence chain:** `wiki:q3-roadmap` (depends-on) → `ticket:RISK-240` (blocked) → `ticket:LED-430` (export, not done) + `slack:standup-risk` [+ q3-planning].
- **Why multi-source:** the milestone ticket only says "blocked"; the blocker is a *different team's* ticket (LED-430), connected via the roadmap depends-on + standup.
- **Likely V1 failure:** reports RISK-240's own status without following the cross-team dependency to LED-430.
- **Expected learning pattern:** heuristic *"milestone blockers are often cross-team dependency tickets — follow depends-on links"*; routing `milestone → [roadmap, milestone ticket, dependency ticket, standup/planning slack]`.

### P4 · service_ownership · "Who owns the Risk Engine now, and who owned it before?"
- **Evidence chain:** `wiki:ownership-matrix` (current = Sentinel/Sofia) → `ticket:OWN-100` (transfer Feb 2026) + `slack:ownership-risk-transfer`.
- **Why multi-source:** current owner is in the matrix, but "before"/when requires the transfer record — the matrix shows only current state.
- **Likely V1 failure:** returns only the current owner; omits the prior owner (Team Pay) and the transfer.
- **Expected learning pattern:** heuristic *"'who owned X before' needs the ownership-transfer record, not just the current matrix"*; routing `ownership → [matrix, transfer ticket, announcement slack]`.

### P5 · design_decision · "Why did FinFlow choose async settlement over synchronous?"
- **Evidence chain:** `wiki:adr-001-async-settlement` → `slack:design-async-settlement` (alternative weighed) → `commit:a6` [+ `wiki:adr-004` / `commit:a2` as the mitigation].
- **Why multi-source:** ADR has the decision; the debate has the alternative; the consistency mitigation is a *separate* ADR. A complete answer joins decision + tradeoff + mitigation.
- **Likely V1 failure:** says "for performance" generically; omits the alternative and the eventual-consistency tradeoff + idempotency mitigation (ADR-004).
- **Expected learning pattern:** heuristic *"design-decision answers must include the alternative considered and the tradeoff/mitigation, sourced from the ADR and any linked ADR"*; routing `design_decision → [ADR wiki, design-debate slack, implementing commit]`.

### P6 · service_ownership (contested) · "Who is responsible for the Payment→Ledger reconciliation boundary?"
- **Evidence chain:** `wiki:ownership-matrix` (boundary = TBD) → `slack:recon-boundary` (no team claims it) → `ticket:LED-450` (stalled) + `commit:a14` (stub).
- **Why multi-source:** the matrix is inconclusive; the real answer ("no single owner — unassigned/contested") only emerges from the debate + the stalled ticket. Requires recognizing the *absence* of ownership.
- **Likely V1 failure:** picks one team from the matrix as if assigned; misses that the boundary is explicitly unassigned.
- **Expected learning pattern:** heuristic *"cross-service boundary ownership may be unassigned — check design debates and stalled tickets, not just the matrix; 'no owner' is a valid answer."*

---

## 4. Held-out questions (H1–H3): structurally similar, not answer-memorization

### H1 (twin of P1) · "Why is the June notification-batching release behind schedule?"
- **Chain:** `slack:rel-jun-notif-batch` → `ticket:NOT-300` → `ticket:NOT-320`/`commit:a5` (resources pulled) [+ a11].
- **Same pattern, not memorized:** same *method/routing* (release slack → blocker ticket → commit) transfers. But the service (Notification≠Payment), entities (NOT-300/320 ≠ LED-412/PAY-501), and blocker *type* (resource reprioritization after an incident, not a staging bug) all differ. P1's answer ("LED-412 idempotency bug") is useless here — only the learned routing+heuristic helps, and those store no P1 answer text.

### H2 (twin of P2) · "What caused the June 9 duplicate-notification incident?"
- **Chain:** `slack:inc-jun9-notif` → `ticket:NOT-310` → `wiki:adr-003` + `slack:notif-dedup-debug` → **`commit:a4`** (dropped dedup) → `ticket:NOT-320`/`commit:a5` (fix).
- **Same pattern, not memorized:** identical investigative move — visible/platform cause (at-least-once bus) vs the real cause (a recent commit removed a safeguard). The heuristic *"check recent commits for removed safeguards"* + commit-log routing transfer exactly. Entities differ (Notification/ADR-003/a4 ≠ Payment/RISK-220/a1); P2's answer doesn't state H2's. Memorizing "disabled idempotency guard" gives the wrong specifics; only the method transfers.

### H3 (twin of P3) · "What's blocking the Q3 settlement-reconciliation milestone?"
- **Chain:** `wiki:q3-roadmap` → `ticket:LED-450` → `slack:recon-boundary` + `slack:standup-ledger` [+ a14].
- **Same pattern, not memorized:** same dependency-tracing method (roadmap depends-on + standup → the blocker). But the dependency's *nature* differs from P3: P3 was a concrete sibling ticket (LED-430 export); H3 is an **ownership gap** (unassigned boundary, overlapping P6). Memorizing "LED-430" is wrong here — only the "follow depends-on links" method transfers.

---

## 5. Dependency graph

**Commits → tickets/ADRs**
```
a1 ─cause→ PAY-530        a1 ─reverted-by→ a15 ─impl→ PAY-540
a2 ─impl→ ADR-004, LED-412    a3 ─impl→ RISK-220
a4 ─cause→ NOT-310, →ADR-003  a5 ─impl→ NOT-320 (fixes a4)
a6 ─impl→ ADR-001         a7 ─impl→ ADR-002       a8 ─impl→ ADR-003
a9 ─impl→ LED-412 (unblocks PAY-501)              a10 ─impl→ PAY-501
a11 ─impl→ NOT-300        a12 ─impl→ LED-430      a13 ─(no ticket: distractor)
a14 ─impl→ LED-450
```
**Tickets → tickets/wiki**
```
PAY-501 ─blocked-by→ LED-412 ─references→ ADR-004
PAY-530 ─references→ RISK-220, commit a1 ; ─child→ PAY-540
RISK-220 ─references→ ADR-002
NOT-310 ─references→ ADR-003, commit a4 ; ─child→ NOT-320 ; (NOT-300 deprioritized for NOT-320)
RISK-240 ─depends-on→ LED-430 ─in→ roadmap        LED-450 ─depends-on→ recon-boundary ─in→ roadmap
OWN-100 ─updates→ ownership-matrix
```
**Slack → tickets/ADRs**
```
rel-may-settlement → PAY-501, LED-412         inc-jun3-charge → PAY-530, RISK-220 (→a1)
inc-jun9-notif → NOT-310, ADR-003             rel-jun-notif-batch → NOT-300, NOT-320
design-async-settlement → ADR-001, ADR-004    ownership-risk-transfer → OWN-100, matrix
q3-planning → RISK-240, LED-450, LED-430      standup-risk → RISK-240, LED-430
standup-ledger → LED-450, recon-boundary      recon-boundary → matrix, LED-450
risk-timeout-debug → RISK-220, a3             notif-dedup-debug → a4, ADR-003, NOT-310
```

---

## 6. Worked example — P2 (duplicate-charge), end to end

**Question:** "What caused the June 3 duplicate-charge incident?" (`prod_incident`, cross-source).

**Root-cause rubric (for the judge):** RC1 retry storm from Risk timeouts (RISK-220/a3) · RC2 idempotency guard disabled (commit a1) · RC3 mechanism: retries no longer deduplicated → duplicate charge · RC4 fix: revert the guard (PAY-540/a15).

**Retrieval (BM25, k=4/source) for "June 3 duplicate-charge incident payment":**
- slack: `inc-jun3-charge` ✓, `risk-timeout-debug` ✓
- ticket: `PAY-530` ✓, `RISK-220` ✓, `PAY-540`
- commit: `a3` ✓, `a13` (distractor), `a15` — **`a1` ranks low** (its message is "perf/idempotency hot path", weak lexical overlap with "duplicate-charge")
- wiki: `adr-002-inline-risk`, `incident-runbook`

**V1 reasoning (no memory):** sees symptom + Risk timeouts/retries (RISK-220/a3); may also note the a13 model deploy. Concludes the proximate cause.
**V1 answer:** *"Duplicate charges were caused by Risk Engine timeouts that triggered automatic payment retries."* → hits RC1 (+ partial RC3), **misses RC2 & RC4** → low root-cause coverage; `commit:a1` absent from citations.

**Gap analysis vs expert:** `missed_evidence_ids = [commit:a1, commit:a15]`; `missed_root_causes = [idempotency guard disabled]`; reasoning_gap = *"stopped at the proximate cause; did not check recent Payment commits for a removed safeguard."*

**Learning event (sanitized, no verbatim answer):** heuristic *"for incident RCA, check recent commits to the affected service for disabled/removed safeguards"*; missed-evidence pattern with retrieval_signals `idempotency, guard, disable, revert`; routing `prod_incident → [incident slack, RCA ticket, recent commits]`.

**V2 (memory-injected):** routing boosts the commit source; query expansion adds `idempotency/guard/disable` → **`a1` and `a15` now retrieved**; the heuristic in the reasoning prompt makes the model check recent commits.
**V2 answer:** *"Duplicate charges resulted from a retry storm (Risk Engine timeouts, RISK-220/a3) hitting a payment path whose idempotency guard had been disabled for performance (commit a1); with the guard removed, retried charges were no longer deduplicated. Fixed by reverting the guard (PAY-540/a15)."* → covers RC1–RC4; **cites a1** (newly-routed, previously-missed → satisfies anti-memorization gate (d)).

**Measured effect:** root-cause coverage ~25–50% → ~100%; evidence recall rises (a1, a15 now matched); similarity up — a clean, honest V1→V2 improvement driven by a *generalizable* method, not a leaked answer.

---

## 7. Root-cause rubrics (for `judge_root_cause_v1`)

Each element is scored hit / partial / miss; coverage = Σ(scores)/len. These ship in `human_answers.json` as `root_cause_rubric`. The **bold** element is the one V1 is expected to miss and V2 to recover.

**P1 — release_delay**
- RC1: The release was deliberately **held/delayed**, not cancelled or de-scoped.
- RC2: **Names the specific blocker — the settlement idempotency bug (LED-412).**
- RC3: The bug was caught in staging/testing before shipping.
- RC4: Unblock condition = the fix was merged and verified (commit a9).

**P2 — prod_incident**
- RC1: Retry storm from Risk Engine timeouts (RISK-220 / a3).
- RC2: **The idempotency guard was disabled in the payment path (commit a1).**
- RC3: Mechanism — with the guard removed, retried charges were no longer deduplicated → duplicates.
- RC4: Fix = revert / re-enable the guard (PAY-540 / a15).

**P3 — milestone_blockage**
- RC1: The milestone is blocked (not merely "in progress").
- RC2: **Blocker = the Ledger historical export dependency (LED-430).**
- RC3: It is a cross-team dependency (Books owns LED-430; Sentinel owns RISK-240).
- RC4: The dependency is incomplete / still in progress.

**P4 — service_ownership**
- RC1: Current owner = Team Sentinel (Sofia Alvarez).
- RC2: **Previous owner = Team Pay.**
- RC3: Ownership transferred (OWN-100), ~Feb 2026.

**P5 — design_decision**
- RC1: Decision = async settlement chosen for throughput/scalability.
- RC2: Alternative considered = synchronous settlement.
- RC3: Tradeoff = eventual-consistency window.
- RC4: **Mitigation = idempotency keys (ADR-004).**

**P6 — service_ownership (contested)**
- RC1: The boundary has **no single/clear owner** (TBD/contested).
- RC2: The ownership matrix marks it TBD/shared.
- RC3: An unresolved design debate confirms it (recon-boundary).
- RC4: This is why reconciliation work (LED-450) is stalled.

**H1 — release_delay (held-out)**
- RC1: The batching release is behind/delayed.
- RC2: **Cause = the team was pulled onto the Jun 9 dedup fix (NOT-320).**
- RC3: Affected work = the batching ticket NOT-300.
- RC4: I.e., reprioritization after the incident, not a code defect.

**H2 — prod_incident (held-out)**
- RC1: The event bus is at-least-once, so consumers must dedup (ADR-003).
- RC2: **Dedup was dropped in a recent refactor (commit a4).**
- RC3: Mechanism — at-least-once + no dedup → duplicate notifications.
- RC4: Fix = re-add dedup (NOT-320 / a5).

**H3 — milestone_blockage (held-out)**
- RC1: The reconciliation milestone is blocked.
- RC2: **Blocker = the unassigned reconciliation-boundary ownership.**
- RC3: A cross-cutting/ownership dependency (recon-boundary debate, LED-450).
- RC4: Work is stalled / the stub (a14) is incomplete.

---

## 8. Gold evidence sets (for deterministic evidence coverage)

`evidence_coverage = |gold ∩ cited| / |gold|`. These ship in `human_answers.json` as `key_source_ids`. The **bold** id is the one V1 typically misses (drives the V1→V2 recall gain).

| Q | gold_evidence_ids |
|---|---|
| **P1** | `slack:rel-may-settlement`, `ticket:PAY-501`, `ticket:LED-412`, **`commit:a9`** |
| **P2** | `slack:inc-jun3-charge`, `ticket:PAY-530`, `ticket:RISK-220`, `commit:a3`, **`commit:a1`**, `commit:a15` |
| **P3** | `wiki:q3-roadmap`, `ticket:RISK-240`, **`ticket:LED-430`**, `slack:standup-risk` |
| **P4** | `wiki:ownership-matrix`, **`ticket:OWN-100`**, `slack:ownership-risk-transfer` |
| **P5** | `wiki:adr-001-async-settlement`, `slack:design-async-settlement`, **`wiki:adr-004-ledger-idempotency`**, `commit:a6` |
| **P6** | `wiki:ownership-matrix`, **`slack:recon-boundary`**, `ticket:LED-450`, `commit:a14` |
| **H1** | `slack:rel-jun-notif-batch`, `ticket:NOT-300`, **`ticket:NOT-320`**, `commit:a5` |
| **H2** | `slack:inc-jun9-notif`, `ticket:NOT-310`, `wiki:adr-003-notif-eventbus`, **`commit:a4`**, `commit:a5` |
| **H3** | `wiki:q3-roadmap`, `ticket:LED-450`, **`slack:recon-boundary`**, `slack:standup-ledger`, `commit:a14` |

---

## 9. Retrieval-debugging table (primary questions)

How BM25 V1 retrieval is expected to fall short, and the learned signal/routing that fixes it in V2. This is the concrete mechanism behind the evidence-coverage and root-cause gains.

| Q | Expected V1 retrieval miss (and why) | Learned retrieval improvement (V2) |
|---|---|---|
| **P1** | Under-ranks `ticket:LED-412` and `commit:a9` — the question words ("slip / delayed / two weeks") don't appear in a bug ticket or a "prevent double-post" commit. | Routing `release_delay → [release slack, blocked-by ticket, fixing commit]` + expansion terms `idempotency, double-posting, LED-412` surface LED-412 and a9. |
| **P2** | Misses `commit:a1` — its message "perf: disable idempotency check" has near-zero lexical overlap with "duplicate charge"; a13 (distractor) may out-rank it. | Expansion signals `idempotency, guard, disable, revert` + commit-source routing pull `a1` and `a15` to the top. |
| **P3** | Misses `ticket:LED-430` ("historical data export job") — no overlap with "blocking fraud-scoring milestone"; retrieval stops at RISK-240 + roadmap. | Follow-the-dependency routing: expand with the depends-on id from the roadmap/RISK-240 → `LED-430`; pull `standup-risk`. |
| **P4** | Under-ranks `ticket:OWN-100` / `slack:ownership-risk-transfer` — "who owns … before" weakly matches a transfer record; matrix dominates. | Ownership routing adds the transfer ticket + announcement; expansion `transfer, previously, formerly, handover`. |
| **P5** | Misses `wiki:adr-004` (separate ADR) and `commit:a6` — "async vs synchronous" matches ADR-001/debate, not the idempotency-mitigation ADR. | `design_decision` routing pulls linked ADRs + the implementing commit; expansion `idempotency, consistency, tradeoff, mitigation`. |
| **P6** | Retrieves `ownership-matrix` only and treats it as authoritative; under-ranks `slack:recon-boundary` (the debate proving no owner). | Routing to design-debate slack + stalled ticket; expansion `boundary, reconciliation, unassigned, unowned, contested`. |
