"""Outcome progress pipeline: traverse Jira hierarchy, classify, report.

Given an RHAISTRAT Outcome key, walks the issue link graph to collect
STRATs (Features), their RFE precursors, and implementation tickets,
then produces a structured progress summary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from jira_progress.client import JiraClient

logger = logging.getLogger(__name__)

PROGRESS_OUTPUT_DIR = Path("progress")

IMPLEMENTATION_PROJECTS = frozenset({"RHOAIENG", "RHAIENG", "AIPCC", "PSAP", "INFERENG", "RHOAIUX"})

TRAVERSAL_LINK_TYPES = frozenset({
    "Blocks",
    "Cloners",
    "Depend",
    "Duplicate",
    "Incorporates",
    "Informs",
    "Related",
    "Triggers",
})

CF_COLOR_STATUS = "customfield_12320845"
CF_BLOCKED = "customfield_12316543"
CF_BLOCKED_REASON = "customfield_12316544"
CF_PARENT_LINK = "customfield_12313140"
CF_TARGET_VERSION = "customfield_12319940"
CF_STATUS_SUMMARY = "customfield_12320841"

PROGRESS_FIELDS = [
    "summary", "status", "assignee", "priority", "issuetype",
    "project", "issuelinks", "components", "labels",
    "created", "updated", "comment",
    CF_COLOR_STATUS, CF_BLOCKED, CF_BLOCKED_REASON, CF_TARGET_VERSION,
    CF_STATUS_SUMMARY, CF_PARENT_LINK,
]

_RELEASE_LABEL_RE = re.compile(r"^(\d+\.\d+)-(committed|candidate)$")
_TARGET_VERSION_RE = re.compile(r"^rhoai-(\d+\.\d+(?:\.\w+)?)$", re.IGNORECASE)


class OutcomeError(Exception):
    """Raised when the provided key is not a valid RHAISTRAT Outcome or Feature."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class OutcomeIssue(BaseModel):
    key: str
    summary: str
    status: str
    project: str
    issue_type: str
    assignee: str = "Unassigned"
    priority: str = ""
    components: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    created: date
    updated: date
    comment_count: int = 0
    color_status: str | None = None
    blocked: bool = False
    blocked_reason: str = ""
    recent_comments: list[str] = Field(default_factory=list)
    target_release: str | None = None
    release_commitment: str = "none"
    status_summary: str = ""


