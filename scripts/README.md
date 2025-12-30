# Pre-Release Test Scripts

Step-by-step instructions for running CognivAgent's pre-release validation tests.

---

## Quick Reference

| Script | Tests | Duration | API Keys Needed |
|--------|-------|----------|-----------------|
| `test-dev-install.sh` | Developer mode + test suite | 5-10 min | Optional |
| `test-user-install.sh` | User mode (minimal) | 2-3 min | Optional |
| `test-docker.sh` | Docker build + container | 3-7 min | Optional |

**Recommended order**: Developer → User → Docker

---

## General Information

### Where to Run From

**Run all scripts from the project root directory:**

```bash
cd /path/to/CognivAgent
./scripts/test-docker.sh
```

Or from anywhere using the full path:

```bash
/path/to/CognivAgent/scripts/test-docker.sh
```

### Virtual Environment

**No virtual environment activation needed!**

- Scripts clone a fresh repo to `/tmp/` for isolation
- Each test creates its own `.venv` via `uv sync`
- Your current environment is not modified

### Output Locations

| Output | Location | Description |
|--------|----------|-------------|
| Test directory | `/tmp/cognivagent-*-test/` | Fresh clone for each test |
| Server logs | `/tmp/cognivagent-*-test-server.log` | Uvicorn output |
| Console output | Terminal (stdout/stderr) | Color-coded results |

**All test artifacts are automatically cleaned up on exit.**

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All tests passed |
| `1` | One or more tests failed |

---

## Test 1: Developer Mode Installation

### Purpose
Validates the full development environment including test suite, type checking, and linting.

### Prerequisites

| Requirement | Check Command | Install |
|-------------|---------------|---------|
| Python 3.11+ | `python3 --version` | `sudo apt install python3.11` |
| FFmpeg | `ffmpeg -version` | `sudo apt install ffmpeg` |
| git | `git --version` | `sudo apt install git` |
| curl | `curl --version` | `sudo apt install curl` |
| Port 8000 free | `ss -tlnp \| grep :8000` | Stop conflicting service |

### Step-by-Step Instructions

#### Step 1: Navigate to Project Root

```bash
cd /path/to/CognivAgent
```

#### Step 2: Verify Prerequisites

```bash
python3 --version    # Should show 3.11+
ffmpeg -version      # Should show 4.x+
ss -tlnp | grep :8000  # Should be empty (port free)
```

#### Step 3: Run Quick Validation (No API)

```bash
./scripts/test-dev-install.sh
```

**What happens:**
1. Clones fresh repo to `/tmp/cognivagent-dev-test/`
2. Runs `install.sh` → Native Python → Developer mode
3. Verifies `data/`, `uploads/`, `examples/demo/` created
4. Verifies pytest, mypy, ruff are installed
5. Runs full test suite (910 tests) — **takes 3-5 minutes**
6. Runs `mypy .` type checking
7. Runs `ruff check .` and `ruff format --check .`
8. Starts server, checks health endpoint
9. Cleans up everything

#### Step 4 (Optional): Run with API Validation

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"
./scripts/test-dev-install.sh --with-api-test
```

**Additional tests with `--with-api-test`:**
- Initializes a chat session
- Validates API keys work end-to-end

### Expected Output

```
========================================================
  CognivAgent Pre-Release Test: Developer Mode Install
========================================================

[INFO] Running quick validation (no API tests)

[STEP] Checking prerequisites...
[PASS] Python 3.11 installed (3.11+ required)
[PASS] FFmpeg installed (version: 6.1)
[PASS] curl is installed
[PASS] git is installed
[PASS] Port 8000 is available

[STEP] Cloning repository to /tmp/cognivagent-dev-test...
[PASS] Repository cloned successfully
[PASS] install.sh present

[STEP] Running install.sh (Developer mode)...
[PASS] install.sh completed successfully
[PASS] Dependency installation message found
[PASS] Developer mode confirmed in output

[STEP] Verifying directory structure...
[PASS] data/ directory created
[PASS] uploads/ directory created
[PASS] examples/demo/ directory created (Developer mode)
[PASS] .env file created
[PASS] .venv directory created

[STEP] Verifying dev dependencies ARE installed...
[PASS] pytest installed (pytest 8.3.4)
[PASS] mypy installed (mypy 1.13.0)
[PASS] ruff installed (ruff 0.8.4)

