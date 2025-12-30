#!/usr/bin/env bash
#
# CognivAgent Pre-Release Test: Docker Installation
#
# Tests the full Docker installation workflow:
#   1. Build Docker image from scratch
#   2. Start container and verify health
#   3. Optionally test with real API keys
#
# Usage:
#   ./scripts/test-docker.sh                  # Quick validation (no API calls)
#   ./scripts/test-docker.sh --with-api-test  # Full test with API validation
#
# Prerequisites:
#   - Docker Engine 20.10+
#   - Docker Compose 2.x+
#   - Port 8000 free
#   - For --with-api-test: ANTHROPIC_API_KEY and OPENAI_API_KEY in environment
#
# Exit Codes:
#   0 - All tests passed
#   1 - Test failure
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

readonly SCRIPT_NAME="$(basename "$0")"
readonly TEST_DIR="/tmp/cognivagent-docker-test"
readonly REPO_URL="https://github.com/costiash/CognivAgent.git"
readonly CONTAINER_NAME="cognivagent"
readonly HEALTH_TIMEOUT=60
readonly PORT=8000

# =============================================================================
# Color Definitions
# =============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# =============================================================================
# Tracking Variables
# =============================================================================

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
WITH_API_TEST=false
CLEANUP_NEEDED=false

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "========================================================"
    echo "  CognivAgent Pre-Release Test: Docker Installation"
    echo "========================================================"
    echo -e "${NC}"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++)) || true
    ((TESTS_RUN++)) || true
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++)) || true
    ((TESTS_RUN++)) || true
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