class OutcomeTree(BaseModel):
    outcome: OutcomeIssue
    strats: list[OutcomeIssue] = Field(default_factory=list)
    rfes: list[OutcomeIssue] = Field(default_factory=list)
    implementation: list[OutcomeIssue] = Field(default_factory=list)
    strat_rfe_map: dict[str, list[str]] = Field(default_factory=dict)
    strat_origin: dict[str, str] = Field(default_factory=dict)
    strat_links: list[StratLink] = Field(default_factory=list)
    strat_children: dict[str, list[OutcomeIssue]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class StratHealth(BaseModel):
    key: str
    summary: str
    status: str
    components: list[str] = Field(default_factory=list)
    color_status: str | None = None
    blocked: bool = False
    blocked_reason: str = ""
    recent_comments: list[str] = Field(default_factory=list)
    target_release: str | None = None
    release_commitment: str = "none"
    health: str = "unknown"
    health_justification: str = ""
    relationship: str = "child"
    status_summary: str = ""


class StratLink(BaseModel):
    """A directed relationship between two STRATs (or a STRAT and an external issue)."""
    source_key: str
    target_key: str
    link_description: str


class ProgressData(BaseModel):
    outcome_key: str
    outcome_summary: str
    outcome_status: str = ""
    rfe_status_counts: dict[str, int] = Field(default_factory=dict)
    strat_status_counts: dict[str, int] = Field(default_factory=dict)
    strat_health: list[StratHealth] = Field(default_factory=list)
    strat_by_release: dict[str, list[StratHealth]] = Field(default_factory=dict)
    strat_links: list[StratLink] = Field(default_factory=list)
    impl_counts: dict[str, dict[str, int]] = Field(default_factory=dict)
    strat_impl_map: dict[str, list[dict]] = Field(default_factory=dict)
    rfe_coverage_gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_issue(raw: dict) -> OutcomeIssue:
    """Parse a Jira REST API issue dict into an OutcomeIssue."""
    fields = raw.get("fields", {})

    assignee_data = fields.get("assignee")
    assignee = assignee_data.get("displayName", "Unassigned") if assignee_data else "Unassigned"

    priority_data = fields.get("priority")
    priority = priority_data.get("name", "") if priority_data else ""

    comment_data = fields.get("comment", {})
    comment_count = 0
    recent_comments: list[str] = []
    if isinstance(comment_data, dict):
        comment_count = comment_data.get("total", 0)
        for c in comment_data.get("comments", [])[-3:]:
            body = c.get("body", "")
            if body:
                recent_comments.append(body[:500])

    components = [c.get("name", "") for c in fields.get("components", [])]
    labels = fields.get("labels", []) or []

    project_data = fields.get("project", {})
    issuetype_data = fields.get("issuetype", {})

    color_status = _parse_custom_field_value(fields.get(CF_COLOR_STATUS))
    blocked = _parse_blocked(fields.get(CF_BLOCKED))
    blocked_reason = ""
    br_data = fields.get(CF_BLOCKED_REASON)
    if isinstance(br_data, str):
        blocked_reason = br_data
    elif isinstance(br_data, dict):
        blocked_reason = br_data.get("value", "") or ""

    target_release, release_commitment = _resolve_target_release(
        labels, fields.get(CF_TARGET_VERSION),
    )

    status_summary_raw = fields.get(CF_STATUS_SUMMARY)
    status_summary = ""
    if isinstance(status_summary_raw, str) and status_summary_raw.strip():
        status_summary = status_summary_raw.strip()[:500]

    return OutcomeIssue(
        key=raw["key"],
        summary=fields.get("summary", ""),
        status=fields.get("status", {}).get("name", "Unknown"),
        project=project_data.get("key", ""),
        issue_type=issuetype_data.get("name", ""),
        assignee=assignee,
        priority=priority,
        components=components,
        labels=labels,
        created=datetime.fromisoformat(fields["created"][:10]).date(),
        updated=datetime.fromisoformat(fields["updated"][:10]).date(),
        comment_count=comment_count,
        color_status=color_status,
        blocked=blocked,
        blocked_reason=blocked_reason,
        recent_comments=recent_comments,
        target_release=target_release,
        release_commitment=release_commitment,
        status_summary=status_summary,
    )


def _parse_custom_field_value(data: object) -> str | None:
    """Extract a string value from a custom field that may be dict, str, or None."""
    if data is None:
        return None
    if isinstance(data, str):
        return data or None
    if isinstance(data, dict):
        return data.get("value") or data.get("name") or None
    return None


def _parse_blocked(data: object) -> bool:
    """Parse a blocked custom field (may be bool, string, dict, or list)."""
    if isinstance(data, bool):
        return data
    if isinstance(data, str):
        return data.lower() in ("true", "yes")
    if isinstance(data, dict):
        val = data.get("value", "")
        return str(val).lower() in ("true", "yes")
    if isinstance(data, list):
        return any(
            str(item.get("value", "")).lower() in ("true", "yes")
            if isinstance(item, dict) else str(item).lower() in ("true", "yes")
            for item in data
        )
    return False


def _resolve_target_release(
    labels: list[str],
    target_versions_raw: object,
) -> tuple[str | None, str]:
    """Determine the target release and commitment level from labels and Target Version field.

    Returns (release_string, commitment) where commitment is "committed", "candidate", or "none".
    """
    label_release: str | None = None
    commitment = "none"
    for label in labels:
        m = _RELEASE_LABEL_RE.match(label)
        if m:
            label_release = m.group(1)
            commitment = m.group(2)
            break

    tv_release: str | None = None
    if isinstance(target_versions_raw, list):
        for item in target_versions_raw:
            name = item.get("name", "") if isinstance(item, dict) else str(item)
            m = _TARGET_VERSION_RE.match(name)
            if m:
                tv_release = m.group(1)
                break

    # Target Version is more specific (may include EA suffix), so prefer it when available
    release = tv_release or label_release
    if release:
        # Normalise e.g. "3.4.EA1" → "3.4-ea-1", "3.4" stays "3.4"
        release = re.sub(r"\.EA(\d+)$", r"-ea-\1", release, flags=re.IGNORECASE)
        release = release.lower()

    return release, commitment


def _compute_strat_health(issue: OutcomeIssue) -> tuple[str, str]:
    """Compute Green/Yellow/Red health status for a STRAT.

    Returns (health, justification). The justification includes the raw signal
    values (Color Status, Status Summary) so the reader can see what drove the
    health determination.
    """
    status_lower = issue.status.lower()

    def _append_signals(base: str) -> str:
        parts = [base]
        if issue.color_status:
            parts.append(f"Color Status: {issue.color_status}")
        if issue.status_summary:
            preview = issue.status_summary.replace("\r\n", " ").replace("\n", " ")[:120]
            parts.append(f'Status Summary: "{preview}"')
        return ". ".join(parts)

    if status_lower in ("closed", "done"):
        return "green", "Closed/delivered"
    if issue.blocked:
        reason = issue.blocked_reason or "no reason given"
        return "red", _append_signals(f"Blocked: {reason}")
    if issue.color_status and issue.color_status.lower() == "red":
        return "red", _append_signals("PM Color Status is Red")
    if status_lower == "new" and issue.release_commitment == "committed":
        return "red", _append_signals(f"Committed to {issue.target_release} but not started")
    if issue.color_status and issue.color_status.lower() == "yellow":
        return "yellow", _append_signals("PM Color Status is Yellow")
    if status_lower == "new" and issue.target_release:
        return "yellow", _append_signals(f"Targeted for {issue.target_release} but still in New")
    if status_lower in ("in progress", "in review", "review") and not issue.target_release:
        return "yellow", _append_signals("In Progress but no target release defined")
    if status_lower in ("in progress", "in review", "review"):
        return "green", _append_signals(f"On track for {issue.target_release}")
    return "unknown", _append_signals("No target release or health signals")


def _extract_linked_keys(raw_issue: dict, direction: str = "outward") -> list[str]:
    """Extract issue keys from issuelinks in the given direction.

    direction: "outward" for children, "inward" for parents/precursors.
    Only follows link types in TRAVERSAL_LINK_TYPES.
    """
    links = raw_issue.get("fields", {}).get("issuelinks", [])
    keys: list[str] = []
    for link in links:
        link_type_name = link.get("type", {}).get("name", "")
        if link_type_name not in TRAVERSAL_LINK_TYPES:
            continue
        linked = link.get(f"{direction}Issue")
        if linked:
            keys.append(linked["key"])
    return keys


def _extract_clone_keys(raw_issue: dict) -> list[str]:
    """Extract issue keys linked via Cloners/Duplicate relationships (RFE precursors)."""
    links = raw_issue.get("fields", {}).get("issuelinks", [])
    keys: list[str] = []
    for link in links:
        link_type_name = link.get("type", {}).get("name", "")
        if link_type_name.lower() in ("cloners", "duplicate", "clones"):
            for direction in ("inwardIssue", "outwardIssue"):
                linked = link.get(direction)
                if linked and linked["key"].startswith("RHAIRFE"):
                    keys.append(linked["key"])
    return keys


def _extract_strat_to_strat_links(
    raw_issues: list[dict],
    strat_keys: set[str],
) -> list[StratLink]:
    """Extract inter-STRAT dependency links from raw issue data.

    Scans issuelinks on each STRAT to find links to other known STRATs.
    Deduplicates bidirectional links so each relationship appears once.
    """
    links: list[StratLink] = []
    seen: set[tuple[str, ...]] = set()

    for raw in raw_issues:
        source_key = raw["key"]
        if source_key not in strat_keys:
            continue
        for link in raw.get("fields", {}).get("issuelinks", []):
            link_type = link.get("type", {})
            for direction, desc_key in [("outwardIssue", "outward"), ("inwardIssue", "inward")]:
                target = link.get(direction)
                if not target:
                    continue
                target_key = target["key"]
                if target_key not in strat_keys or target_key == source_key:
                    continue
                desc = link_type.get(desc_key, link_type.get("name", ""))
                dedup_key = (min(source_key, target_key), max(source_key, target_key),
                             link_type.get("name", ""))
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                links.append(StratLink(
                    source_key=source_key,
                    target_key=target_key,
                    link_description=desc,
                ))
    return links


def _build_strat_children_map(
    all_raws: list[dict],
    strat_keys: set[str],
    impl_keys: set[str],
) -> dict[str, list[OutcomeIssue]]:
    """Map each STRAT to its implementation child tickets via Parent Link ancestry.

    Walks each impl ticket's Parent Link chain upward until it hits a known STRAT
    key. Tickets that can't be traced to a STRAT are collected under "_unparented".
    """
    key_to_raw: dict[str, dict] = {r["key"]: r for r in all_raws}

    parent_of: dict[str, str] = {}
    for raw in all_raws:
        parent_val = raw.get("fields", {}).get(CF_PARENT_LINK)
        if isinstance(parent_val, str) and parent_val:
            parent_of[raw["key"]] = parent_val

    result: dict[str, list[OutcomeIssue]] = {k: [] for k in strat_keys}
    result["_unparented"] = []

    for raw in all_raws:
        key = raw["key"]
        if key not in impl_keys:
            continue
        issue = _parse_issue(raw)
        ancestor = _find_strat_ancestor(key, parent_of, strat_keys)
        result[ancestor].append(issue)

    empty_keys = [k for k, v in result.items() if not v and k != "_unparented"]
    for k in empty_keys:
        pass  # keep empty lists to show STRATs with 0 children

    return result


def _find_strat_ancestor(
    key: str,
    parent_of: dict[str, str],
    strat_keys: set[str],
    max_depth: int = 10,
) -> str:
    """Walk up the Parent Link chain from *key* to find the owning STRAT."""
    current = key
    for _ in range(max_depth):
        parent = parent_of.get(current)
        if not parent:
            return "_unparented"
        if parent in strat_keys:
            return parent
        current = parent
    return "_unparented"


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


def _classify_issue(
    issue: OutcomeIssue,
    strats: list[OutcomeIssue],
    rfes: list[OutcomeIssue],
    implementation: list[OutcomeIssue],
    strat_keys: set[str],
    rfe_keys: set[str],
    impl_keys: set[str],
) -> None:
    """Classify an issue into the right bucket (mutates lists in place)."""
    if issue.project == "RHAISTRAT" and issue.issue_type == "Feature":
        if issue.key not in strat_keys:
            strats.append(issue)
            strat_keys.add(issue.key)
    elif issue.project == "RHAIRFE":
        if issue.key not in rfe_keys:
            rfes.append(issue)
            rfe_keys.add(issue.key)
    elif issue.project in IMPLEMENTATION_PROJECTS:
        if issue.key not in impl_keys:
            implementation.append(issue)
            impl_keys.add(issue.key)


async def fetch_outcome_tree(client: JiraClient, root_key: str) -> OutcomeTree:
    """Walk the Jira hierarchy from an Outcome or STRAT to build the issue tree.

    Accepts either:
    - An **Outcome** (RHAISTRAT issue_type=Outcome): discovers child STRATs,
      RFEs, and implementation tickets.
    - A **Feature/STRAT** (RHAISTRAT issue_type=Feature): treats the STRAT
      itself as both root and the sole STRAT, discovers its implementation
      children.

    Uses two complementary mechanisms:
    1. **childIssuesOf()** JQL — the Jira hierarchy (Parent Link field).
    2. **issuelinks** — explicit links (Depend, Related, Blocks).
    """
    raw_root = await client.get_issue_with_links(root_key, fields=PROGRESS_FIELDS)
    root_issue = _parse_issue(raw_root)

    is_strat_entry = (
        root_issue.project == "RHAISTRAT"
        and root_issue.issue_type == "Feature"
    )
    if root_issue.issue_type != "Outcome" and not is_strat_entry:
        raise OutcomeError(
            f"{root_key} is a {root_issue.issue_type!r} in {root_issue.project}, "
            f"not an Outcome or Feature. Aborting."
        )

    warnings: list[str] = []
    strats: list[OutcomeIssue] = []
    rfes: list[OutcomeIssue] = []
    implementation: list[OutcomeIssue] = []
    strat_keys: set[str] = set()
    rfe_keys: set[str] = set()
    impl_keys: set[str] = set()
    strat_origin: dict[str, str] = {}

    # When the root is a STRAT, add it as the sole STRAT up front
    if is_strat_entry:
        strats.append(root_issue)
        strat_keys.add(root_key)
        strat_origin[root_key] = "self"

    # --- Primary: Jira hierarchy via childIssuesOf() ---
    jql = f'issue in childIssuesOf("{root_key}") ORDER BY key ASC'
    try:
        child_issues = await client.search(jql, fields=PROGRESS_FIELDS, max_results=500)
        logger.info("%s: childIssuesOf returned %d issues", root_key, len(child_issues))
    except Exception:
        logger.warning("childIssuesOf() failed for %s, falling back to links only", root_key)
        child_issues = []

    for raw in child_issues:
        issue = _parse_issue(raw)
        if issue.project == "RHAISTRAT" and issue.issue_type == "Feature":
            strat_origin.setdefault(issue.key, "child")
        _classify_issue(issue, strats, rfes, implementation, strat_keys, rfe_keys, impl_keys)

    # --- Secondary: issuelinks on the root itself ---
    root_links = raw_root.get("fields", {}).get("issuelinks", [])
    root_link_descriptions: dict[str, str] = {}
    for link in root_links:
        link_type = link.get("type", {})
        for direction, desc_key in [("outwardIssue", "outward"), ("inwardIssue", "inward")]:
            target = link.get(direction)
            if target:
                desc = link_type.get(desc_key, link_type.get("name", ""))
                root_link_descriptions[target["key"]] = desc

    link_keys_out = _extract_linked_keys(raw_root, "outward")
    link_keys_in = _extract_linked_keys(raw_root, "inward")
    all_link_keys = set(link_keys_out + link_keys_in)
    unseen_link_keys = all_link_keys - strat_keys - rfe_keys - impl_keys - {root_key}

    fetched_linked_raws: list[dict] = []
    if unseen_link_keys:
        raw_linked = await asyncio.gather(
            *[client.get_issue_with_links(k, fields=PROGRESS_FIELDS) for k in unseen_link_keys]
        )
        for raw in raw_linked:
            issue = _parse_issue(raw)
            if issue.project == "RHAISTRAT" and issue.issue_type == "Feature":
                desc = root_link_descriptions.get(issue.key, "linked")
                strat_origin.setdefault(issue.key, f"linked: {desc}")
            _classify_issue(issue, strats, rfes, implementation, strat_keys, rfe_keys, impl_keys)
            fetched_linked_raws.append(raw)

    if not strats and not rfes and not implementation:
        warnings.append(f"No child or linked issues found for {root_key}")

    logger.info(
        "%s: %d STRATs, %d RFEs, %d implementation",
        root_key, len(strats), len(rfes), len(implementation),
    )

    # --- Build strat_rfe_map and inter-STRAT links ---
    # Include root + hierarchy children + fetched linked issues for full coverage
    all_raws: list[dict] = child_issues + fetched_linked_raws
    if is_strat_entry:
        all_raws = [raw_root] + all_raws
    strat_rfe_map: dict[str, list[str]] = {}
    strat_raws = [r for r in all_raws if r["key"] in strat_keys]
    for raw in strat_raws:
        clone_keys = _extract_clone_keys(raw)
        strat_rfe_map[raw["key"]] = clone_keys

    strat_links = _extract_strat_to_strat_links(all_raws, strat_keys)

    # --- Build strat_children: map each STRAT to its implementation tickets ---
    strat_children = _build_strat_children_map(all_raws, strat_keys, impl_keys)

    return OutcomeTree(
        outcome=root_issue,
        strats=strats,
        rfes=rfes,
        implementation=implementation,
        strat_rfe_map=strat_rfe_map,
        strat_origin=strat_origin,
        strat_links=strat_links,
        strat_children=strat_children,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Progress extraction (pure Python, no API calls)
# ---------------------------------------------------------------------------


def extract_progress(tree: OutcomeTree) -> ProgressData:
    """Extract structured progress data from an OutcomeTree."""
    rfe_status_counts: dict[str, int] = {}
    for rfe in tree.rfes:
        rfe_status_counts[rfe.status] = rfe_status_counts.get(rfe.status, 0) + 1

    strat_status_counts: dict[str, int] = {}
    strat_health: list[StratHealth] = []
    strat_by_release: dict[str, list[StratHealth]] = {}

    for strat in tree.strats:
        strat_status_counts[strat.status] = strat_status_counts.get(strat.status, 0) + 1

        health, justification = _compute_strat_health(strat)
        relationship = tree.strat_origin.get(strat.key, "child")
        sh = StratHealth(
            key=strat.key,
            summary=strat.summary,
            status=strat.status,
            components=strat.components,
            color_status=strat.color_status,
            blocked=strat.blocked,
            blocked_reason=strat.blocked_reason,
            recent_comments=strat.recent_comments,
            target_release=strat.target_release,
            release_commitment=strat.release_commitment,
            health=health,
            health_justification=justification,
            relationship=relationship,
            status_summary=strat.status_summary,
        )
        strat_health.append(sh)

        release_bucket = strat.target_release or "Unplanned"
        strat_by_release.setdefault(release_bucket, []).append(sh)

    impl_counts: dict[str, dict[str, int]] = {}
    for impl in tree.implementation:
        project_counts = impl_counts.setdefault(impl.project, {})
        category = _status_to_category(impl.status)
        project_counts[category] = project_counts.get(category, 0) + 1

    rfe_coverage_gaps = _find_rfe_coverage_gaps(tree)

    strat_impl_map: dict[str, list[dict]] = {}
    for strat_key, children in tree.strat_children.items():
        strat_impl_map[strat_key] = [
            {"key": c.key, "summary": c.summary, "status": c.status, "project": c.project}
            for c in children
        ]

    return ProgressData(
        outcome_key=tree.outcome.key,
        outcome_summary=tree.outcome.summary,
        outcome_status=tree.outcome.status,
        rfe_status_counts=rfe_status_counts,
        strat_status_counts=strat_status_counts,
        strat_health=strat_health,
        strat_by_release=strat_by_release,
        strat_links=tree.strat_links,
        impl_counts=impl_counts,
        strat_impl_map=strat_impl_map,
        rfe_coverage_gaps=rfe_coverage_gaps,
        warnings=tree.warnings,
    )


def _find_rfe_coverage_gaps(tree: OutcomeTree) -> list[str]:
    """Find approved RFEs that have no corresponding STRAT (coverage gap)."""
    rfe_keys_with_strats: set[str] = set()
    for rfe_keys in tree.strat_rfe_map.values():
        rfe_keys_with_strats.update(rfe_keys)

    gaps: list[str] = []
    for rfe in tree.rfes:
        if rfe.status.lower() == "approved" and rfe.key not in rfe_keys_with_strats:
            gaps.append(rfe.key)
    return gaps


def _status_to_category(status: str) -> str:
    """Map a Jira status name to a high-level category (To Do / In Progress / Done)."""
    status_lower = status.lower()
    if status_lower in ("closed", "done", "resolved", "release pending", "released"):
        return "Done"
    if status_lower in ("in progress", "in review", "review", "code review", "testing"):
        return "In Progress"
    return "To Do"


# ---------------------------------------------------------------------------
# Formatting (structured markdown, no LLM)
# ---------------------------------------------------------------------------


def _health_icon(health: str) -> str:
    """Return a text indicator for health status."""
    return {"green": "GREEN", "yellow": "YELLOW", "red": "RED"}.get(health, "UNKNOWN")


def format_progress_report(data: ProgressData) -> str:
    """Format ProgressData into a readable markdown report."""
    lines: list[str] = []

    lines.append(f"# Outcome Progress: {data.outcome_key}")
    lines.append(f"\n**{data.outcome_summary}** — Status: {data.outcome_status}\n")

    # --- Outcome Summary: all STRATs with relationships and health ---
    total_strats = sum(data.strat_status_counts.values())
    if data.strat_health:
        lines.append(f"## Outcome Summary ({total_strats} STRATs)\n")
        lines.append("| Key | Summary | Status | Health | Relationship | Target Release |")
        lines.append("|-----|---------|--------|--------|-------------|----------------|")
        for sh in data.strat_health:
            health_label = _health_icon(sh.health)
            target = sh.target_release or "—"
            lines.append(
                f"| {sh.key} | {sh.summary} | {sh.status} "
                f"| {health_label} | {sh.relationship} | {target} |"
            )
        lines.append("")

        if data.strat_links:
            lines.append("### Inter-STRAT Dependencies\n")
            for sl in data.strat_links:
                lines.append(f"- **{sl.source_key}** {sl.link_description} **{sl.target_key}**")
            lines.append("")

    # --- Per-STRAT health signals ---
    strats_with_signals = [
        sh for sh in data.strat_health
        if sh.color_status or sh.status_summary or sh.blocked
    ]
    if strats_with_signals:
        lines.append("### Health Signals\n")
        for sh in strats_with_signals:
            lines.append(f"**{sh.key}** ({sh.summary}):\n")
            lines.append(f"- Color Status: {sh.color_status or 'Not set'}")
            if sh.status_summary:
                preview = sh.status_summary.replace("\r\n", " ").replace("\n", " ")[:200]
                lines.append(f'- Status Summary: "{preview}"')
            blocked_str = f"Yes — {sh.blocked_reason}" if sh.blocked else "No"
            lines.append(f"- Blocked: {blocked_str}")
            if sh.target_release:
                lines.append(f"- Target Release: {sh.target_release} ({sh.release_commitment})")
            lines.append("")

    # --- STRATs status breakdown ---
    lines.append(f"## STRATs ({total_strats} total)\n")
    if data.strat_status_counts:
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        for status, count in sorted(data.strat_status_counts.items()):
            lines.append(f"| {status} | {count} |")
        lines.append("")

    # Release-grouped STRAT health table
    if data.strat_by_release:
        lines.append("## STRATs by Target Release\n")
        release_order = sorted(
            (k for k in data.strat_by_release if k != "Unplanned"),
        )
        if "Unplanned" in data.strat_by_release:
            release_order.append("Unplanned")

        for release in release_order:
            strats = data.strat_by_release[release]
            lines.append(f"### {release} ({len(strats)} STRATs)\n")
            lines.append("| Key | Summary | Status | Health | Justification |")
            lines.append("|-----|---------|--------|--------|---------------|")
            for sh in strats:
                health_label = _health_icon(sh.health)
                lines.append(
                    f"| {sh.key} | {sh.summary} | {sh.status} "
                    f"| {health_label} | {sh.health_justification} |"
                )
            lines.append("")

    # Blocked STRATs callout
    blocked_strats = [sh for sh in data.strat_health if sh.blocked]
    if blocked_strats:
        lines.append("### Blocked STRATs\n")
        for sh in blocked_strats:
            lines.append(f"- **{sh.key}** ({sh.summary}): {sh.blocked_reason}")
        lines.append("")

    # --- RFEs ---
    total_rfes = sum(data.rfe_status_counts.values())
    lines.append(f"## RFE Precursors ({total_rfes} total)\n")
    if data.rfe_status_counts:
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        for status, count in sorted(data.rfe_status_counts.items()):
            lines.append(f"| {status} | {count} |")
        lines.append("")

    if data.rfe_coverage_gaps:
        lines.append("### Coverage Gaps — Approved RFEs Without STRATs\n")
        for key in data.rfe_coverage_gaps:
            lines.append(f"- {key}")
        lines.append("")

    # --- Implementation ---
    total_impl = sum(
        sum(cats.values()) for cats in data.impl_counts.values()
    )
    lines.append(f"## Implementation Tickets ({total_impl} total)\n")
    if data.impl_counts:
        lines.append("| Project | To Do | In Progress | Done | Total |")
        lines.append("|---------|-------|-------------|------|-------|")
        for project in sorted(data.impl_counts):
            cats = data.impl_counts[project]
            todo = cats.get("To Do", 0)
            inprog = cats.get("In Progress", 0)
            done = cats.get("Done", 0)
            total = todo + inprog + done
            lines.append(f"| {project} | {todo} | {inprog} | {done} | {total} |")
        lines.append("")

    # --- Warnings ---
    if data.warnings:
        lines.append("## Warnings\n")
        for w in data.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------


async def synthesize_progress(
    data: ProgressData,
    structured_report: str,
    model: str,
) -> str:
    """Use an LLM to produce a narrative progress summary from structured data."""
    from pydantic_ai import Agent

    from jira_progress.prompts import format_progress_synthesis

    prompt = format_progress_synthesis(
        outcome_key=data.outcome_key,
        outcome_summary=data.outcome_summary,
        structured_report=structured_report,
        today=date.today(),
    )
    agent = Agent(model)
    result = await agent.run(prompt)
    return result.output if hasattr(result, "output") else str(result.data)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_progress(
    data: ProgressData,
    report: str,
    output_dir: Path = PROGRESS_OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Write progress results to JSON and markdown files. Returns (json_path, md_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    safe_key = data.outcome_key.replace("-", "_").lower()
    base_name = f"{today}_{safe_key}"

    json_path = output_dir / f"{base_name}.json"
    md_path = output_dir / f"{base_name}.md"

    export_data = {
        "date": today,
        "outcome_key": data.outcome_key,
        "outcome_summary": data.outcome_summary,
        "outcome_status": data.outcome_status,
        "rfe_status_counts": data.rfe_status_counts,
        "strat_status_counts": data.strat_status_counts,
        "strat_health": [sh.model_dump() for sh in data.strat_health],
        "strat_by_release": {
            release: [sh.model_dump() for sh in strats]
            for release, strats in data.strat_by_release.items()
        },
        "strat_links": [sl.model_dump() for sl in data.strat_links],
        "impl_counts": data.impl_counts,
        "strat_impl_map": data.strat_impl_map,
        "rfe_coverage_gaps": data.rfe_coverage_gaps,
        "warnings": data.warnings,
    }

    json_path.write_text(json.dumps(export_data, indent=2))
    md_path.write_text(report)

    logger.info("Exported progress to %s and %s", json_path, md_path)
    return json_path, md_path
