"""Bounded ArticleMemory updates independent of persistence and LLMs."""

from __future__ import annotations

from dataclasses import dataclass

from apps.article_agent.domain import ArticleMemory, SectionDraft, SectionPlan


@dataclass(frozen=True, slots=True)
class MemoryBudget:
    max_items_per_field: int = 24
    max_summary_characters: int = 360


class MemoryUpdater:
    """Adds concise, deterministic memory facts and evicts oldest low-priority data."""

    def __init__(self, budget: MemoryBudget | None = None) -> None:
        self.budget = budget or MemoryBudget()

    def update(
        self,
        memory: ArticleMemory,
        section: SectionPlan,
        draft: SectionDraft,
        *,
        claims: list[str] | None = None,
        facts: list[str] | None = None,
        examples: list[str] | None = None,
        terms: list[str] | None = None,
        open_threads: list[str] | None = None,
    ) -> ArticleMemory:
        summary = self._summarize(draft.content)
        updated = ArticleMemory(
            covered_topics=[*memory.covered_topics, section.heading],
            section_summaries=[*memory.section_summaries, f"{section.heading}: {summary}"],
            important_facts=[*memory.important_facts, *(facts or [])],
            claims_made=[*memory.claims_made, *(claims or [])],
            examples_used=[*memory.examples_used, *(examples or [])],
            terms_introduced=[*memory.terms_introduced, *(terms or [])],
            avoid_repeating=[*memory.avoid_repeating, *section.key_points],
            style_notes=list(memory.style_notes),
            open_threads=[*memory.open_threads, *(open_threads or [])],
        ).normalized()
        return self._enforce_budget(updated)

    def _enforce_budget(self, memory: ArticleMemory) -> ArticleMemory:
        def bounded(items: list[str]) -> list[str]:
            return items[-self.budget.max_items_per_field :]

        return ArticleMemory(
            covered_topics=bounded(memory.covered_topics),
            section_summaries=bounded(memory.section_summaries),
            important_facts=bounded(memory.important_facts),
            claims_made=bounded(memory.claims_made),
            examples_used=bounded(memory.examples_used),
            terms_introduced=bounded(memory.terms_introduced),
            avoid_repeating=bounded(memory.avoid_repeating),
            style_notes=bounded(memory.style_notes),
            open_threads=bounded(memory.open_threads),
        )

    def _summarize(self, content: str) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= self.budget.max_summary_characters:
            return normalized
        return normalized[: self.budget.max_summary_characters - 1].rsplit(" ", 1)[0] + "…"
