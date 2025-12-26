# Gemini 3 Flash Capabilities Reference

Technical specifications and constraints for the Gemini 3 Flash querying skill.

## Model Specifications

| Specification | Value | Notes |
|--------------|-------|-------|
| Model ID | `gemini-3-flash-preview` | Currently in preview |
| Context Window | 1,000,000 tokens | ~750,000 words or ~3.75MB of code |
| Max Output | 64,000 tokens | ~48,000 words |
| Knowledge Cutoff | January 2025 | Current frameworks and best practices |
| API | Google Gen AI SDK | `google-genai` package |
| Pricing (Input) | $0.50/1M tokens | 75% cheaper than Pro |
| Pricing (Output) | $3.00/1M tokens | 75% cheaper than Pro |

## Thinking Levels

Gemini 3 Flash supports configurable thinking depth via the `thinking_level` parameter:

| Level | Use Case | Processing Time | Quality |
|-------|----------|-----------------|---------|
| `minimal` | Simple queries, high-throughput | Fastest | Standard Gemini 3 Flash |
| `low` | Code explanations, basic analysis | Fast | Light reasoning |
| `medium` | Code reviews, moderate debugging | Moderate | Balanced |
| `high` | Architecture analysis, security audits | Slower | Deep analysis (default) |

**Note:** Gemini 3 Flash has more granular thinking levels than Gemini 3 Pro (which only supports `low` and `high`).

**Default:** `high` for analyzer and fixer tools, `high` for general queries.

**Guidance:**
- Use `minimal` for straightforward questions and high-volume tasks
- Use `low` for standard code reviews
- Use `medium` for balanced analysis
- Use `high` for security audits, architecture analysis, and complex debugging

## Comparison: Gemini 3 Flash vs GPT-5.2

| Feature | Gemini 3 Flash | GPT-5.2 |
|---------|----------------|---------|
| Context Window | 1,000,000 tokens | 400,000 tokens |
| Max Output | 64,000 tokens | 128,000 tokens |
| Thinking Levels | minimal/low/medium/high | none/low/medium/high/xhigh |
| Input Pricing | $0.50/1M | Higher |
| Output Pricing | $3.00/1M | Higher |
| Speed | Faster | Slower |
| API | google-genai | OpenAI Responses API |

**When to use Gemini 3 Flash:**
- Larger codebases (leverage 1M context)
- Cost-sensitive analysis
- Speed-critical tasks
- When visual/spatial reasoning is needed

**When to use GPT-5.2:**
- Maximum output length needed (128K vs 64K)
- Extended reasoning with `xhigh` level
- OpenAI ecosystem integration

## File Collection Limits

### Size Limits
- **Per-file maximum:** 500KB
- **Total collection maximum:** 2MB
- Files exceeding limits are automatically excluded with warning

### Allowed File Extensions
```
.py .js .ts .jsx .tsx .java .c .cpp .h .hpp .cs .go .rs .rb .php
.swift .kt .scala .sh .bash .zsh .sql .md .json .yaml .yml .toml
.xml .html .css .scss .vue .svelte .astro
```

### Excluded Patterns
- `__pycache__/` directories
- `node_modules/` directories
- `.git/` directories
- `.env` files (security: prevents secret exposure)
- Binary files (images, videos, archives)
- Generated files (build artifacts, compiled code)

## Security Constraints

### Blocked System Paths
The following directories are blocked to prevent system modification:
- `/etc`
- `/usr`
- `/bin`
- `/sbin`
- `/var`
- `/root`

### Path Traversal Protection
- Paths must be relative to project root
- `..` (parent directory) patterns blocked
- Symbolic links validated to stay within project

### Environment File Exclusion
`.env` files are automatically excluded to prevent exposure of:
- API keys
- Database credentials
- Secret tokens
- Configuration secrets

## Analysis Dimensions

The analyzer evaluates code across six dimensions with P0-P3 prioritization:

### 1. Code Quality
- Readability and maintainability
- Language idioms and best practices
- Code complexity (cyclomatic, nesting depth)
- DRY principle violations
- Dead code detection

### 2. Architecture & Design
- Component alignment and cohesion
- Separation of concerns
- Dependency management and coupling
- Design pattern usage
- API design quality

### 3. Logical Flow
- Control flow correctness
- Edge case handling
- Error propagation paths
- State management consistency
- Race condition potential

### 4. Security
- Input validation gaps
- Injection vulnerabilities (SQL, command, XSS)
- Authentication/authorization issues
- Sensitive data exposure
- Dependency vulnerabilities

### 5. Performance
- Algorithmic complexity concerns
- Memory usage patterns
- I/O bottlenecks
- Caching opportunities
- N+1 query patterns

### 6. Testing & Reliability
- Test coverage gaps
- Error handling completeness
- Logging adequacy
- Graceful degradation

## Priority Levels (P0-P3)

| Priority | Severity | Description | Action Required |
|----------|----------|-------------|-----------------|
| **P0** | Critical | Bugs, security vulnerabilities, data loss risks | Fix immediately |
| **P1** | High | Significant quality issues, maintainability problems | Address soon |
| **P2** | Medium | Improvements that enhance codebase | Plan for next iteration |
| **P3** | Low | Nice-to-have improvements, minor suggestions | Consider for future |

## Fix Philosophy

### Core Principle: Root-Cause Fixes Only

**The fixer tool adheres to a strict philosophy:**
> "NO MONKEY PATCHES - fix at the SOURCE, not where symptoms appear"

### Good Fixes (Encouraged)
- Address architectural flaws that allowed the bug
- Fix validation at entry points, not every usage
- Correct the data model if the model is wrong
- Fix the abstraction if the abstraction is leaky

### Bad Fixes (Avoided)
- Adding try/catch around symptoms
- Null checks scattered everywhere
- Special-case handling that masks real issues
- "Just make it work" patches that add technical debt

### Fix Implementation Standards
- Preserve existing behavior except for the bug
- Maintain or improve type safety
- Add or update tests to prevent regression
- Follow existing code style and patterns
- Document WHY the fix works, not just WHAT it does

## Output Constraints

### Character Limits
- Maximum output: 100,000 characters
- Output exceeding limit is truncated with warning

### Output Formats

#### Markdown (Default)
- Human-readable formatting
- Code blocks with syntax highlighting
- Hierarchical sections
- Optimized for direct reading

#### JSON
- Structured data for programmatic parsing
- Includes metadata (model, timing, token usage)

## API Key Configuration

The skill accepts API keys via environment variables:

```bash
# Primary (preferred)
GEMINI_API_KEY=your-api-key

# Alternative
GOOGLE_API_KEY=your-api-key
```

Get an API key from [Google AI Studio](https://aistudio.google.com/apikey).
