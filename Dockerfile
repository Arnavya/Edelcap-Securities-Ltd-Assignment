# FinFlow Reasoning Engine — single image, multi-mode (dashboard / eval / tests / pipeline).
FROM python:3.11-slim

WORKDIR /app

# Non-root runtime user.
RUN useradd -m -u 1000 finflow

# Dependencies first (layer caching). Pure-Python deps — no build toolchain needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (secrets and local DBs excluded via .dockerignore).
COPY . .

# Writable DB location + entrypoint perms; drop privileges.
RUN chmod +x entrypoint.sh \
    && mkdir -p /data \
    && chown -R finflow:finflow /app /data

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FINFLOW_DB=/data/finflow.db

USER finflow
EXPOSE 8501

ENTRYPOINT ["./entrypoint.sh"]
CMD ["dashboard"]
