"""Thin async Jira REST API client for structured data fetching."""

from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


class JiraClient:
    """Async Jira REST client using Bearer PAT auth (Data Center) or Basic auth (Cloud)."""

    def __init__(
        self,
        url: str,
        *,
        personal_token: str = "",
        username: str = "",
        api_token: str = "",
        max_concurrent: int = 3,
    ) -> None:
        self.base_url = url.rstrip("/")
        self._semaphore = asyncio.Semaphore(max_concurrent)
        headers: dict[str, str] = {"Accept": "application/json"}

        if personal_token:
            headers["Authorization"] = f"Bearer {personal_token}"
            self._auth = None
        else:
            self._auth = httpx.BasicAuth(username, api_token)

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            auth=self._auth,
            timeout=30.0,
        )

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        """Make an HTTP request with rate-limit retry and concurrency control."""
        async with self._semaphore:
            for attempt in range(MAX_RETRIES):
                resp = await self._client.request(method, url, **kwargs)
                if resp.status_code != 429:
                    return resp
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, int(retry_after))
                logger.warning(
                    "429 rate limited on %s, retrying in %.1fs (attempt %d/%d)",
                    url, delay, attempt + 1, MAX_RETRIES,
                )
                await asyncio.sleep(delay)
            return resp  # return last response even if still 429

    async def search(
        self,
        jql: str,
        fields: list[str] | None = None,
        max_results: int = 200,
    ) -> list[dict]:
        """Run a JQL search and return all matching issues, handling pagination."""
        all_issues: list[dict] = []
        start_at = 0
        page_size = min(max_results, 100)

        default_fields = [
            "summary", "status", "assignee", "priority",
            "created", "updated", "comment", "components", "issuetype",
        ]

        while True:
            params: dict[str, str | int] = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
                "fields": ",".join(fields or default_fields),
            }

            resp = await self._request("GET", "/rest/api/2/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            issues = data.get("issues", [])
            all_issues.extend(issues)

            if len(all_issues) >= data.get("total", 0) or len(all_issues) >= max_results:
                break
            start_at += len(issues)
            if not issues:
                break

        return all_issues[:max_results]

    async def add_comment(self, issue_key: str, body: str) -> dict:
        """Post a comment on a Jira issue. Returns the created comment."""
        resp = await self._request(
            "POST", f"/rest/api/2/issue/{issue_key}/comment",
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict:
        """Fetch a single issue by key."""
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        resp = await self._request("GET", f"/rest/api/2/issue/{issue_key}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_fields(self) -> list[dict]:
        """Fetch all field definitions from the Jira instance (for custom field ID discovery)."""
        resp = await self._request("GET", "/rest/api/2/field")
        resp.raise_for_status()
        return resp.json()

    async def get_issue_with_links(
        self, issue_key: str, fields: list[str] | None = None,
    ) -> dict:
        """Fetch an issue with issuelinks and common fields expanded."""
        default = [
            "summary", "status", "assignee", "priority", "issuetype",
            "project", "issuelinks", "components", "labels",
            "created", "updated", "comment",
        ]
        return await self.get_issue(issue_key, fields=fields or default)

    async def get_transitions(self, issue_key: str) -> list[dict]:
        """Get available status transitions for an issue."""
        resp = await self._request("GET", f"/rest/api/2/issue/{issue_key}/transitions")
        resp.raise_for_status()
        return resp.json().get("transitions", [])

    async def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """Transition an issue to a new status. Transition ID must come from get_transitions."""
        resp = await self._request(
            "POST", f"/rest/api/2/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
        )
        resp.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> JiraClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
