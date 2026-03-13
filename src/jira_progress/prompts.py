"""Prompt templates for the outcome progress pipeline."""

from __future__ import annotations

from datetime import date


def format_progress_synthesis(
    outcome_key: str,
    outcome_summary: str,
    structured_report: str,
    today: date,
) -> str:
    """Build the LLM prompt for synthesizing a narrative progress summary."""
    return f"""You are a senior engineering program manager writing a progress report.

Today is {today.isoformat()}.

Below is a structured progress report for **{outcome_key}** — "{outcome_summary}".

{structured_report}

Write a concise executive summary covering:

1. **Overall Health** — one paragraph summarising the Outcome's status, health distribution across STRATs, and whether it is on track.
2. **Release Readiness** — for each target release bucket, a one-line assessment (ON TRACK / AT RISK / BLOCKED).
3. **Key Findings** — 3-5 bullet points with the most important observations.
4. **Risks & Blockers** — any RED or blocked STRATs, missing target releases, or coverage gaps.
5. **Recommended Actions** — 3-5 concrete next steps, each one sentence.

Rules:
- Be specific: reference STRAT keys, release versions, and ticket counts.
- Use the health signals (Color Status, Status Summary, Blocked) to justify assessments.
- Do NOT invent information not present in the data.
- Keep the total length under 600 words.
- Use markdown formatting with headers and bullet points.
"""