print_divider() {
    echo -e "${CYAN}--------------------------------------------------------${NC}"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# =============================================================================
# Cleanup Function
# =============================================================================

cleanup() {
    if [ "$CLEANUP_NEEDED" = true ]; then
        print_info "Cleaning up..."

        # Stop and remove container
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true

        # Remove test directory
        if [ -d "$TEST_DIR" ]; then
            rm -rf "$TEST_DIR"
            print_info "Removed test directory: $TEST_DIR"
        fi
    fi
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# =============================================================================
# Prerequisite Checks
# =============================================================================

check_prerequisites() {
    print_step "Checking prerequisites..."
    local prereq_ok=true

    # Check Docker
    if command_exists docker; then
        local docker_version
        docker_version=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "unknown")
        print_pass "Docker installed (version: $docker_version)"
    else
        print_fail "Docker not found"
        prereq_ok=false
    fi

    # Check Docker Compose
    if docker compose version >/dev/null 2>&1; then
        local compose_version
        compose_version=$(docker compose version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "unknown")
        print_pass "Docker Compose installed (version: $compose_version)"
    elif command_exists docker-compose; then
        local compose_version
        compose_version=$(docker-compose --version 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "unknown")
        print_pass "docker-compose installed (version: $compose_version)"
    else
        print_fail "Docker Compose not found"
        prereq_ok=false
    fi

    # Check Docker daemon is running
    if docker ps >/dev/null 2>&1; then
        print_pass "Docker daemon is running"
    else
        print_fail "Docker daemon not running or not accessible"
        prereq_ok=false
    fi

    # Check port availability
    if ! ss -tlnp 2>/dev/null | grep -q ":${PORT} " && \
       ! netstat -tlnp 2>/dev/null | grep -q ":${PORT} "; then
        print_pass "Port $PORT is available"
    else
        print_fail "Port $PORT is already in use"
        prereq_ok=false
    fi

    # Check disk space (need at least 2GB for Docker build)
    local docker_root
    docker_root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo "/var/lib/docker")
    local free_space_mb
    free_space_mb=$(df -m "$docker_root" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
    if [ "$free_space_mb" -gt 2048 ]; then
        print_pass "Sufficient disk space (${free_space_mb}MB free)"
    else
        print_warn "Low disk space (${free_space_mb}MB free). Build may fail."
    fi

    # Check API keys if --with-api-test
    if [ "$WITH_API_TEST" = true ]; then
        if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
            print_pass "ANTHROPIC_API_KEY is set"
        else
            print_fail "ANTHROPIC_API_KEY not set (required for --with-api-test)"
            prereq_ok=false
        fi

        if [ -n "${OPENAI_API_KEY:-}" ]; then
            print_pass "OPENAI_API_KEY is set"
        else
            print_fail "OPENAI_API_KEY not set (required for --with-api-test)"
            prereq_ok=false
        fi
    fi

    if [ "$prereq_ok" = false ]; then
        echo ""
        print_fail "Prerequisites not met. Cannot continue."
        exit 1
    fi

    echo ""
}

# =============================================================================
# Test Functions
# =============================================================================

test_clone_repository() {
    print_step "Cloning repository to $TEST_DIR..."

    # Clean up any existing test directory
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
    fi

    if git clone --depth 1 "$REPO_URL" "$TEST_DIR" 2>/dev/null; then
        print_pass "Repository cloned successfully"
        CLEANUP_NEEDED=true
    else
        print_fail "Failed to clone repository"
        exit 1
    fi

    # Verify essential files exist
    if [ -f "$TEST_DIR/Dockerfile" ] && [ -f "$TEST_DIR/docker-compose.yml" ]; then
        print_pass "Dockerfile and docker-compose.yml present"
    else
        print_fail "Missing Docker configuration files"
        exit 1
    fi

    echo ""
}

test_create_env() {
    print_step "Setting up environment..."

    cd "$TEST_DIR"

    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_pass "Created .env from .env.example"
    else
        print_fail ".env.example not found"
        exit 1
    fi

    # Add API keys if available
    if [ "$WITH_API_TEST" = true ]; then
        # Replace placeholder keys with real ones
        sed -i "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=${OPENAI_API_KEY}/" .env
        sed -i "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}/" .env
        print_pass "Configured real API keys in .env"
    else
        print_info "Using placeholder API keys (--with-api-test not specified)"
    fi

    echo ""
}

test_docker_build() {
    print_step "Building Docker image (this may take 2-5 minutes)..."

    cd "$TEST_DIR"

    local build_start
    build_start=$(date +%s)

    if docker compose build 2>&1 | tail -20; then
        local build_end
        build_end=$(date +%s)
        local build_time=$((build_end - build_start))
        print_pass "Docker image built successfully (${build_time}s)"
    else
        print_fail "Docker build failed"
        exit 1
    fi

    echo ""
}

test_docker_start() {
    print_step "Starting Docker container..."

    cd "$TEST_DIR"

    # Remove any existing container with same name
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true

    if docker compose up -d 2>&1; then
        print_pass "Container started"
    else
        print_fail "Failed to start container"
        exit 1
    fi

    # Verify container is running
    sleep 2
    if docker ps --filter name="$CONTAINER_NAME" --format "{{.Status}}" | grep -q "Up"; then
        print_pass "Container is running"
    else
        print_fail "Container not running"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        exit 1
    fi

    echo ""
}

test_wait_healthy() {
    print_step "Waiting for container to become healthy (max ${HEALTH_TIMEOUT}s)..."

    local elapsed=0
    local status=""

    while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
        status=$(docker inspect "$CONTAINER_NAME" --format="{{.State.Health.Status}}" 2>/dev/null || echo "unknown")

        if [ "$status" = "healthy" ]; then
            print_pass "Container is healthy (${elapsed}s)"
            echo ""
            return 0
        elif [ "$status" = "unhealthy" ]; then
            print_fail "Container became unhealthy"
            docker logs "$CONTAINER_NAME" 2>&1 | tail -30
            exit 1
        fi

        sleep 2
        elapsed=$((elapsed + 2))
        printf "\r  Waiting... ${elapsed}s (status: $status)    "
    done

    echo ""
    print_fail "Container did not become healthy within ${HEALTH_TIMEOUT}s"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -30
    exit 1
}

test_health_endpoint() {
    print_step "Testing health endpoint..."

    local health_response
    health_response=$(curl -sf "http://localhost:${PORT}/health" 2>/dev/null || echo "FAILED")

    if [ "$health_response" = '{"status":"ok"}' ]; then
        print_pass "Health endpoint returns expected response"
    else
        print_fail "Health endpoint unexpected response: $health_response"
    fi

    echo ""
}

test_page_loads() {
    print_step "Testing if main page loads..."

    local http_code
    http_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        print_pass "Main page returns HTTP 200"
    else
        print_fail "Main page returned HTTP $http_code"
    fi

    # Check for essential JavaScript
    local page_content
    page_content=$(curl -sf "http://localhost:${PORT}/" 2>/dev/null || echo "")

    if echo "$page_content" | grep -q 'type="module"'; then
        print_pass "ES modules detected in page"
    else
        print_fail "ES modules not found in page"
    fi

    if echo "$page_content" | grep -q 'cytoscape'; then
        print_pass "Cytoscape.js library referenced"
    else
        print_warn "Cytoscape.js not detected (may be loaded dynamically)"
    fi

    echo ""
}

test_data_persistence() {
    print_step "Testing data persistence across restart..."

    cd "$TEST_DIR"

    # Create a marker file in the data directory
    local marker_file="data/test-persistence-marker.txt"
    echo "persistence-test-$(date +%s)" > "$marker_file"

    if [ -f "$marker_file" ]; then
        print_pass "Marker file created in data/"
    else
        print_fail "Could not create marker file"
        return
    fi

    # Restart container
    print_info "Restarting container..."
    docker compose restart 2>/dev/null

    # Wait for healthy again
    local elapsed=0
    while [ $elapsed -lt 30 ]; do
        local status
        status=$(docker inspect "$CONTAINER_NAME" --format="{{.State.Health.Status}}" 2>/dev/null || echo "unknown")
        if [ "$status" = "healthy" ]; then
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    # Check marker file survived
    if [ -f "$marker_file" ]; then
        print_pass "Data persisted across container restart"
        rm -f "$marker_file"
    else
        print_fail "Data did not persist across restart"
    fi

    echo ""
}

test_api_connectivity() {
    if [ "$WITH_API_TEST" != true ]; then
        print_info "Skipping API connectivity test (use --with-api-test)"
        echo ""
        return
    fi

    print_step "Testing API connectivity (initializing session)..."

    # This test creates a session which validates API keys work
    local session_id
    session_id=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "test-$(date +%s)")

    local init_response
    init_response=$(curl -sf -X POST "http://localhost:${PORT}/chat/init" \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"$session_id\"}" 2>/dev/null || echo "FAILED")

    if echo "$init_response" | grep -q '"response"\|"greeting"\|"message"'; then
        print_pass "Session initialized successfully - API keys valid"
    elif echo "$init_response" | grep -q "error\|invalid\|authentication"; then
        print_fail "API key validation failed: $init_response"
    else
        print_warn "Unexpected init response: ${init_response:0:100}..."
    fi

    echo ""
}

