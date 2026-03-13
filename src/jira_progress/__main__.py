"""CLI entry point for jira-progress-reporter."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from jira_progress.client import JiraClient
from jira_progress.pipeline import (
    OutcomeError,
    export_progress,
    extract_progress,
    fetch_outcome_tree,
    format_progress_report,
    synthesize_progress,
)
from jira_progress.slides import export_progress_to_pptx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_env(key: str, required: bool = False) -> str:
    """Get environment variable, optionally raising if not set."""
    value = os.getenv(key, "")
    if required and not value:
        logger.error(f"Missing required environment variable: {key}")
        sys.exit(1)
    return value


async def main_async(issue_key: str, slides: bool, llm_synthesis: bool) -> None:
    """Run the progress report pipeline."""
    jira_url = get_env("JIRA_URL", required=True)
    personal_token = get_env("JIRA_PERSONAL_TOKEN")
    username = get_env("JIRA_USERNAME")
    api_token = get_env("JIRA_API_TOKEN")

    if not personal_token and not (username and api_token):
        logger.error(
            "Must provide either JIRA_PERSONAL_TOKEN (Data Center) or "
            "JIRA_USERNAME + JIRA_API_TOKEN (Cloud)"
        )
        sys.exit(1)

    model = get_env("MODEL") or "anthropic:claude-sonnet-4-6"

    logger.info("Fetching outcome tree for %s", issue_key)
    async with JiraClient(
        jira_url,
        personal_token=personal_token,
        username=username,
        api_token=api_token,
    ) as client:
        try:
            tree = await fetch_outcome_tree(client, issue_key)
        except OutcomeError as e:
            logger.error(str(e))
            sys.exit(1)

    logger.info("Extracting progress data")
    data = extract_progress(tree)

    logger.info("Formatting structured report")
    structured_report = format_progress_report(data)

    if llm_synthesis:
        logger.info("Synthesizing with LLM (%s)", model)
        final_report = await synthesize_progress(data, structured_report, model)
    else:
        final_report = structured_report

    logger.info("Exporting to progress/")
    json_path, md_path = export_progress(data, final_report)
    logger.info("Saved: %s", md_path)
    logger.info("Saved: %s", json_path)

    if slides:
        logger.info("Generating PowerPoint slides")
        pptx_path = export_progress_to_pptx(data)
        logger.info("Saved: %s", pptx_path)

    print(f"\n✓ Report generated: {md_path}")
    if slides:
        print(f"✓ Slides generated: {pptx_path}")


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Jira Outcome/Feature progress reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  jira-progress RHAISTRAT-26
  jira-progress RHAISTRAT-26 --slides
  jira-progress RHAISTRAT-26 --no-llm

Environment Variables:
  JIRA_URL                    Jira base URL (required)
  JIRA_PERSONAL_TOKEN         Personal access token (Data Center)
  JIRA_USERNAME               Username (Cloud)
  JIRA_API_TOKEN              API token (Cloud)
  MODEL                       LLM model (default: anthropic:claude-sonnet-4-6)
        """,
    )
    parser.add_argument("issue_key", help="Jira Outcome or Feature key (e.g., RHAISTRAT-26)")
    parser.add_argument(
        "--slides",
        action="store_true",
        help="Generate PowerPoint slides",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM synthesis (structured report only)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main_async(args.issue_key, args.slides, not args.no_llm))
    except KeyboardInterrupt:
        logger.info("Cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
