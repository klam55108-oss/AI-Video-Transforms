#!/usr/bin/env bash
#
# CognivAgent Pre-Release Test: User Mode Installation
#
# Tests the native Python installation for end users:
#   1. Clone fresh repo
#   2. Run install.sh with "Native Python" → "User (minimal)"
#   3. Verify directories and dependencies
#   4. Start server and check health
#   5. Optionally test with real API keys
#
# Usage:
#   ./scripts/test-user-install.sh                  # Quick validation (no API calls)
#   ./scripts/test-user-install.sh --with-api-test  # Full test with API validation
#
# Prerequisites:
#   - Python 3.11+
#   - FFmpeg 4.x+
#   - curl
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
readonly TEST_DIR="/tmp/cognivagent-user-test"
readonly REPO_URL="https://github.com/costiash/agent-video-to-data.git"
readonly HEALTH_TIMEOUT=30
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
SERVER_PID=""

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "========================================================"
    echo "  CognivAgent Pre-Release Test: User Mode Installation"
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

        # Stop server if running
        if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
            kill "$SERVER_PID" 2>/dev/null || true
            wait "$SERVER_PID" 2>/dev/null || true
            print_info "Stopped server (PID: $SERVER_PID)"
        fi

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

    # Check uv package manager (manages its own Python)
    # Note: uv will automatically download Python 3.11 if needed based on pyproject.toml
    export PATH="$HOME/.local/bin:$PATH"
    if command_exists uv; then
        local uv_version
        uv_version=$(uv --version 2>/dev/null || echo "unknown")
        print_pass "uv installed ($uv_version) - will manage Python 3.11"
    else
        print_info "uv not found - will be installed by install.sh"
    fi

    # Check FFmpeg (required for transcription, also checked by install.sh)
    if command_exists ffmpeg; then
        local ffmpeg_version
        ffmpeg_version=$(ffmpeg -version 2>&1 | head -1 | grep -oP '\d+\.\d+' | head -1 || echo "unknown")
        print_pass "FFmpeg installed (version: $ffmpeg_version)"
    else
        print_fail "FFmpeg not found (required for transcription)"
        print_info "Install with: sudo apt install ffmpeg"
        prereq_ok=false
    fi

    # Check curl
    if command_exists curl; then
        print_pass "curl is installed"
    else
        print_fail "curl not found"
        prereq_ok=false
    fi

    # Check git
    if command_exists git; then
        print_pass "git is installed"
    else
        print_fail "git not found"
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

    # Verify install.sh exists
    if [ -f "$TEST_DIR/install.sh" ]; then
        print_pass "install.sh present"
    else
        print_fail "install.sh not found"
        exit 1
    fi

    echo ""
}

test_install_script() {
    print_step "Running install.sh (User mode)..."

    cd "$TEST_DIR"
    chmod +x install.sh

    # CRITICAL: Unset VIRTUAL_ENV to prevent install.sh from using an external venv
    unset VIRTUAL_ENV

    # Run install.sh with automated input:
    # First choice: 1 (Native Python)
    # Second choice: 1 (User minimal)
    # Use printf to provide input, capture output
    local install_output
    if install_output=$(printf '1\n1\n' | ./install.sh 2>&1); then
        print_pass "install.sh completed successfully"
    else
        print_fail "install.sh failed"
        echo "$install_output" | tail -20
        exit 1
    fi

    # Check expected output messages
    if echo "$install_output" | grep -q "Installing Python dependencies"; then
        print_pass "Dependency installation message found"
    else
        print_warn "Expected installation message not found"
    fi

    if echo "$install_output" | grep -q "production only\|no-dev"; then
        print_pass "User mode (no-dev) confirmed in output"
    else
        print_warn "Could not confirm User mode from output"
    fi

    echo ""
}

test_directory_structure() {
    print_step "Verifying directory structure..."

    cd "$TEST_DIR"

    # Check required directories
    if [ -d "data" ]; then
        print_pass "data/ directory created"
    else
        print_fail "data/ directory missing"
    fi

    if [ -d "uploads" ]; then
        print_pass "uploads/ directory created"
    else
        print_fail "uploads/ directory missing"
    fi

    # In User mode, examples/demo should NOT exist
    if [ -d "examples/demo" ]; then
        print_fail "examples/demo/ exists (should only be in Developer mode)"
    else
        print_pass "examples/demo/ correctly absent (User mode)"
    fi

    # Check .env file
    if [ -f ".env" ]; then
        print_pass ".env file created"
    else
        print_fail ".env file missing"
    fi

    # Check .venv directory (created by uv)
    if [ -d ".venv" ]; then
        print_pass ".venv directory created"
    else
        print_fail ".venv directory missing"
    fi

    echo ""
}

