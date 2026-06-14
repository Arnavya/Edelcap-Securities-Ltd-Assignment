# REPO_TREE — FinFlow Reasoning Engine

Generated during the release-candidate audit (excludes `__pycache__`, `*.pyc`,
`*.db`, `retrieval_snapshots/`, `.pytest_cache`).

```
finflow-reasoning-engine/
├── README.md  requirements.txt  pyproject.toml  .env.example  .gitignore
├── PROJECT_STATUS.md  TECHNICAL_DEBT.md  RESEARCH_FINDINGS.md  REPO_TREE.md  RELEASE_READINESS.md
├── finflow/                         # 42 .py files, ~2,620 LOC
│   ├── __init__.py  config.py  orchestrator.py
│   ├── models/        (10) answer, evaluation, evidence, gap, human_answer,
│   │                       learning, question, reasoning, retrieval, __init__
│   ├── llm/           (5)  base, groq_provider, mock_provider, factory, __init__
│   ├── retrieval/     (7)  retriever, bm25_retriever, expansion, knowledge_store,
│   │                       loaders, snapshot_store, __init__
│   ├── agents/        (5)  investigation_agent, gap_analysis_agent,
│   │                       learning_event_generator, json_parsing, __init__
│   ├── memory/        (2)  learning_memory, __init__
│   ├── evaluation/    (6)  judge, evaluator, evidence_overlap, improvement,
│   │                       leakage, __init__
│   ├── persistence/   (3)  repository, sqlite_repo, __init__
│   └── prompts/       (1 .py + 8 .txt)
│       ├── investigation_v1.txt   investigation_v2.txt
│       ├── gap_v1.txt
│       ├── learning_extract_v1.txt  learning_extract_v2.txt
│       ├── judge_similarity_v1.txt  judge_similarity_v2.txt
│       └── judge_root_cause_v1.txt
├── data/                            # synthetic corpus (authored, version-controlled)
│   ├── DATASET_DESIGN.md
│   ├── feed.json                    # 9 questions (6 primary + 3 held-out)
│   ├── human_answers.json           # 9 ground-truth answers + rubrics + gold evidence
│   └── sources/
│       ├── slack_threads.json (14)  tickets.json (14)
│       └── wiki.json (8)            commits.json (18)        = 54 evidence items
├── scripts/   run_pipeline.py  run_evaluation.py  seed_db.py
├── dashboard/ __init__.py  data.py  app.py  live_app.py  ui.py   (read-only + interactive HITL)
└── tests/                           # 10 files, 90 tests
    ├── conftest.py  helpers.py  __init__.py
    ├── test_models.py          (8)
    ├── test_llm_providers.py   (11)
    ├── test_dataset.py         (12)
    ├── test_retrieval.py       (18)
    ├── test_investigation.py   (8)
    ├── test_gap_analysis.py    (5)
    ├── test_learning.py        (9)
    ├── test_evaluation.py      (9)
    ├── test_interactive.py     (3)
    └── test_dashboard.py       (7)
```

## Counts
| Category | Count |
|---|---|
| Python source files (`finflow/`) | 42 |
| Prompt templates (`.txt`) | 9 |
| Scripts | 3 |
| Dashboard modules | 5 (read-only `app.py` + interactive `live_app.py` + shared `ui.py`) |
| Test files | 10 |
| **Tests** | **90 (all passing, offline)** |
| Total tracked files (zip contents) | 98 |
| Evidence items | 54 (14 slack / 14 ticket / 8 wiki / 18 commit) |
| Questions | 9 (6 primary + 3 held-out) |
| SQLite tables | 9 |
