---
name: council-advice
description: Multi-model AI council for actionable project advice. Leverages Gemini CLI MCP and GPT-5.1-Codex-Max MCP in parallel, then synthesizes through an Opus Judge for stage-appropriate, non-overkill recommendations. Use when seeking architectural guidance, code review synthesis, or implementation planning.
---

# Council Advice

A multi-model advisory council that provides actionable, stage-appropriate recommendations by combining perspectives from multiple AI models and filtering through rigorous evaluation rubrics.

## Architecture Overview

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    COUNCIL ADVICE FLOW                       │
                    └─────────────────────────────────────────────────────────────┘

                                         User Request
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                 PHASE 1: COUNCIL CONSULTATION                │
                    │                      (Parallel Execution)                    │
                    └─────────────────────────────────────────────────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         │                    │                    │
                         ▼                    ▼                    ▼
                ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
                │ GEMINI ADVISOR  │  │  CODEX ADVISOR  │  │ CONTEXT LOADER  │
                │                 │  │                 │  │                 │
                │ gemini_analyze  │  │ codex_analyzer  │  │ Read project    │
                │ gemini_query    │  │ codex_query     │  │ files & stage   │
                └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
                         │                    │                    │
                         └────────────────────┼────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                 PHASE 2: OPUS JUDGE DELIBERATION             │
                    │                   (Claude Opus 4.5 via API)                  │
                    └─────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
                         ┌─────────────────────────────────────────┐
                         │            EVALUATION RUBRICS           │
                         │                                         │
                         │  • Stage Relevancy (MVP/PoC/Prod)       │
                         │  • Overkill Detection                   │
                         │  • Over-complexity Assessment           │
                         │  • Over-engineering Detection           │
                         │  • Implementation Feasibility           │
                         │  • Project Purpose Alignment            │
                         └─────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                 PHASE 3: ACTIONABLE REPORT                   │
                    │                   (Implementation Plan)                      │
                    └─────────────────────────────────────────────────────────────┘
```

## How to Use

When the user asks for council advice on any topic:

1. **Clarify the request context** if not provided:
   - Project stage: MVP, PoC, Production, Maintenance
   - Purpose: What problem is being solved?
   - Constraints: Time, resources, technical limitations

2. **Execute Phase 1**: Call council members in parallel

3. **Execute Phase 2**: Run the Opus Judge script

4. **Present Phase 3**: Deliver the actionable report

## Phase 1: Council Consultation

Execute these MCP tool calls **in parallel** for maximum efficiency:

### Gemini Advisor
Use `mcp__gemini-cli__gemini_analyze` for code/architecture analysis or `mcp__gemini-cli__gemini_query` for general guidance.

**Prompt template for Gemini:**
```
You are the Gemini Advisor on a multi-model council. Analyze the following request and provide your expert recommendations.

REQUEST: {user_request}

CONTEXT:
- Project Stage: {stage}
- Project Purpose: {purpose}
- Technical Stack: {tech_stack}

Provide:
1. Your assessment of the situation
2. Specific recommendations (prioritized)
3. Potential risks or concerns
4. Alternative approaches if applicable

Be thorough but practical. Focus on actionable insights.
```

### Codex Advisor
Use `mcp__codex__codex_analyzer` for deep code analysis or `mcp__codex__codex_query` for high-reasoning guidance.

**Prompt template for Codex:**
```
You are the Codex Advisor on a multi-model council. Provide high-reasoning analysis for the following request.

REQUEST: {user_request}

CONTEXT:
- Project Stage: {stage}
- Project Purpose: {purpose}
- Technical Stack: {tech_stack}

Analyze with focus on:
1. Root-cause understanding of the problem
2. Architecture-level recommendations
3. Code quality implications
4. Security and performance considerations
5. Testing and maintainability impact

Provide depth and rigor in your analysis.
```

### Context Loader
Simultaneously read relevant project files to understand:
- Current implementation state
- Project structure
- Existing patterns and conventions

## Phase 2: Opus Judge Deliberation

After receiving council responses, execute the Opus Judge script:

```bash
python .claude/skills/council-advice/scripts/opus_judge.py \
  --gemini-response "$GEMINI_RESPONSE" \
  --codex-response "$CODEX_RESPONSE" \
  --project-stage "$PROJECT_STAGE" \
  --project-purpose "$PROJECT_PURPOSE" \
  --request "$ORIGINAL_REQUEST"