test_no_dev_dependencies() {
    print_step "Verifying dev dependencies are NOT installed..."

    cd "$TEST_DIR"

    # Ensure uv is in PATH
    export PATH="$HOME/.local/bin:$PATH"

    # CRITICAL: Unset VIRTUAL_ENV to prevent uv from using an external venv
    unset VIRTUAL_ENV

    # Use the test project's venv Python directly to check for packages
    # This avoids any confusion with uv's project detection
    local venv_python="$TEST_DIR/.venv/bin/python"

    # pytest should NOT be available in User mode
    if "$venv_python" -m pytest --version >/dev/null 2>&1; then
        print_fail "pytest IS installed (should not be in User mode)"
    else
        print_pass "pytest correctly NOT installed (User mode)"
    fi

    # mypy should NOT be available in User mode
    if "$venv_python" -m mypy --version >/dev/null 2>&1; then
        print_fail "mypy IS installed (should not be in User mode)"
    else
        print_pass "mypy correctly NOT installed (User mode)"
    fi

    # ruff should NOT be available in User mode
    # Note: ruff is a standalone binary, check if it exists in venv/bin
    if [ -x "$TEST_DIR/.venv/bin/ruff" ]; then
        print_fail "ruff IS installed (should not be in User mode)"
    else
        print_pass "ruff correctly NOT installed (User mode)"
    fi

    echo ""
}

test_configure_api_keys() {
    print_step "Configuring API keys..."

    cd "$TEST_DIR"

    if [ "$WITH_API_TEST" = true ]; then
        # Replace placeholder keys with real ones
        sed -i "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=${OPENAI_API_KEY}/" .env
        sed -i "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}/" .env
        print_pass "Real API keys configured in .env"
    else
        print_info "Using placeholder API keys (--with-api-test not specified)"
    fi

    echo ""
}

test_start_server() {
    print_step "Starting server..."

    cd "$TEST_DIR"

    # Ensure uv is in PATH
    export PATH="$HOME/.local/bin:$PATH"

    # Start server in background
    uv run python -m app.main > /tmp/cognivagent-user-test-server.log 2>&1 &
    SERVER_PID=$!

    print_info "Server started with PID: $SERVER_PID"

    # Wait for server to start
    local elapsed=0
    while [ $elapsed -lt $HEALTH_TIMEOUT ]; do
        if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
            print_pass "Server started and responding (${elapsed}s)"
            echo ""
            return 0
        fi

        # Check if process is still running
        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            print_fail "Server process died"
            cat /tmp/cognivagent-user-test-server.log | tail -30
            exit 1
        fi

        sleep 1
        elapsed=$((elapsed + 1))
        printf "\r  Waiting for server... ${elapsed}s    "
    done

    echo ""
    print_fail "Server did not respond within ${HEALTH_TIMEOUT}s"
    cat /tmp/cognivagent-user-test-server.log | tail -30
    exit 1
}

test_health_endpoint() {
    print_step "Testing health endpoint..."

    local health_response
    health_response=$(curl -sf "http://127.0.0.1:${PORT}/health" 2>/dev/null || echo "FAILED")

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
    http_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        print_pass "Main page returns HTTP 200"
    else
        print_fail "Main page returned HTTP $http_code"
    fi

    # Check for essential elements
    local page_content
    page_content=$(curl -sf "http://127.0.0.1:${PORT}/" 2>/dev/null || echo "")

    if echo "$page_content" | grep -q 'CognivAgent\|cognivagent'; then
        print_pass "Page contains CognivAgent branding"
    else
        print_warn "CognivAgent branding not detected"
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

    local session_id
    session_id=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "test-$(date +%s)")

    local init_response
    init_response=$(curl -sf -X POST "http://127.0.0.1:${PORT}/chat/init" \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"$session_id\"}" 2>/dev/null || echo "FAILED")

    if echo "$init_response" | grep -q '"response"\|"greeting"\|"message"'; then
        print_pass "Session initialized successfully - API keys valid"
    elif echo "$init_response" | grep -q "error\|invalid\|authentication"; then
        print_fail "API key validation failed: ${init_response:0:200}"
    else
        print_warn "Unexpected init response: ${init_response:0:100}..."
    fi

    echo ""
}

test_stop_server() {
    print_step "Stopping server..."

    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
        print_pass "Server stopped gracefully"
        SERVER_PID=""
    else
        print_info "Server was not running"
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
    test_install_script
    test_directory_structure
    test_no_dev_dependencies
    test_configure_api_keys
    test_start_server
    test_health_endpoint
    test_page_loads
    test_api_connectivity
    test_stop_server

    # Print results and exit with appropriate code
    if print_results; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
