#!/bin/bash
set -euo pipefail

# Claude Attribution Cleanup Hook (LOCAL ONLY - not committed to repo)
# Triggers on git push commands, cleans Co-Authored-By attributions from unpushed commits

# Read hook input from stdin
INPUT=$(cat)

# Extract tool name and command
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only process Bash tool with git push commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0  # Allow other tools
fi

if [[ ! "$COMMAND" =~ ^git\ push ]]; then
    exit 0  # Allow non-push commands
fi

# --- Git push detected, check for attributions ---

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
echo -e "${YELLOW}⚠️  Pre-Push Hook: Claude Attribution Check${NC}" >&2
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
echo "" >&2

# Count commits with attributions (only unpushed commits)
UPSTREAM=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo "")
if [[ -n "$UPSTREAM" ]]; then
    COUNT=$(git log "$UPSTREAM"..HEAD --grep="Co-Authored-By:" --oneline 2>/dev/null | wc -l | tr -d ' ')
    RANGE="$UPSTREAM..HEAD"
else
    COUNT=$(git log HEAD --grep="Co-Authored-By:" --oneline 2>/dev/null | wc -l | tr -d ' ')
    RANGE="HEAD"
fi

if [[ "$COUNT" -eq 0 ]]; then
    echo -e "${GREEN}✅ No Claude attributions in unpushed commits${NC}" >&2
    echo "" >&2
    exit 0  # Allow push
fi

echo -e "${YELLOW}Found $COUNT unpushed commit(s) with Claude attributions:${NC}" >&2
echo "" >&2
git log "$RANGE" --grep="Co-Authored-By:" --oneline 2>/dev/null | head -10 >&2
echo "" >&2

# Perform the cleanup automatically
echo -e "${CYAN}🔧 Cleaning attributions from commits...${NC}" >&2

# Create backup branch
BACKUP="backup-pre-clean-$(date +%Y%m%d-%H%M%S)"
git branch "$BACKUP" 2>/dev/null || true
echo -e "${GREEN}✅ Backup branch created: $BACKUP${NC}" >&2

# Run filter-branch to remove attributions
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --msg-filter '
    sed -e "/^Co-Authored-By:/d" \
        -e "/🤖 Generated with \[Claude Code\]/d" | \
    sed -e :a -e "/^\s*$/{\$d;N;ba" -e "}"
' -- "$RANGE" 2>&1 >&2 || {
    echo -e "${RED}❌ Filter-branch failed${NC}" >&2
    exit 0  # Allow push anyway, don't block on failure
}

# Clean up filter-branch refs
git for-each-ref --format="%(refname)" refs/original/ 2>/dev/null | xargs -r -n 1 git update-ref -d 2>/dev/null || true

echo "" >&2
echo -e "${GREEN}✅ Attributions cleaned! Push will proceed with clean commits.${NC}" >&2
echo -e "${CYAN}ℹ️  Backup branch: $BACKUP${NC}" >&2
echo "" >&2

# Allow the push to proceed with now-clean commits
exit 0