[STEP] Running test suite (this may take several minutes)...
[PASS] Test suite passed (910 tests in 180s)

[STEP] Running type checking (mypy)...
[PASS] Type checking passed

[STEP] Running linter (ruff check)...
[PASS] Linting passed

[STEP] Checking code formatting (ruff format)...
[PASS] Code formatting check passed

...

--------------------------------------------------------

Test Results Summary

  Total:  18
  Passed: 18
  Failed: 0

All tests passed!

--------------------------------------------------------
```

### Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Python 3.10 is below required 3.11+" | Wrong Python version | Install Python 3.11+ |
| "FFmpeg not found" | Missing FFmpeg | `sudo apt install ffmpeg` |
| Test suite timeout | Slow machine | Tests have 10-min timeout |
| "Port 8000 is already in use" | Another service running | `sudo kill $(lsof -t -i:8000)` |

---

## Test 2: User Mode Installation

### Purpose
Validates the minimal production installation for end users (no dev tools).

### Prerequisites

Same as Developer mode (see above).

### Step-by-Step Instructions

#### Step 1: Navigate to Project Root

```bash
cd /path/to/CognivAgent
```

#### Step 2: Run Quick Validation

```bash
./scripts/test-user-install.sh
```

**What happens:**
1. Clones fresh repo to `/tmp/cognivagent-user-test/`
2. Runs `install.sh` → Native Python → User (minimal)
3. Verifies `data/`, `uploads/` created
4. Verifies `examples/demo/` does NOT exist (User mode)
5. Verifies pytest, mypy, ruff are NOT installed
6. Starts server, checks health endpoint
7. Cleans up everything

#### Step 3 (Optional): Run with API Validation

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"
./scripts/test-user-install.sh --with-api-test
```

### Expected Output

```
========================================================
  CognivAgent Pre-Release Test: User Mode Installation
========================================================

[INFO] Running quick validation (no API tests)

[STEP] Checking prerequisites...
[PASS] Python 3.11 installed (3.11+ required)
[PASS] FFmpeg installed (version: 6.1)
...

[STEP] Running install.sh (User mode)...
[PASS] install.sh completed successfully
[PASS] User mode (no-dev) confirmed in output

[STEP] Verifying directory structure...
[PASS] data/ directory created
[PASS] uploads/ directory created
[PASS] examples/demo/ correctly absent (User mode)
[PASS] .env file created
[PASS] .venv directory created

[STEP] Verifying dev dependencies are NOT installed...
[PASS] pytest correctly NOT installed (User mode)
[PASS] mypy correctly NOT installed (User mode)
[PASS] ruff correctly NOT installed (User mode)

...

Test Results Summary

  Total:  14
  Passed: 14
  Failed: 0

All tests passed!
```

### Key Differences from Developer Mode

| Aspect | User Mode | Developer Mode |
|--------|-----------|----------------|
| `examples/demo/` | NOT created | Created |
| pytest | NOT installed | Installed |
| mypy | NOT installed | Installed |
| ruff | NOT installed | Installed |
| Test suite | NOT run | 910 tests run |
| Install command | `uv sync --no-dev` | `uv sync` |

---

## Test 3: Docker Installation

### Purpose
Validates Docker image build, container startup, health checks, and data persistence.

### Prerequisites

