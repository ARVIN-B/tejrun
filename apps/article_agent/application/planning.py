"""Deterministic initial article planning with weighted word allocation."""

from __future__ import annotations

from dataclasses import dataclass

from apps.article_agent.domain import ArticlePlan, ArticleRequest, SectionPlan


@dataclass(frozen=True, slots=True)
class PlanningPolicy:
    body_budget_ratio: float = 0.78
    word_tolerance: float = 0.08


class ArticlePlanner:
    """Creates a valid plan while preserving the user's required headings."""

    def __init__(self, policy: PlanningPolicy | None = None) -> None:
        self.policy = policy or PlanningPolicy()

    def create_plan(self, request: ArticleRequest) -> ArticlePlan:
        allocations = self._allocate_words(request.word_count, len(request.headings))
        sections = [
            SectionPlan(
                index=index,
                heading=heading,
                purpose=self._section_purpose(index, len(request.headings), heading),
                key_points=[f"Explain the role of {heading} in relation to {request.title}."],
                target_words=allocation,
                minimum_words=max(1, int(allocation * 0.8)),
                maximum_words=max(1, int(allocation * 1.2)),
                must_include=[heading],
                must_avoid=["Repeat already covered concepts without adding new value."],
                dependencies=[index - 1] if index else [],
                research_requirements=[],
            )
            for index, (heading, allocation) in enumerate(zip(request.headings, allocations, strict=True))
        ]
        return ArticlePlan(
            title=request.title,
            goal=request.purpose,
            audience=request.audience,
            tone=request.tone,
            language=request.language,
            primary_topic=request.title,
            keywords=request.keywords,
            sections=sections,
            global_constraints=[
                "Preserve the user-provided heading intent.",
                "Prefer grounded, useful detail over filler.",
                "Do not fabricate sources or statistics.",
            ],
            coverage_requirements=request.headings,
        )

    def _allocate_words(self, target_words: int, section_count: int) -> list[int]:
        body_budget = max(section_count, round(target_words * self.policy.body_budget_ratio))
        if section_count == 1:
            return [body_budget]

        weights = [0.7, *([1.25] * max(0, section_count - 2)), 0.9]
        total_weight = sum(weights)
        allocations = [max(1, round(body_budget * weight / total_weight)) for weight in weights]
        allocations[-1] += body_budget - sum(allocations)
        return allocations

    @staticmethod
    def _section_purpose(index: int, section_count: int, heading: str) -> str:
        if index == 0:
            return f"Establish the scope and reader context for {heading}."
        if index == section_count - 1:
            return f"Complete the planned coverage through {heading} without generic repetition."
        return f"Develop a distinct, useful aspect of the article through {heading}."
