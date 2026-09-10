# Multi-stage Dockerfile for Issue Observatory Search

# Stage 1: Base image with Python
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies. The lib* block is Chromium's runtime set, installed by
# hand because "playwright install --with-deps" (1.41) asks apt for ttf-unifont
# and ttf-ubuntu-font-family, which no longer exist on Debian 12 (bookworm), so
# it aborts before downloading the browser.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxcb1 libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libglib2.0-0 libexpat1 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /app

# Stage 2: Development image
FROM base as development

# Copy dependency files. requirements.txt is required here: setup.py reads
# install_requires from it and silently installs nothing if it is missing.
COPY setup.py setup.cfg requirements.txt ./
COPY README.md ./

# Copy backend package
COPY backend ./backend

# Install dependencies in editable mode
RUN pip install -e ".[dev]"

# spaCy models required for content analysis, pinned to the versions the
# compatibility table lists for spacy 3.7. Installed by direct wheel URL rather
# than "spacy download": that command resolves the version from a compatibility
# file it fetches at build time, and when that fetch fails it silently builds a
# versionless URL and dies on a 404.
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl \
    https://github.com/explosion/spacy-models/releases/download/da_core_news_sm-3.7.0/da_core_news_sm-3.7.0-py3-none-any.whl

# Browser only; its shared libraries came from apt in the base stage.
RUN playwright install chromium

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run development server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Production image
FROM base as production

# Copy dependency files. requirements.txt is required here: setup.py reads
# install_requires from it and silently installs nothing if it is missing.
COPY setup.py setup.cfg requirements.txt ./
COPY README.md ./

# Install production dependencies
RUN pip install .

# spaCy models required for content analysis, pinned to the versions the
# compatibility table lists for spacy 3.7. Installed by direct wheel URL rather
# than "spacy download": that command resolves the version from a compatibility
# file it fetches at build time, and when that fetch fails it silently builds a
# versionless URL and dies on a 404.
RUN pip install --no-cache-dir \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl \
    https://github.com/explosion/spacy-models/releases/download/da_core_news_sm-3.7.0/da_core_news_sm-3.7.0-py3-none-any.whl

# Copy application code
COPY backend ./backend
COPY migrations ./migrations
COPY alembic.ini ./

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run production server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
