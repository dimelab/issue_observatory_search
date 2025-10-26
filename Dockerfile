# Multi-stage Dockerfile for Issue Observatory Search

# Stage 1: Base image with Python
FROM python:3.14-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /app

# Stage 2: Development image
FROM base as development

# Copy dependency files
COPY setup.py setup.cfg ./
COPY README.md ./

# Copy backend package
COPY backend ./backend

# Install dependencies in editable mode
RUN pip install -e ".[dev]"

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run development server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Production image
FROM base as production

# Copy dependency files
COPY setup.py setup.cfg ./
COPY README.md ./

# Install production dependencies
RUN pip install .

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
