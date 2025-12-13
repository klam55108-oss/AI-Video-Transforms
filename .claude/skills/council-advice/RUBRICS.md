# Council Advice Evaluation Rubrics

Detailed evaluation criteria used by the Opus Judge to synthesize multi-model recommendations into actionable, stage-appropriate advice.

## Core Philosophy

> **"The right amount of complexity is the minimum needed for the current task."**

The Opus Judge exists to filter well-intentioned but inappropriate recommendations. Both Gemini and Codex are powerful models that may suggest sophisticated solutions. The judge's role is to ensure recommendations match the project's reality, not its theoretical ideal.

## Evaluation Framework

### Decision Matrix

For each recommendation, the judge assigns scores across six dimensions:

| Dimension | Weight | Score Range |
|-----------|--------|-------------|
| Stage Relevancy | 25% | 0-10 |
| Overkill Detection | 20% | 0-10 |
| Complexity Assessment | 20% | 0-10 |
| Engineering Appropriateness | 15% | 0-10 |
| Implementation Feasibility | 10% | 0-10 |
| Purpose Alignment | 10% | 0-10 |

**Decision Thresholds:**
- **Embrace**: Weighted score >= 7.0
- **Defer**: Weighted score 4.0-6.9
- **Reject**: Weighted score < 4.0

---

## Dimension 1: Stage Relevancy (25%)

### Scoring Guide

| Score | Description |
|-------|-------------|
| 10 | Perfect fit for current stage |
| 8-9 | Good fit with minor timing considerations |
| 6-7 | Acceptable but could wait |
| 4-5 | Better suited for next stage |
| 2-3 | Premature by 2+ stages |
| 0-1 | Completely inappropriate for stage |

### Stage-Specific Criteria

#### MVP (Minimum Viable Product)
**Priority**: Validate core hypothesis with minimum effort

| Accept | Reject |
|--------|--------|
| Core feature implementation | Comprehensive error handling |
| Basic happy-path flows | Edge case coverage |
| Simple, working solution | Performance optimization |
| Manual processes OK | Automation infrastructure |
| Hardcoded config OK | Dynamic configuration systems |

**Red Flags for MVP:**
- "Production-ready" anything
- "Scalable architecture"
- "Comprehensive test coverage"
- "Robust error handling"

#### PoC (Proof of Concept)
**Priority**: Prove technical feasibility

| Accept | Reject |
|--------|--------|
| Technical feasibility proof | User experience polish |
| Integration validation | Security hardening |
| Performance baseline | Monitoring infrastructure |
| Key risk mitigation | Documentation |

**Red Flags for PoC:**
- "User-friendly interface"
- "Security best practices"
- "Operational excellence"

#### Production
**Priority**: Reliability, security, maintainability

| Accept | Reject |
|--------|--------|
| Security hardening | Gold-plating features |
| Error handling | Speculative optimization |
| Monitoring & logging | Over-abstraction |
| Performance optimization | Technology experiments |
| Test coverage | Major rewrites |

**Red Flags for Production:**
- "While we're at it, let's also..."
- "Future-proofing for..."
- "Industry best practice X" (without clear benefit)

#### Maintenance
**Priority**: Stability, minimal disruption

| Accept | Reject |
|--------|--------|
| Bug fixes | Feature additions |
| Security patches | Refactoring |
| Documentation updates | Technology migrations |
| Performance tuning | Architecture changes |

**Red Flags for Maintenance:**
- "Modernize the codebase"
- "Upgrade to latest version"
- "Refactor for better..."

---

## Dimension 2: Overkill Detection (20%)

### Scoring Guide

| Score | Description |
|-------|-------------|
| 10 | Solution perfectly proportional to problem |
| 8-9 | Slight overhead, justified |
| 6-7 | Noticeable overhead, debatable value |
| 4-5 | Solution 2x problem complexity |
| 2-3 | Solution 5x+ problem complexity |
| 0-1 | Nuclear option for papercut |

### Overkill Indicators

**Architectural Overkill:**
- Microservices for single-user app
- Event sourcing for simple CRUD
- Kubernetes for hobby project
- Message queues for synchronous workflows

**Code Overkill:**
- Factory factories
- Multiple abstraction layers for single implementation
- Interface for every class
- Generic solutions for specific problems

**Process Overkill:**
- Full CI/CD for prototype
- Multi-environment setup for local-only app
- Enterprise security for internal tools
- SLA monitoring for experimental features

### Proportionality Check

Ask: "If I described this solution to someone unfamiliar with the problem, would they think it's reasonable?"

| Problem Size | Reasonable Solution |
|--------------|---------------------|
| 1 file change | 1 file change |
| 1 feature | 1-3 files, no new dependencies |
| 1 module | Up to 10 files, 1-2 new dependencies |
| System change | Bounded blast radius, clear migration |

---

## Dimension 3: Complexity Assessment (20%)

### Scoring Guide

| Score | Description |
|-------|-------------|
| 10 | Simplest possible solution |
| 8-9 | Minor complexity, clear value |
| 6-7 | Moderate complexity, justified |
| 4-5 | High complexity, questionable value |
| 2-3 | Very high complexity |
| 0-1 | Incomprehensible complexity |

### Complexity Metrics

**Cognitive Complexity:**
- How long to understand the solution?
- How many concepts must be learned?
- How many moving parts?

**Operational Complexity:**
- How many things can fail?
- How hard to debug?
- How many configurations needed?

**Maintenance Complexity:**
- How hard to modify later?
- How much tribal knowledge required?
- How fragile to changes elsewhere?