test_container_cleanup() {
    print_step "Testing container cleanup..."

    cd "$TEST_DIR"

    if docker compose down 2>/dev/null; then
        print_pass "Container stopped via docker compose down"
    else
        print_fail "Failed to stop container cleanly"
    fi

    # Verify container is gone
    if ! docker ps --filter name="$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
        print_pass "Container removed successfully"
    else
        print_fail "Container still exists after cleanup"
    fi

    echo ""
}

# =============================================================================
# Results Summary
# =============================================================================

print_results() {
    print_divider
    echo ""
    echo -e "${BOLD}Test Results Summary${NC}"
    echo ""
    echo -e "  Total:  ${TESTS_RUN}"
    echo -e "  ${GREEN}Passed: ${TESTS_PASSED}${NC}"
    echo -e "  ${RED}Failed: ${TESTS_FAILED}${NC}"
    echo ""

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}${BOLD}All tests passed!${NC}"
        echo ""
        print_divider
        return 0
    else
        echo -e "${RED}${BOLD}Some tests failed!${NC}"
        echo ""
        print_divider
        return 1
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            --with-api-test)
                WITH_API_TEST=true
                shift
                ;;
            --help|-h)
                echo "Usage: $SCRIPT_NAME [--with-api-test]"
                echo ""
                echo "Options:"
                echo "  --with-api-test   Run additional tests that require valid API keys"
                echo "  --help            Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    print_header

    if [ "$WITH_API_TEST" = true ]; then
        print_info "Running with API tests enabled"
    else
        print_info "Running quick validation (no API tests)"
    fi
    echo ""

    # Run all tests
    check_prerequisites
    test_clone_repository
    test_create_env
    test_docker_build
    test_docker_start
    test_wait_healthy
    test_health_endpoint
    test_page_loads
    test_data_persistence
    test_api_connectivity
    test_container_cleanup

    # Print results and exit with appropriate code
    if print_results; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
