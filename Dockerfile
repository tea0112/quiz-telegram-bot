# syntax=docker/dockerfile:1.7

# -------- Base image with Python and uv --------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    UV_SYSTEM_PYTHON=1

# Install system deps (curl for uv install, locales, tzdata)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
      curl ca-certificates tzdata locales \
    && rm -rf /var/lib/apt/lists/*

# Set UTF-8 locale
RUN sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# -------- Dependency resolution (cached) --------
# Copy only project metadata first to maximize cache hits
COPY pyproject.toml README.md ./

# Resolve and download dependencies to a local cache layer
# If a lockfile is present, use a frozen install. Otherwise, create it.
RUN if [ -f uv.lock ]; then \
      uv sync --frozen --no-editable; \
    else \
      uv sync --no-editable && uv lock; \
    fi

# -------- Runtime image --------
FROM base AS runtime

ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} appuser && useradd -m -u ${UID} -g ${GID} appuser

# Copy application code
COPY . .

# Ensure questions directory exists (mounted in compose/helm typically)
RUN mkdir -p /app/questions /app/data

# Set permissions for runtime directories
RUN chown -R appuser:appuser /app

USER appuser

# Environment defaults (override via env or .env file when running)
ENV QUESTIONS_DIRECTORY=/app/questions \
    DATABASE_PATH=/app/data/quiz_bot.db \
    TZ=UTC

# Data volume for persistent database
VOLUME ["/app/data", "/app/questions"]

# Healthcheck: simple ping by starting Python to import modules
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import importlib;importlib.import_module('bot') and print('ok')" || exit 1

# Default command uses uv to run the bot
CMD ["uv", "run", "bot.py"]


