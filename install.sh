#!/usr/bin/env bash
#
# CognivAgent Installation Script
# Interactive setup wizard for native Python (uv) or Docker deployment
#
# Usage: ./install.sh
#
# Requirements:
#   - curl or pip (for uv installation)
#   - bash 4.0+ (for associative arrays)
#

set -euo pipefail

# =============================================================================
# TTY Check for Interactive Input
# =============================================================================
# When piped from curl, stdin is consumed. We read from /dev/tty instead.
# This check ensures we're in an environment that supports interactive prompts.

if ! [ -t 0 ] && ! [ -e /dev/tty ]; then
    echo "ERROR: This installer requires an interactive terminal." >&2
    echo "Please run: ./install.sh (after downloading)" >&2
    exit 1
fi

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
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "========================================================"
    echo "         CognivAgent Setup Wizard                       "
    echo "========================================================"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_step() {
    echo -e "${CYAN}[>]${NC} $1"
}

print_divider() {
    echo -e "${CYAN}--------------------------------------------------------${NC}"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Repository URL
readonly REPO_URL="https://github.com/costiash/CognivAgent.git"
readonly REPO_NAME="CognivAgent"

# Get or create project root
# When piped from curl, we need to clone the repo first
# NOTE: All status messages go to stderr so only the path goes to stdout
get_project_root() {
    # Check if we're running from within the repo already
    if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" != "/dev/stdin" ] && [ -f "${BASH_SOURCE[0]}" ]; then
        cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
        return
    fi

    # Running from pipe - need to clone
    local install_dir="${PWD}/${REPO_NAME}"

    if [ -d "$install_dir" ]; then
        print_warning "Directory $REPO_NAME already exists." >&2
        read -rp "Remove and re-clone? [y/N]: " remove_choice < /dev/tty
        if [[ "$remove_choice" =~ ^[Yy]$ ]]; then
            rm -rf "$install_dir"
        else
            print_info "Using existing directory." >&2
            echo "$install_dir"
            return
        fi
    fi

    print_step "Cloning CognivAgent repository..." >&2
    if ! command_exists git; then
        print_error "git is required but not installed." >&2
        echo "Please install git and try again." >&2
        exit 1
    fi

    if git clone "$REPO_URL" "$install_dir" >&2; then
        print_success "Repository cloned to $install_dir" >&2
        echo "$install_dir"
    else
        print_error "Failed to clone repository" >&2
        exit 1
    fi
}

# =============================================================================
# System Dependencies Check
# =============================================================================

check_ffmpeg() {
    print_step "Checking for FFmpeg (required for transcription)..."

    if command_exists ffmpeg; then
        local ffmpeg_version
        ffmpeg_version=$(ffmpeg -version 2>&1 | head -1 | grep -oP '\d+\.\d+' | head -1 || echo "unknown")
        print_success "FFmpeg is installed (version: $ffmpeg_version)"
        return 0
    fi

    print_error "FFmpeg not found!"
    echo ""
    echo "  FFmpeg is required for video/audio transcription."
    echo ""
    echo "  Install with:"
    echo "    Ubuntu/Debian: sudo apt install ffmpeg"
    echo "    macOS:         brew install ffmpeg"
    echo "    Fedora:        sudo dnf install ffmpeg"
    echo "    Arch:          sudo pacman -S ffmpeg"
    echo ""
    print_warning "Continuing without FFmpeg - transcription will not work!"
    echo ""
    read -rp "Continue anyway? [y/N]: " continue_choice < /dev/tty
    if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
        exit 1
    fi
}

# =============================================================================
# UV Installation
# =============================================================================

check_uv() {
    print_step "Checking for uv package manager..."

    if command_exists uv; then
        local uv_version
        uv_version=$(uv --version 2>/dev/null || echo "unknown")
        print_success "uv is installed ($uv_version)"
        return 0
    fi

    print_warning "uv not found. Installing..."
    install_uv
}

install_uv() {
    # Try curl installation first (official method)
    if command_exists curl; then
        print_info "Installing uv via official installer..."
        if curl -LsSf https://astral.sh/uv/install.sh | sh; then
            # Source the new PATH
            export PATH="$HOME/.local/bin:$PATH"
            if command_exists uv; then
                print_success "uv installed successfully!"
                print_info "Note: Add this to your shell profile for persistence:"
                echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
                return 0
            fi
        fi
        print_warning "curl installation failed, trying pip..."
    fi

    # Fallback to pip
    if command_exists pip3; then
        print_info "Installing uv via pip3..."
        if pip3 install --user uv; then
            export PATH="$HOME/.local/bin:$PATH"
            if command_exists uv; then
                print_success "uv installed via pip3!"
                print_info "Note: Add this to your shell profile for persistence:"
                echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
                return 0
            fi
        fi
    elif command_exists pip; then
        print_info "Installing uv via pip..."
        if pip install --user uv; then
            export PATH="$HOME/.local/bin:$PATH"
            if command_exists uv; then
                print_success "uv installed via pip!"
                print_info "Note: Add this to your shell profile for persistence:"
                echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
                return 0
            fi
        fi
    fi

    print_error "Failed to install uv. Please install manually:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  OR"
    echo "  pip install uv"
    exit 1
}

# =============================================================================
# Docker Checks
# =============================================================================

check_docker() {
    print_step "Checking Docker installation..."

    local docker_ok=true

    if ! command_exists docker; then
        print_error "docker not found"
        docker_ok=false
    else
        local docker_version
        docker_version=$(docker --version 2>/dev/null || echo "unknown")
        print_success "docker is installed ($docker_version)"
    fi

    # Check for docker-compose (standalone) or docker compose (plugin)
    if command_exists docker-compose; then
        local compose_version
        compose_version=$(docker-compose --version 2>/dev/null || echo "unknown")
        print_success "docker-compose is installed ($compose_version)"
    elif docker compose version >/dev/null 2>&1; then
        local compose_version
        compose_version=$(docker compose version 2>/dev/null || echo "unknown")
        print_success "docker compose plugin is installed ($compose_version)"
    else
        print_error "docker-compose not found"
        docker_ok=false
    fi

    if [ "$docker_ok" = false ]; then
        print_error "Docker requirements not met. Please install Docker and docker-compose."
        echo ""
        echo "Installation guides:"
        echo "  Linux:  https://docs.docker.com/engine/install/"
        echo "  macOS:  https://docs.docker.com/desktop/install/mac-install/"
        echo "  WSL:    https://docs.docker.com/desktop/install/windows-install/"
        exit 1
    fi
}

# =============================================================================
# Directory Setup
# =============================================================================

setup_directories() {
    local project_root="$1"
    local mode="$2"  # "user" or "developer"

    print_step "Creating required directories..."

    # Always create these
    mkdir -p "$project_root/data"
    mkdir -p "$project_root/uploads"

    print_success "Created data/"
    print_success "Created uploads/"

    # Developer mode: extra directories
    if [ "$mode" = "developer" ]; then
        mkdir -p "$project_root/examples/demo"
        print_success "Created examples/demo/"
    fi
}

# =============================================================================
# Environment Setup
# =============================================================================

setup_env_file() {
    local project_root="$1"

    print_step "Setting up environment file..."

    if [ -f "$project_root/.env" ]; then
        print_warning ".env file already exists. Skipping copy."
        print_info "Review your .env file and ensure API keys are set."
    else
        if [ -f "$project_root/.env.example" ]; then
            cp "$project_root/.env.example" "$project_root/.env"
            print_success "Created .env from .env.example"
        else
            print_error ".env.example not found. Creating minimal .env..."
            cat > "$project_root/.env" << 'EOF'
# CognivAgent Environment Variables
# Fill in your API keys below

# Required: OpenAI API Key (for transcription)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Required: Anthropic API Key (for Claude Agent)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here
EOF
            print_success "Created minimal .env file"
        fi
    fi
}

# =============================================================================
# Native Python Installation
# =============================================================================

install_native() {
    local project_root="$1"

    # Check system dependencies for native installation
    check_ffmpeg

    print_divider
    echo ""
    echo -e "${BOLD}Select installation profile:${NC}"
    echo ""
    echo "  1) User (minimal) - Just the essentials to run the app"
    echo "  2) Developer (full) - Includes dev tools, linting, testing"
    echo ""

    local profile_choice
    read -rp "Enter choice [1/2]: " profile_choice < /dev/tty

    case "$profile_choice" in
        1)
            install_native_user "$project_root"
            ;;
        2)
            install_native_developer "$project_root"
            ;;
        *)
            print_warning "Invalid choice. Defaulting to User mode."
            install_native_user "$project_root"
            ;;
    esac
}

