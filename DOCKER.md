# Docker Deployment Guide

This document provides instructions for running agent-video-to-data in Docker containers.

## Quick Start

### 1. Prerequisites

- Docker 20.10+
- docker-compose 1.29+ (or Docker Compose V2)
- Environment variables set in `.env` file

### 2. Environment Setup

Create a `.env` file in the project root with your API keys:

```bash
cp .env.example .env
# Edit .env and add your API keys:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```

### 3. Run with Docker Compose

```bash
# Build and start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

The application will be available at `http://localhost:8000`.

## Manual Docker Build

### Build the Image

```bash
docker build -t agent-video-to-data:latest .
```

### Run the Container

```bash
docker run -d \
  --name agent-video-to-data \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  agent-video-to-data:latest
```

## Health Checks

The container includes a health check endpoint at `/health`:

```bash
# Check health status
curl http://localhost:8000/health
# Response: {"status":"ok"}

# View health status
docker inspect --format='{{.State.Health.Status}}' agent-video-to-data
```

## Data Persistence

The `data/` directory is mounted as a volume to persist:
- Session data (`data/sessions/`)
- Transcripts (`data/transcripts/`)
- Knowledge graph projects (`data/kg_projects/`)
- Exports (`data/exports/`)

## Configuration

### Environment Variables

Override default settings by adding to `.env` or docker-compose.yml:

```yaml
environment:
  - APP_CLAUDE_MODEL=claude-opus-4-5
  - APP_CLAUDE_API_MAX_CONCURRENT=2
  - APP_RESPONSE_TIMEOUT=300.0
  - APP_SESSION_TTL=3600.0
```

See `.env.example` for all available configuration options.

## Security

### Non-Root User

The container runs as a non-root user (`agent`, UID 1000) for security best practices.

### API Keys

**NEVER** commit `.env` to version control. API keys are passed as environment variables at runtime.

## Troubleshooting

### Container won't start

Check logs for errors:

```bash
docker-compose logs app
```

### Health check failing

Ensure the application has started before the health check runs (5s startup period):

```bash
docker ps -a
docker logs agent-video-to-data
```

### Permission issues with data volume

Ensure the `data/` directory is writable:

```bash
chmod -R 755 data/
```

### Missing dependencies

If you modify `pyproject.toml`, rebuild the image:

```bash
docker-compose build --no-cache
```

## Production Deployment

### Resource Limits

Add resource constraints in docker-compose.yml:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Reverse Proxy

For production, use a reverse proxy (nginx, Traefik) with HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Monitoring

The `/health` endpoint can be used with monitoring tools:

- **Docker**: Built-in health checks
- **Kubernetes**: liveness/readiness probes
- **Prometheus**: Custom metrics endpoint (future enhancement)

## Development

### Live Reload

For development with live reload, override the CMD:

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/app:/app/app \
  -v $(pwd)/data:/app/data \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  agent-video-to-data:latest \
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Image Size Optimization

The Dockerfile uses a multi-stage build pattern for optimization:

- Base: Python 3.11-slim (~50MB base)
- System deps: ffmpeg, curl (~100MB)
- Python deps: Production only via uv (~200MB)
- Final image: ~400-500MB

## References

- [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)
- [Docker Compose specification](https://docs.docker.com/compose/compose-file/)
- [Docker health checks](https://docs.docker.com/engine/reference/builder/#healthcheck)
