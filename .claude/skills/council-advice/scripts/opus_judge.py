#!/usr/bin/env python3
"""Opus Judge: Multi-model council synthesizer using Claude Opus 4.5.

This script receives recommendations from Gemini and Codex advisors,
applies evaluation rubrics, and produces a synthesized actionable report.

Usage:
    python opus_judge.py \
        --gemini-response "..." \
        --codex-response "..." \
        --project-stage "MVP" \
        --project-purpose "..." \
        --request "..."

Environment:
    ANTHROPIC_API_KEY: Required for Claude API access
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")

try:
    from anthropic import AsyncAnthropic  # type: ignore[import-untyped]
except ImportError:
    print("Error: anthropic package not installed. Run: uv add anthropic")
    sys.exit(1)


# Model configuration
OPUS_MODEL = "claude-opus-4-5-20251101"
MAX_TOKENS = 32768


def build_judge_prompt(
    gemini_response: str,
    codex_response: str,
    project_stage: str,
    project_purpose: str,
    original_request: str,
) -> str:
    """Build the comprehensive prompt for the Opus Judge."""
    return f"""You are the Head of the Council, known as the "Opus Judge". Your role is to synthesize recommendations from multiple AI advisors and produce actionable, stage-appropriate advice.

## Your Responsibilities

1. **Receive** multi-model reviews from the council
2. **Weight** recommendations against actual project context
3. **Apply** evaluation rubrics rigorously
4. **Decide** what to embrace, defer, or reject
5. **Produce** a clear, actionable implementation plan

## Evaluation Rubrics

For each recommendation, score across six dimensions (0-10 scale):

### 1. Stage Relevancy (25% weight)
- Does this match the current project stage needs?
- MVP: Focus on core validation, avoid optimization
- PoC: Focus on feasibility, avoid production concerns
- Production: Focus on reliability, security, performance
- Maintenance: Focus on stability, avoid disruption

### 2. Overkill Detection (20% weight)
- Is the solution proportional to the problem?
- Red flags: microservices for simple apps, enterprise patterns for prototypes

### 3. Complexity Assessment (20% weight)
- Is this the simplest solution that works?
- Prefer: standard library > third-party, explicit > clever, sequential > async

### 4. Engineering Appropriateness (15% weight)
- Does this solve actual needs, not hypothetical futures?
- Red flags: "we might need", "future-proofing", "industry standard"

### 5. Implementation Feasibility (10% weight)
- Can this be implemented with available resources?
- Consider time, expertise, infrastructure constraints

### 6. Purpose Alignment (10% weight)
- Does this advance the core mission?
- Would users notice/care about this change?

## Decision Thresholds

