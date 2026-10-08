"""Configured HTTP research integration with source provenance validation."""

from __future__ import annotations

import os

import aiohttp

from apps.article_agent.domain import ArticlePlan, ResearchData


class HttpResearchProvider:
    """Adapter for an explicitly configured trusted research service.

    Expected response schema: facts/statistics/examples/claims/sources arrays
    and optional confidence. Sources must be canonical provider URLs.
    """

    def __init__(self, endpoint: str | None = None, api_key: str | None = None, timeout: int = 20) -> None:
        self.endpoint = endpoint or os.getenv("ARTICLE_AGENT_RESEARCH_URL", "")
        self.api_key = api_key or os.getenv("ARTICLE_AGENT_RESEARCH_API_KEY", "")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    async def research(self, plan: ArticlePlan) -> ResearchData:
        if not self.configured:
            raise RuntimeError("research provider is not configured")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"title": plan.title, "topic": plan.primary_topic, "keywords": plan.keywords, "language": plan.language}
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.endpoint, json=payload, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
        if not isinstance(data, dict) or not isinstance(data.get("sources", []), list):
            raise RuntimeError("research provider returned malformed data")
        sources = [source for source in data["sources"] if isinstance(source, str) and source.startswith(("https://", "http://"))]
        return ResearchData(
            facts=[item for item in data.get("facts", []) if isinstance(item, str)],
            statistics=[item for item in data.get("statistics", []) if isinstance(item, str)],
            examples=[item for item in data.get("examples", []) if isinstance(item, str)],
            claims=[item for item in data.get("claims", []) if isinstance(item, str)],
            sources=sources, confidence=data.get("confidence"), provider=self.endpoint,
            mode="optional", status="no_results" if not sources else "available",
        )
