#!/bin/sh
# Multi-mode entrypoint. First arg selects the mode; remaining args pass through.
#   dashboard (default) | eval | tests | pipeline | seed | <any command>
set -e

mode="${1:-dashboard}"
[ "$#" -gt 0 ] && shift || true

case "$mode" in
  dashboard)
    # seed_db is idempotent (INSERT OR REPLACE); no LLM/key needed to seed inputs.
    python scripts/seed_db.py || true
    exec streamlit run dashboard/app.py \
      --server.port "${PORT:-8501}" --server.address 0.0.0.0 --server.headless true
    ;;
  live)
    # interactive human-in-the-loop page (needs GROQ_API_KEY)
    python scripts/seed_db.py || true
    exec streamlit run dashboard/live_app.py \
      --server.port "${PORT:-8501}" --server.address 0.0.0.0 --server.headless true
    ;;
  eval)
    exec python scripts/run_evaluation.py "$@"
    ;;
  pipeline)
    exec python scripts/run_pipeline.py "$@"
    ;;
  seed)
    exec python scripts/seed_db.py
    ;;
  tests)
    exec python -m pytest "$@"
    ;;
  *)
    # Allow arbitrary commands: `docker run ... python -c '...'`
    exec "$mode" "$@"
    ;;
esac