- **Embrace** (implement now): Weighted score >= 7.0
- **Defer** (later): Weighted score 4.0-6.9
- **Reject** (don't do): Weighted score < 4.0

## Context Overrides

Always prioritize regardless of scores:
- Security vulnerabilities
- Data loss risks
- Legal/compliance requirements
- User safety concerns

---

## Project Context

**Stage**: {project_stage}
**Purpose**: {project_purpose}
**Original Request**: {original_request}

---

## Council Recommendations

### Gemini Advisor Response:

{gemini_response}

### Codex Advisor Response:

{codex_response}

---

## Your Task

Analyze both advisor responses and produce a synthesized report in the following JSON structure:

```json
{{
  "executive_summary": "2-3 sentence summary of key recommendations",
  "project_context": {{
    "stage": "{project_stage}",
    "purpose": "{project_purpose}",
    "request": "{original_request}"
  }},
  "recommendations": {{
    "embraced": [
      {{
        "title": "Recommendation title",
        "source": "Gemini|Codex|Both",
        "priority": "P0|P1|P2",
        "scores": {{
          "stage_relevancy": 8,
          "overkill": 9,
          "complexity": 8,
          "engineering": 9,
          "feasibility": 9,
          "alignment": 10,
          "weighted_total": 8.7
        }},
        "rationale": "Why this was embraced",
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "estimated_effort": "Time estimate"
      }}
    ],
    "deferred": [
      {{
        "title": "Recommendation title",
        "source": "Gemini|Codex|Both",
        "scores": {{...}},
        "deferral_reason": "Why deferred",
        "revisit_when": "Condition for reconsidering"
      }}
    ],
    "rejected": [
      {{
        "title": "Recommendation title",
        "source": "Gemini|Codex|Both",
        "scores": {{...}},
        "rejection_reason": "Why rejected"
      }}
    ]
  }},
  "implementation_plan": {{
    "immediate_actions": ["Action 1", "Action 2"],
    "short_term_actions": ["Action 1", "Action 2"],
    "future_considerations": ["Consideration 1"]
  }},
  "council_notes": {{
    "advisor_agreement": ["Points where advisors agreed"],
    "advisor_disagreement": ["Points where advisors disagreed"],
    "synthesis_notes": "How conflicts were resolved"
  }}
}}
```

**Important Guidelines:**

1. Be ruthless about stage appropriateness - MVP doesn't need production patterns
2. Prefer simpler solutions when scores are close
3. If both advisors agree, still apply rubrics - consensus doesn't mean appropriate
4. Document your reasoning for each decision
5. Make implementation steps concrete and actionable
6. Identify quick wins (high value, low effort) as P0

Output ONLY the JSON, no additional text."""


async def call_opus_judge(
    gemini_response: str,
    codex_response: str,
    project_stage: str,
    project_purpose: str,
    original_request: str,
) -> dict[str, Any]:
    """Call Claude Opus 4.5 to synthesize council recommendations."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "error": "ANTHROPIC_API_KEY environment variable not set",
            "success": False,
        }

    client = AsyncAnthropic(api_key=api_key)

    prompt = build_judge_prompt(
        gemini_response=gemini_response,
        codex_response=codex_response,
        project_stage=project_stage,
        project_purpose=project_purpose,
        original_request=original_request,
    )

    try:
        # Use streaming for better UX on long responses
        full_response = ""
        async with client.messages.stream(
            model=OPUS_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                # Print progress indicator
                print(".", end="", flush=True, file=sys.stderr)

        print(file=sys.stderr)  # Newline after progress dots

        # Parse the JSON response
        # Handle potential markdown code blocks
        response_text = full_response.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        result = json.loads(response_text.strip())
        result["success"] = True
        return result

    except json.JSONDecodeError as e:
        return {
            "error": f"Failed to parse Opus Judge response as JSON: {e}",
            "raw_response": full_response,
            "success": False,
        }
    except Exception as e:
        return {
            "error": f"Opus Judge API call failed: {e}",
            "success": False,
        }


def format_report(judge_response: dict[str, Any]) -> str:
    """Format the judge response as a readable markdown report."""
    if not judge_response.get("success"):
        return f"""# Council Advice Report - ERROR

**Error**: {judge_response.get("error", "Unknown error")}

{judge_response.get("raw_response", "")}
"""

    report_parts = [
        "# Council Advice Report",
        "",
        "## Executive Summary",
        judge_response.get("executive_summary", "No summary available"),
        "",
        "## Project Context",
        f"- **Stage**: {judge_response.get('project_context', {}).get('stage', 'Unknown')}",
        f"- **Purpose**: {judge_response.get('project_context', {}).get('purpose', 'Unknown')}",
        f"- **Request**: {judge_response.get('project_context', {}).get('request', 'Unknown')}",
        "",
    ]

    recommendations = judge_response.get("recommendations", {})

    # Embraced recommendations
    embraced = recommendations.get("embraced", [])
    if embraced:
        report_parts.extend(["## Recommendations: Embrace (Implement These)", ""])
        for i, rec in enumerate(embraced, 1):
            scores = rec.get("scores", {})
            report_parts.extend(
                [
                    f"### {i}. {rec.get('title', 'Untitled')}",
                    f"- **Source**: {rec.get('source', 'Unknown')}",
                    f"- **Priority**: {rec.get('priority', 'P2')}",
                    f"- **Weighted Score**: {scores.get('weighted_total', 'N/A')}",
                    f"- **Rationale**: {rec.get('rationale', 'No rationale')}",
                    "",
                    "**Implementation Steps**:",
                ]
            )
            for step in rec.get("implementation_steps", []):
                report_parts.append(f"1. {step}")
            report_parts.extend(
                [
                    "",
                    f"**Estimated Effort**: {rec.get('estimated_effort', 'Unknown')}",
                    "",
                ]
            )

    # Deferred recommendations
    deferred = recommendations.get("deferred", [])
    if deferred:
        report_parts.extend(["## Recommendations: Defer (Not Now, Maybe Later)", ""])
        for i, rec in enumerate(deferred, 1):
            scores = rec.get("scores", {})
            report_parts.extend(
                [
                    f"### {i}. {rec.get('title', 'Untitled')}",
                    f"- **Source**: {rec.get('source', 'Unknown')}",
                    f"- **Weighted Score**: {scores.get('weighted_total', 'N/A')}",
                    f"- **Deferral Reason**: {rec.get('deferral_reason', 'No reason')}",
                    f"- **Revisit When**: {rec.get('revisit_when', 'Unknown')}",
                    "",
                ]
            )

    # Rejected recommendations
    rejected = recommendations.get("rejected", [])
    if rejected:
        report_parts.extend(["## Recommendations: Reject (Do Not Implement)", ""])
        for i, rec in enumerate(rejected, 1):
            scores = rec.get("scores", {})
            report_parts.extend(
                [
                    f"### {i}. {rec.get('title', 'Untitled')}",
                    f"- **Source**: {rec.get('source', 'Unknown')}",
                    f"- **Weighted Score**: {scores.get('weighted_total', 'N/A')}",
                    f"- **Rejection Reason**: {rec.get('rejection_reason', 'No reason')}",
                    "",
                ]
            )

    # Implementation plan
    impl_plan = judge_response.get("implementation_plan", {})
    report_parts.extend(["## Implementation Plan", ""])

    immediate = impl_plan.get("immediate_actions", [])
    if immediate:
        report_parts.append("### Immediate Actions (This Session)")
        for action in immediate:
            report_parts.append(f"- [ ] {action}")
        report_parts.append("")

    short_term = impl_plan.get("short_term_actions", [])
    if short_term:
        report_parts.append("### Short-term Actions (This Sprint)")
        for action in short_term:
            report_parts.append(f"- [ ] {action}")
        report_parts.append("")

    future = impl_plan.get("future_considerations", [])
    if future:
        report_parts.append("### Future Considerations")
        for consideration in future:
            report_parts.append(f"- [ ] {consideration}")
        report_parts.append("")

    # Council notes
    notes = judge_response.get("council_notes", {})
    report_parts.extend(["## Council Notes", ""])

    agreements = notes.get("advisor_agreement", [])
    if agreements:
        report_parts.append("**Areas of Agreement:**")
        for agreement in agreements:
            report_parts.append(f"- {agreement}")
        report_parts.append("")

    disagreements = notes.get("advisor_disagreement", [])
    if disagreements:
        report_parts.append("**Areas of Disagreement:**")
        for disagreement in disagreements:
            report_parts.append(f"- {disagreement}")
        report_parts.append("")

    synthesis = notes.get("synthesis_notes", "")
    if synthesis:
        report_parts.extend(
            [
                "**Synthesis Notes:**",
                synthesis,
                "",
            ]
        )

    return "\n".join(report_parts)


async def main() -> None:
    """Main entry point for the Opus Judge script."""
    parser = argparse.ArgumentParser(
        description="Opus Judge: Multi-model council synthesizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--gemini-response",
        required=True,
        help="Response from Gemini advisor",
    )
    parser.add_argument(
        "--codex-response",
        required=True,
        help="Response from Codex advisor",
    )
    parser.add_argument(
        "--project-stage",
        required=True,
        choices=["MVP", "PoC", "Production", "Maintenance"],
        help="Current project stage",
    )
    parser.add_argument(
        "--project-purpose",
        required=True,
        help="Project purpose/mission statement",
    )
    parser.add_argument(
        "--request",
        required=True,
        help="Original user request",
    )
    parser.add_argument(
        "--output-format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    args = parser.parse_args()

    print("Consulting the Opus Judge...", file=sys.stderr)

    result = await call_opus_judge(
        gemini_response=args.gemini_response,
        codex_response=args.codex_response,
        project_stage=args.project_stage,
        project_purpose=args.project_purpose,
        original_request=args.request,
    )

    if args.output_format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))


if __name__ == "__main__":
    asyncio.run(main())
