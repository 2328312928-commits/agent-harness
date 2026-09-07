FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY agent_harness ./agent_harness
COPY evals/dataset ./evals/dataset
RUN pip install --upgrade pip && pip install .

RUN useradd --create-home --uid 10001 harness \
    && mkdir -p /workspace /app/data \
    && chown -R harness:harness /workspace /app/data

USER harness

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "agent_harness.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

