# Workflows Reference

Step-by-step checklists for common GPT-5.2 query workflows.

## Analyzing Code

Use this checklist for comprehensive code analysis:

### Pre-Analysis

- [ ] **Identify target files/directories**
  - Single file: `app/services/processor.py`
  - Module: `app/api/`
  - Entire codebase: `.` (use cautiously, may hit 2MB limit)

- [ ] **Choose focus areas** (default: `all`)
  - `security` - Vulnerability scanning, auth issues
  - `performance` - Bottlenecks, complexity analysis
  - `architecture` - Design patterns, coupling/cohesion
  - `testing` - Test coverage, reliability
  - `quality` - Readability, maintainability, best practices
  - `all` - Comprehensive analysis across all dimensions

- [ ] **Select analysis type** (default: `comprehensive`)
  - `quick` - Fast overview, high-level issues only
  - `comprehensive` - Balanced depth and breadth
  - `deep` - Maximum reasoning, exhaustive analysis

### Execution

- [ ] **Run gpt52_analyze.py**
  ```bash
  python .claude/skills/querying-gpt52/scripts/gpt52_analyze.py \
    --target "app/core/" \
    --focus-areas "security,performance" \
    --analysis-type comprehensive
  ```

### Review Findings

- [ ] **Review P0 (Critical) findings first**
  - Security vulnerabilities
  - Crash-inducing bugs
  - Data loss risks
  - Action: Fix immediately before deployment

- [ ] **Address P1 (High Priority) findings**
  - Significant quality issues
  - Major architectural flaws
  - Performance bottlenecks
  - Action: Schedule for current sprint

- [ ] **Evaluate P2 (Medium Priority) findings**
  - Code complexity issues
  - Test coverage gaps
  - Minor architectural improvements
  - Action: Add to backlog, address in next iteration

- [ ] **Consider P3 (Low Priority) findings**
  - Code style inconsistencies
  - Optional optimizations
  - Enhancement suggestions
  - Action: Consider for future improvements

## Fixing Bugs

Use this checklist for root-cause bug fixing:

### Preparation

- [ ] **Gather error information**
  - Error messages (exact text)
  - Stack traces (full output)
  - Reproduction steps
  - Expected vs. actual behavior

- [ ] **Identify affected files**
  - Where does the error occur?
  - What files are in the call chain?
  - Are there related files that might contribute?

- [ ] **Choose fix scope** (default: `root_cause`)
  - `root_cause` - Fix architectural flaw (recommended)
  - `minimal` - Smallest change to resolve issue
  - `comprehensive` - Fix and address related patterns

### Execution

- [ ] **Run gpt52_fix.py with detailed issue description**
  ```bash
  python .claude/skills/querying-gpt52/scripts/gpt52_fix.py \
    --target "app/core/session.py" \
    --issues "Race condition: KeyError in session cleanup when multiple tasks run simultaneously. Stack trace: ..." \
    --fix-scope root_cause
  ```

### Review Proposed Fix

- [ ] **Verify root cause analysis**
  - Does it explain WHY the bug exists?
  - Does it trace back to architectural design?
  - Does it avoid symptom-focused explanations?

- [ ] **Evaluate fix quality**
  - Addresses root cause (not symptoms)
  - Preserves existing behavior
  - Maintains type safety
  - Follows code style
  - Avoids try/catch around symptoms
  - Avoids scattered null checks
  - Avoids "just make it work" patches

- [ ] **Apply changes and test**
  - Implement the proposed fix
  - Run existing tests
  - Add regression test (from "Testing Recommendation" section)
  - Verify fix resolves the issue

## Council-Advice Integration

When using GPT-5.2 with the council-advice skill for multi-model validation:

### Setup

- [ ] **Run gpt52_analyze.py for Codex perspective**
  ```bash
  python .claude/skills/querying-gpt52/scripts/gpt52_analyze.py \
    --target "app/api/" \
    --focus-areas "architecture,quality" \
    --output-format json > codex_analysis.json
  ```

- [ ] **Use JSON output format** for programmatic parsing
  - `--output-format json` enables structured data
  - Output compatible with `opus_judge.py`

### Integration

- [ ] **Combine with Gemini analysis**
  - Run Gemini analyzer separately
  - Collect both perspectives

- [ ] **Run opus_judge.py to synthesize**
  ```bash
  python .claude/skills/council-advice/scripts/opus_judge.py \
    --codex-report codex_analysis.json \
    --gemini-report gemini_analysis.json \
    --output synthesis.md
  ```

- [ ] **Review synthesized judgment**
  - Consensus points (both models agree)
  - Divergent perspectives (valuable insights)
  - Recommended actions with priority

## General Query Best Practices

For ad-hoc queries using `gpt52_query.py`:

- [ ] **Formulate clear, specific questions**
  - Include context (language, framework, version)
  - Specify constraints (performance, compatibility)
  - Provide example code if relevant

- [ ] **Choose appropriate reasoning effort**
  - `none` or `low` - Simple factual questions
  - `medium` - Standard coding questions
  - `high` - Algorithm design, trade-off analysis
  - `xhigh` - Complex optimization, multi-step reasoning

- [ ] **Iterate on results**
  - If output is too general, add specifics to prompt
  - If output is too verbose, request concise summary
  - If unclear, ask for clarification or examples
