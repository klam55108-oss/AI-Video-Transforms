---
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(gh pr create:*), Bash(gh pr list:*), Read, Edit, Write, Glob, Grep, Task
description: Explore changes, update docs, commit, push, and create PR
argument-hint: [optional: specific focus area]
---

# Document and Ship Workflow

You are executing a comprehensive workflow to document recent changes and ship them via PR.

## Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Recent commits on this branch vs main: !`git log main..HEAD --oneline 2>/dev/null || echo "No commits ahead of main"`
- Changed files summary: !`git diff --stat`

## Your Task

Execute this workflow in order:

### Step 1: Explore and Understand Changes

Use the Task tool with `subagent_type='Explore'` to thoroughly analyze ALL modified files:
- Read each modified file completely
- Run `git diff` to see exactly what changed
- Understand the purpose and impact of each change
- Identify patterns and themes across changes

$ARGUMENTS

### Step 2: Update Project Documentation

For each relevant documentation file, you MUST:

1. **READ the file first** to understand its structure and formatting style
2. **ONLY THEN make updates** that perfectly fit the existing organization

Documentation files to consider:
- @README.md - Project overview, features table
- @FRONTEND.md - Frontend modules documentation
- @CLAUDE.md - Development guidelines, critical patterns
- @.claude/rules/ - Rule files (frontend.md, fastapi.md, config.md, etc.)

**Critical**: Match the exact formatting, table styles, code block patterns, and section organization of each file.

### Step 3: Commit with Conventional Commit Format

Create a commit following conventional commit format:
- Use appropriate type: `feat`, `fix`, `docs`, `refactor`, `chore`
- Include scope in parentheses if relevant: `feat(jobs):`, `fix(api):`
- Write a clear, descriptive message referencing the MAIN work done
- Use bullet points for detailed changes
- **DO NOT include any footer attributes** (no Co-Authored-By, no Generated with, etc.)

Example format:
```
feat(scope): short description of main change

- Detail point 1
- Detail point 2
- Detail point 3
```

### Step 4: Push to Origin

Push the current branch to origin:
```bash
git push origin <current-branch>
```

### Step 5: Create Pull Request

Create a PR to main with:
- **Title**: Match the commit message subject line
- **Body**: Include:
  - Summary section with bullet points
  - Changes table organized by layer (Backend/Frontend/Documentation)
  - Test plan with checkbox items

Use this format:
```
## Summary
- Key change 1
- Key change 2

## Changes
| File | Change |
|------|--------|
| `path/to/file` | Description |

## Test plan
- [ ] Test item 1
- [ ] Test item 2
```

## Important Rules

- **Read before edit**: Never modify a doc without reading it first
- **Preserve formatting**: Match existing table styles, headers, code blocks
- **Focused commits**: Reference the MAIN work, not peripheral changes
- **No footers**: Do not add Co-Authored-By or similar attributes
- **Complete workflow**: Execute all 5 steps unless explicitly told otherwise
