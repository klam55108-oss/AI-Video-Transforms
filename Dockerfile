# Multi-stage build for production-optimized image
FROM python:3.11-slim AS base

# Install system dependencies
# ffmpeg: Required for video/audio processing (pydub, transcription)
# curl: Required for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user for security
RUN useradd -m -u 1000 agent
WORKDIR /app

# Copy dependency files first (leverage Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (production only, no dev dependencies)
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/

# Create data directories with proper ownership
RUN mkdir -p data/sessions data/transcripts data/kg_projects data/exports data/knowledge_bases \
    && chown -R agent:agent /app

# Switch to non-root user
USER agent

# Expose application port
EXPOSE 8000

# Health check endpoint
# Checks /health endpoint every 30s with 10s timeout
# Gives 5s for app startup before first check
# Fails after 3 consecutive failures
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application with production settings
# Bind to 0.0.0.0 to accept connections from outside container
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