install_native_user() {
    local project_root="$1"

    print_divider
    print_info "Installing in User mode (minimal dependencies)..."
    echo ""

    cd "$project_root"

    # Sync without dev dependencies
    print_step "Installing Python dependencies (production only)..."
    if uv sync --no-dev; then
        print_success "Dependencies installed!"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi

    # Setup directories and env
    setup_directories "$project_root" "user"
    setup_env_file "$project_root"

    print_native_instructions "$project_root" "user"
}

install_native_developer() {
    local project_root="$1"

    print_divider
    print_info "Installing in Developer mode (full dependencies)..."
    echo ""

    cd "$project_root"

    # Sync all dependencies including dev
    print_step "Installing Python dependencies (including dev tools)..."
    if uv sync; then
        print_success "Dependencies installed!"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi

    # Setup directories and env
    setup_directories "$project_root" "developer"
    setup_env_file "$project_root"

    print_native_instructions "$project_root" "developer"
}

print_native_instructions() {
    local project_root="$1"
    local mode="$2"

    echo ""
    print_divider
    echo ""
    echo -e "${GREEN}${BOLD}Installation Complete!${NC}"
    echo ""
    echo -e "${BOLD}Next Steps:${NC}"
    echo ""
    echo "  1. Edit .env and add your API keys:"
    echo -e "     ${CYAN}nano $project_root/.env${NC}"
    echo ""
    echo "     Required keys:"
    echo "       - OPENAI_API_KEY=sk-..."
    echo "       - ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    echo "  2. Start the server:"
    echo -e "     ${CYAN}cd $project_root${NC}"
    echo -e "     ${CYAN}uv run python -m app.main${NC}"
    echo ""
    echo "  3. Open in your browser:"
    echo -e "     ${CYAN}http://127.0.0.1:8000${NC}"
    echo ""

    if [ "$mode" = "developer" ]; then
        echo -e "${BOLD}Developer Commands:${NC}"
        echo ""
        echo "  Run tests:       uv run pytest"
        echo "  Type check:      uv run mypy ."
        echo "  Lint:            uv run ruff check . && uv run ruff format ."
        echo ""
    fi

    print_divider
}

