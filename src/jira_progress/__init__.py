"""Jira progress reporter - generate Outcome/Feature progress reports with dependency graphs."""

from jira_progress.client import JiraClient
from jira_progress.pipeline import (
    OutcomeError,
    ProgressData,
    export_progress,
    extract_progress,
    fetch_outcome_tree,
    format_progress_report,
    synthesize_progress,
)
from jira_progress.slides import export_progress_to_pptx

__version__ = "0.1.0"

__all__ = [
    "JiraClient",
    "OutcomeError",
    "ProgressData",
    "export_progress",
    "export_progress_to_pptx",
    "extract_progress",
    "fetch_outcome_tree",
    "format_progress_report",
    "synthesize_progress",
]
