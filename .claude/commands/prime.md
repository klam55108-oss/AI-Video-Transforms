---
description: Load project context into the context window for efficient onboarding
allowed-tools: Bash(git ls-files:*), Bash(find:*), Bash(ls:*), Bash(head:*), Bash(cat:*), Read, Glob, Grep
argument-hint: [focus-area]
---

# Prime: Project Context Loading

Load a comprehensive understanding of the codebase into context. Focus area (optional): $ARGUMENTS

## Project Files

All tracked files in the repository:

!`git ls-files`

## Core Documentation

### Claude Agent SDK Docs **HIGHLY IMPORTANT**
@ai_docs/claude_agent_sdk/01_OVERVIEW_QUICKSTART.md
@ai_docs/claude_agent_sdk/02_CORE_API_TOOLS.md
@ai_docs/claude_agent_sdk/03_SESSION_PERMISSIONS_HOSTING.md
@ai_docs/claude_agent_sdk/04_API_REFERENCE.md
@ai_docs/claude_agent_sdk/05_FILE_CHECKPOINTING.md

### README.md — Project Overview
@README.md

### CLAUDE.md — Development Guidelines
@CLAUDE.md

### FRONTEND.md — Frontend Architecture
@FRONTEND.md

### DOCKER.md — Deployment Instructions
@DOCKER.md

## Project Structure

### Source Layout
!`find app -type f -name "*.py" | head -60`

### Test Organization
!`find tests -type f -name "*.py" 2>/dev/null | head -30`

### Frontend Modules
!`find app/static/js -type f -name "*.js" 2>/dev/null | head -30`

## Architecture Quick Reference

### API Routers
!`ls -la app/api/routers/ 2>/dev/null`

### Core Modules
!`ls -la app/core/ 2>/dev/null`

### Services
!`ls -la app/services/ 2>/dev/null || echo "Services in app/core/"`

### Knowledge Graph Domain
!`ls -la app/kg/ 2>/dev/null`

### Agent/MCP Tools
!`ls -la app/agent/ 2>/dev/null`

## Configuration

### Settings Schema (first 50 lines)
!`head -50 app/core/config.py 2>/dev/null`

### Environment Example
!`cat .env.example 2>/dev/null || echo "No .env.example found"`

## Task

Based on the above context:

1. **Summarize** the project purpose and architecture in 2-3 sentences
2. **Identify** the key patterns (SessionActor, MCP tools, job queue, KG workflow)
3. **Note** any focus areas relevant to: $ARGUMENTS
4. **Be ready** to assist with development tasks using the established patterns
5. **Note:** Summarize loaded files rather than retaining full contents in context.

If a focus area was specified, prioritize understanding that area in depth.