```

The Opus Judge:
1. **Receives** multi-model reviews
2. **Weights** recommendations against project context
3. **Applies** evaluation rubrics (see [RUBRICS.md](RUBRICS.md))
4. **Decides** what to embrace and what to disregard
5. **Produces** a synthesized, actionable report

### Opus Judge Evaluation Criteria

For each recommendation, the judge evaluates:

| Criterion | Accept If | Reject If |
|-----------|-----------|-----------|
| **Stage Relevancy** | Matches current stage needs | Premature optimization for stage |
| **Overkill Detection** | Proportional to problem | Solution exceeds problem scope |
| **Complexity** | Appropriate for team/project | Unnecessarily complex |
| **Engineering** | Solves actual need | Builds for hypothetical futures |
| **Feasibility** | Achievable with current resources | Requires unrealistic effort |
| **Purpose Alignment** | Advances project goals | Tangential to core mission |

## Phase 3: Actionable Report

The final output follows this structure for seamless conversion to implementation:

```markdown
# Council Advice Report

## Executive Summary
[2-3 sentences on the key recommendation]

## Project Context
- **Stage**: {stage}
- **Purpose**: {purpose}
- **Request**: {original_request}

## Recommendations

### Embraced (Implement These)

#### 1. [Recommendation Title]
- **Source**: Gemini/Codex/Both
- **Priority**: P0/P1/P2
- **Rationale**: Why this was embraced
- **Implementation Steps**:
  1. Step one
  2. Step two
  3. Step three
- **Estimated Effort**: [time estimate]

### Deferred (Not Now, Maybe Later)

#### 1. [Recommendation Title]
- **Source**: Gemini/Codex/Both
- **Reason for Deferral**: [Stage mismatch/Overkill/etc.]
- **Revisit When**: [Condition for reconsidering]

### Rejected (Do Not Implement)

#### 1. [Recommendation Title]
- **Source**: Gemini/Codex/Both
- **Rejection Reason**: [Over-engineered/Out of scope/etc.]

## Implementation Plan

### Immediate Actions (This Session)
- [ ] Action 1
- [ ] Action 2

### Short-term Actions (This Sprint)
- [ ] Action 1
- [ ] Action 2

### Future Considerations
- [ ] Consideration 1
- [ ] Consideration 2

## Council Notes
[Any areas of agreement/disagreement between advisors]
```

## Best Practices

### Parallel Execution
Always call Gemini and Codex tools **in parallel** when possible:
```
If you intend to call multiple tools and there are no dependencies between
the tool calls, make all of the independent tool calls in parallel.
```

### Stage-Appropriate Advice

| Stage | Prioritize | Avoid |
|-------|------------|-------|
| **MVP** | Speed, validation, core features | Optimization, scalability, edge cases |
| **PoC** | Proving concept, minimal viable | Production concerns, polish |
| **Production** | Reliability, security, performance | Technical debt shortcuts |
| **Maintenance** | Stability, documentation | Major rewrites |

### When to Use This Skill

- Seeking architectural guidance
- Planning feature implementation
- Code review synthesis
- Evaluating technical approaches
- Making technology decisions
- Refactoring strategy

### When NOT to Use This Skill

- Simple, straightforward tasks
- Emergency bug fixes (use direct tools)
- Documentation-only requests
- One-line code changes

## Troubleshooting

### MCP Tools Not Available
Ensure both MCP servers are configured in `.mcp.json`:
- `gemini-cli`: Gemini CLI wrapper
- `codex`: GPT-5.1-Codex-Max wrapper

### Opus Judge Script Fails
Check:
1. `ANTHROPIC_API_KEY` is set
2. Required packages installed (`anthropic>=0.50.0`)
3. Script has execute permissions

### Slow Response
- Council consultation runs in parallel (~30-60s)
- Opus Judge adds ~30-60s
- Total expected time: 1-2 minutes for comprehensive advice

## Related Documentation

- [RUBRICS.md](RUBRICS.md) - Detailed evaluation rubrics for the Opus Judge
- [Gemini MCP README](../../../mcp_servers/gemini/README.md)
- [Codex MCP README](../../../mcp_servers/codex/CODEX.md)
