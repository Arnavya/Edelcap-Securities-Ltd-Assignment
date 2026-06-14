# DOCKER_GUIDE — FinFlow Reasoning Engine

One image, four modes, no secrets baked in. Secrets are injected only via the
environment / `.env` (which is `.dockerignore`d and never copied into the image).

## Prerequisites
- Docker Engine + Compose v2 (tested: Docker 29.5.3, Compose v5.1.4).
- A Groq API key for the dashboard's live answers and for evaluation (the **test**
  mode needs no key). Put it in `.env`:
  ```
  cp .env.example .env      # then set GROQ_API_KEY=...
  ```

## Build
```bash
docker build -t finflow-reasoning-engine:latest .
# or
docker compose build
```

## Run modes

### 1) Dashboard (default)
```bash
docker compose up app
# open http://localhost:8501
```
On start it seeds the SQLite inputs (idempotent, no key needed) then serves the
read-only dashboard. Has a healthcheck on `/_stcore/health`.

Plain Docker equivalent:
```bash
docker run --rm -p 8501:8501 --env-file .env -v finflow-db:/data finflow-reasoning-engine
```

### 2) Evaluation (needs GROQ_API_KEY + quota)
```bash
docker compose --profile eval run --rm eval
```

### 3) Tests (offline, no key)
```bash
docker compose --profile tests run --rm tests
# plain docker:
docker run --rm -e FINFLOW_PROVIDER=mock finflow-reasoning-engine tests
```

### 4) Pipeline / arbitrary commands
```bash
docker run --rm --env-file .env -v finflow-db:/data finflow-reasoning-engine pipeline --question P2
docker run --rm --env-file .env -v finflow-db:/data finflow-reasoning-engine seed
docker run --rm finflow-reasoning-engine python -c "import finflow; print(finflow.__version__)"
```

## Environment variables (all optional except the key for live use)
| Var | Default (image) | Purpose |
|---|---|---|
| `FINFLOW_PROVIDER` | `groq` | `groq` or `mock` |
| `GROQ_API_KEY` | — (from `.env`) | required for `groq` provider |
| `FINFLOW_MODEL` | `llama-3.3-70b-versatile` | investigation/gap/learning model |
| `FINFLOW_JUDGE_MODEL` | = `FINFLOW_MODEL` | judge model |
| `FINFLOW_DB` | `/data/finflow.db` | SQLite path (mounted volume) |
| `FINFLOW_RETRIEVAL_K` | `4` | per-source top-k |
| `PORT` | `8501` | dashboard port |

## Data persistence
Generated artifacts live in the named volume `finflow-db` (mounted at `/data`).
Reset everything:
```bash
docker compose down -v
```

## Health check
The `app` service reports healthy once Streamlit answers `GET /_stcore/health`
(interval 30s, 5 retries, 20s start period). Check with:
```bash
docker inspect --format '{{.State.Health.Status}}' <container>
```

## Troubleshooting
- **`GROQ_API_KEY is required`** — you ran `eval`/live `dashboard` without a key. Add it to `.env`, or use `tests`/`FINFLOW_PROVIDER=mock`.
- **`429 RateLimitError`** — Groq daily token quota; wait for reset or use a higher tier. Not a container issue.
- **Empty dashboard** — no runs persisted yet. Run `pipeline`/`eval` first (they write to the `finflow-db` volume the dashboard reads).
- **`exec: -q: not found`** — don't append pytest args after a compose service name; `docker compose run tests <X>` overrides the command. Use the service default, or `docker run ... tests -q`.