# =============================================================================
# Docker Installation
# =============================================================================

install_docker() {
    local project_root="$1"

    print_divider
    print_info "Setting up Docker deployment..."
    echo ""

    # Check Docker requirements
    check_docker

    cd "$project_root"

    # Setup env file
    setup_env_file "$project_root"

    # Create data directory for volume mount
    mkdir -p "$project_root/data"
    print_success "Created data/ directory for Docker volume"

    print_docker_instructions "$project_root"
}

print_docker_instructions() {
    local project_root="$1"

    echo ""
    print_divider
    echo ""
    echo -e "${GREEN}${BOLD}Docker Setup Complete!${NC}"
    echo ""
    echo -e "${BOLD}Next Steps:${NC}"
    echo ""
    echo "  1. Edit .env and add your API keys:"
    echo -e "     ${CYAN}nano $project_root/.env${NC}"
    echo ""
    echo "     Required keys:"
    echo "       - OPENAI_API_KEY=sk-..."
    echo "       - ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
    echo "  2. Build and start the container:"
    echo -e "     ${CYAN}cd $project_root${NC}"

    # Check which compose command is available
    if command_exists docker-compose; then
        echo -e "     ${CYAN}docker-compose up -d${NC}"
    else
        echo -e "     ${CYAN}docker compose up -d${NC}"
    fi
    echo ""
    echo "  3. Open in your browser:"
    echo -e "     ${CYAN}http://localhost:8000${NC}"
    echo ""
    echo -e "${BOLD}Useful Commands:${NC}"
    echo ""
    if command_exists docker-compose; then
        echo "  View logs:       docker-compose logs -f"
        echo "  Stop:            docker-compose down"
        echo "  Rebuild:         docker-compose up -d --build"
    else
        echo "  View logs:       docker compose logs -f"
        echo "  Stop:            docker compose down"
        echo "  Rebuild:         docker compose up -d --build"
    fi
    echo ""
    print_divider
}

# =============================================================================
# Main Script
# =============================================================================

main() {
    local project_root
    project_root="$(get_project_root)"

    # Print header
    print_header

    # Check/install uv first (needed for native option)
    check_uv

    echo ""
    print_divider
    echo ""
    echo -e "${BOLD}Select installation method:${NC}"
    echo ""
    echo "  1) Native Python (recommended for development)"
    echo "  2) Docker (recommended for production/easy setup)"
    echo ""

    local method_choice
    read -rp "Enter choice [1/2]: " method_choice < /dev/tty

    case "$method_choice" in
        1)
            install_native "$project_root"
            ;;
        2)
            install_docker "$project_root"
            ;;
        *)
            print_warning "Invalid choice. Defaulting to Native Python."
            install_native "$project_root"
            ;;
    esac

    echo ""
    echo -e "${GREEN}${BOLD}Happy coding!${NC}"
    echo ""
}

# Run main
main "$@"
