FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Cloud Run injects $PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

# UID/GID 1000 matches the group Render uses for mounted secret files, so the app user
# can read /etc/secrets/*.json (they are root:1000, mode 0640).
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY:-2}"]