| Requirement | Check Command | Install |
|-------------|---------------|---------|
| Docker Engine 20.10+ | `docker --version` | [Docker Install Guide](https://docs.docker.com/engine/install/) |
| Docker Compose 2.x+ | `docker compose version` | Included with Docker Desktop |
| Docker daemon running | `docker ps` | `sudo systemctl start docker` |
| Port 8000 free | `ss -tlnp \| grep :8000` | Stop conflicting service |
| 2GB+ disk space | `df -h /var/lib/docker` | Free up space |

**Note:** No Python, FFmpeg, or uv needed on host — Docker image includes everything!

### Step-by-Step Instructions

#### Step 1: Navigate to Project Root

```bash
cd /path/to/CognivAgent
```

#### Step 2: Verify Docker is Running

```bash
docker ps  # Should not error
docker compose version  # Should show 2.x+
```

#### Step 3: Run Quick Validation

```bash
./scripts/test-docker.sh
```

**What happens:**
1. Clones fresh repo to `/tmp/cognivagent-docker-test/`
2. Creates `.env` from `.env.example`
3. Builds Docker image (`docker compose build`) — **takes 2-5 minutes first time**
4. Starts container (`docker compose up -d`)
5. Waits for container to become "healthy" (max 60s)
6. Tests `/health` endpoint
7. Tests main page loads
8. Tests data persistence across container restart
9. Stops container (`docker compose down`)
10. Cleans up everything

#### Step 4 (Optional): Run with API Validation

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"
./scripts/test-docker.sh --with-api-test
```

### Expected Output

```
========================================================
  CognivAgent Pre-Release Test: Docker Installation
========================================================

[INFO] Running quick validation (no API tests)

[STEP] Checking prerequisites...
[PASS] Docker installed (version: 24.0)
[PASS] Docker Compose installed (version: 2.21)
[PASS] Docker daemon is running
[PASS] Port 8000 is available
[PASS] Sufficient disk space (45000MB free)

[STEP] Cloning repository to /tmp/cognivagent-docker-test...
[PASS] Repository cloned successfully
[PASS] Dockerfile and docker-compose.yml present

[STEP] Setting up environment...
[PASS] Created .env from .env.example
[INFO] Using placeholder API keys (--with-api-test not specified)

[STEP] Building Docker image (this may take 2-5 minutes)...
... (build output)
[PASS] Docker image built successfully (120s)

[STEP] Starting Docker container...
[PASS] Container started
[PASS] Container is running

[STEP] Waiting for container to become healthy (max 60s)...
[PASS] Container is healthy (8s)

[STEP] Testing health endpoint...
[PASS] Health endpoint returns expected response

[STEP] Testing if main page loads...
[PASS] Main page returns HTTP 200
[PASS] ES modules detected in page
[PASS] Cytoscape.js library referenced

[STEP] Testing data persistence across restart...
[PASS] Marker file created in data/
[INFO] Restarting container...
[PASS] Data persisted across container restart

[STEP] Testing container cleanup...
[PASS] Container stopped via docker compose down
[PASS] Container removed successfully

--------------------------------------------------------

Test Results Summary

  Total:  16
  Passed: 16
  Failed: 0

All tests passed!

--------------------------------------------------------
```

### Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Docker daemon not running" | Docker service stopped | `sudo systemctl start docker` |
| "Permission denied" on docker | User not in docker group | `sudo usermod -aG docker $USER` then logout/login |
| Build fails at apt-get | Network issue | Check internet connection, retry |
| Container unhealthy | Startup crash | Check `docker logs cognivagent` |
| "Port 8000 is already in use" | Another container/service | `docker stop cognivagent` or kill other process |

### Viewing Container Logs

If a test fails, you can inspect the container logs:

```bash
# During test (in another terminal)
docker logs cognivagent -f

# After test failure (before cleanup)
docker logs cognivagent 2>&1 | tail -50
```

---

## Running All Three Tests

### Sequential Execution (Recommended Order)

```bash
cd /path/to/CognivAgent

# 1. Developer mode first (catches code issues)
./scripts/test-dev-install.sh

# 2. User mode (validates production path)
./scripts/test-user-install.sh

# 3. Docker (validates deployment packaging)
./scripts/test-docker.sh
```

### One-Liner (Stops on First Failure)

```bash
cd /path/to/CognivAgent
./scripts/test-dev-install.sh && ./scripts/test-user-install.sh && ./scripts/test-docker.sh
```

### With API Testing

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"

./scripts/test-dev-install.sh --with-api-test && \
./scripts/test-user-install.sh --with-api-test && \
./scripts/test-docker.sh --with-api-test
```

---

## Summary Table

| Question | Answer |
|----------|--------|
| **Where to run from?** | Project root (`/path/to/CognivAgent`) or anywhere with full path |
| **Need to activate venv?** | No — scripts create isolated environments |
| **Where are test files?** | `/tmp/cognivagent-*-test/` (auto-cleaned) |
| **Where are logs?** | `/tmp/cognivagent-*-test-server.log` (auto-cleaned) |
| **How to see results?** | Terminal output with color-coded PASS/FAIL |
| **What if test fails?** | Check terminal output, logs show last 30 lines |
| **Do tests modify my code?** | No — tests clone fresh repos to /tmp |
| **Can I run tests in parallel?** | No — they use the same port (8000) |

---

## Getting Help

```bash
./scripts/test-docker.sh --help
./scripts/test-user-install.sh --help
./scripts/test-dev-install.sh --help
```

Each script displays usage information and available options.