### Simplicity Preferences

| Prefer | Over |
|--------|------|
| Standard library | Third-party package |
| Built-in feature | Custom implementation |
| Explicit code | Clever abstractions |
| Copy-paste (2-3x) | Premature abstraction |
| Sequential flow | Callbacks/events |
| Synchronous | Asynchronous (unless necessary) |

---

## Dimension 4: Engineering Appropriateness (15%)

### Scoring Guide

| Score | Description |
|-------|-------------|
| 10 | Solves exactly what's needed |
| 8-9 | Solves need with minimal extras |
| 6-7 | Solves need with some speculation |
| 4-5 | Builds for hypothetical futures |
| 2-3 | Architecture astronautics |
| 0-1 | Solution looking for a problem |

### Over-Engineering Indicators

**YAGNI Violations:**
- "We might need this later"
- "What if we want to support X?"
- "This makes it easier to add Y in the future"
- "Industry standard approach"

**Abstraction Problems:**
- Interface with single implementation
- Generic type parameters used once
- Configuration for unchanging values
- Plugin system for fixed features

**Design Pattern Abuse:**
- Pattern name in class names (UserFactory, UserBuilder, UserStrategy)
- Patterns applied prophylactically
- Multiple patterns for simple problem

### Right-Sizing Guide

| Need | Right Size |
|------|------------|
| One implementation | Concrete class |
| Two implementations | Maybe interface |
| Three+ implementations | Definitely interface |
| Varying behavior | Strategy pattern |
| Unchanging behavior | Direct implementation |

---

## Dimension 5: Implementation Feasibility (10%)

### Scoring Guide

| Score | Description |
|-------|-------------|
| 10 | Can implement in current session |
| 8-9 | Can implement in a day |
| 6-7 | Can implement in a sprint |
| 4-5 | Requires significant planning |
| 2-3 | Requires team coordination |
| 0-1 | Major project/initiative |

### Feasibility Factors

**Resource Constraints:**
- Available time
- Team expertise
- Budget
- Infrastructure

**Technical Constraints:**
- Existing architecture compatibility
- Dependency availability
- Performance requirements
- Security requirements

**Risk Assessment:**
- Reversibility if it fails
- Impact on existing features
- Learning curve
- Operational burden

---

## Dimension 6: Purpose Alignment (10%)

### Scoring Guide

| Score | Description |
|-------|-------------|
| 10 | Directly advances core mission |
| 8-9 | Supports core mission |
| 6-7 | Tangentially related |
| 4-5 | Nice-to-have, not essential |
| 2-3 | Distraction from mission |
| 0-1 | Counter to project goals |

### Alignment Questions

1. Does this help solve the user's core problem?
2. Does this make the product better at its main job?
3. Would users notice/care about this?
4. Does this help the team ship faster?
5. Does this reduce risk to the core mission?

---

## Special Considerations

### When Advisors Agree

If both Gemini and Codex recommend the same thing:
- **Increase confidence** in the recommendation
- **Still apply rubrics** - consensus doesn't mean appropriate
- **Note agreement** in the report

### When Advisors Disagree

If Gemini and Codex conflict:
- **Analyze the disagreement** - what's the root cause?
- **Prefer the simpler option** when scores are close
- **Consider combining** if recommendations are complementary
- **Document the conflict** for user awareness

### Context Overrides

Some contexts override normal scoring:

| Context | Override |
|---------|----------|
| Security vulnerability | Prioritize fix regardless of stage |
| Data loss risk | Prioritize fix regardless of stage |
| Legal/compliance | Must address regardless of complexity |
| User safety | Must address regardless of cost |

---

## Example Evaluations

### Example 1: "Add comprehensive logging"

**Context**: MVP stage, single developer, local-only app

| Dimension | Score | Reasoning |
|-----------|-------|-----------|
| Stage Relevancy | 3 | Logging is production concern |
| Overkill | 4 | Comprehensive = overkill for MVP |
| Complexity | 5 | Adds infrastructure complexity |
| Engineering | 4 | Building for hypothetical debugging |
| Feasibility | 8 | Easy to implement |
| Alignment | 4 | Doesn't validate core hypothesis |

**Weighted Score**: 4.15 → **DEFER**

**Recommendation**: "Add basic print statements for now. Implement structured logging when moving to production."

### Example 2: "Add input validation"

**Context**: Production stage, user-facing API

| Dimension | Score | Reasoning |
|-----------|-------|-----------|
| Stage Relevancy | 10 | Critical for production |
| Overkill | 9 | Proportional to security need |
| Complexity | 8 | Standard practice |
| Engineering | 9 | Solves real security need |
| Feasibility | 9 | Well-understood implementation |
| Alignment | 10 | Protects users and system |

**Weighted Score**: 9.25 → **EMBRACE**

**Recommendation**: "Implement comprehensive input validation using Pydantic models with custom validators."

### Example 3: "Migrate to microservices"

**Context**: PoC stage, 3-person team, proving concept

| Dimension | Score | Reasoning |
|-----------|-------|-----------|
| Stage Relevancy | 1 | Completely inappropriate for PoC |
| Overkill | 1 | Nuclear option |
| Complexity | 1 | Massive complexity increase |
| Engineering | 2 | Building for imagined scale |
| Feasibility | 2 | Would consume all resources |
| Alignment | 1 | Prevents proving concept |

**Weighted Score**: 1.25 → **REJECT**

**Recommendation**: "Reject microservices. Use modular monolith if any separation needed. Revisit only if/when scale actually demands it."
