"""Deterministic initial article planning with weighted word allocation."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from apps.article_agent.domain import ArticleAllocation, ArticleBudget, ArticlePlan, ArticleRequest, SectionPlan


@dataclass(frozen=True, slots=True)
class PlanningPolicy:
    section_weight: float = 1.0
    conclusion_weight: float = 0.7
    faq_weight: float = 1.0
    common_mistakes_weight: float = 0.55
    applications_weight: float = 0.55
    minimum_ratio: float = 0.85
    maximum_ratio: float = 1.15


class ArticlePlanner:
    """Creates a valid plan while preserving the user's required headings."""

    def __init__(self, policy: PlanningPolicy | None = None) -> None:
        self.policy = policy or PlanningPolicy()

    def create_plan(self, request: ArticleRequest) -> ArticlePlan:
        budget = self._create_budget(request)
        sections = [
            SectionPlan(
                index=index,
                heading=heading,
                purpose=self._section_purpose(index, len(request.headings), heading),
                key_points=[f"Explain the role of {heading} in relation to {request.title}."],
                target_words=allocation.target_words,
                minimum_words=allocation.minimum_words,
                maximum_words=allocation.maximum_words,
                must_include=[heading],
                must_avoid=["Repeat already covered concepts without adding new value."],
                dependencies=[index - 1] if index else [],
                research_requirements=[],
                keywords=request.keywords,
            )
            for index, heading in enumerate(request.headings)
            for allocation in [budget.allocation_for(f"section:{index}")]
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
            budget=budget,
            global_constraints=[
                "Preserve the user-provided heading intent.",
                "Prefer grounded, useful detail over filler.",
                "Do not fabricate sources or statistics.",
            ],
            coverage_requirements=request.headings,
        )

    def _create_budget(self, request: ArticleRequest) -> ArticleBudget:
        units = [
            *( (f"section:{index}", "section", self.policy.section_weight, index) for index in range(len(request.headings)) ),
            ("conclusion", "conclusion", self.policy.conclusion_weight, 1),
            ("faq", "faq", self.policy.faq_weight, 2),
            ("common_mistakes", "common_mistakes", self.policy.common_mistakes_weight, 3),
            ("applications", "applications", self.policy.applications_weight, 4),
        ]
        targets = self._allocate_exactly(request.word_count, [unit[2] for unit in units])
        return ArticleBudget(
            total_words=request.word_count,
            allocations=[
                ArticleAllocation(
                    unit_id=unit_id, unit_type=unit_type, target_words=target,
                    minimum_words=max(1, int(target * self.policy.minimum_ratio)),
                    maximum_words=max(target, ceil(target * self.policy.maximum_ratio)),
                    priority=priority,
                )
                for (unit_id, unit_type, _weight, priority), target in zip(units, targets, strict=True)
            ],
        )

    @staticmethod
    def _allocate_exactly(total_words: int, weights: list[float]) -> list[int]:
        """Largest-remainder allocation; deterministic and exact for all sizes."""
        total_weight = sum(weights)
        raw = [total_words * weight / total_weight for weight in weights]
        targets = [max(1, int(value)) for value in raw]
        remainder = total_words - sum(targets)
        order = sorted(range(len(weights)), key=lambda index: (raw[index] - int(raw[index]), -index), reverse=True)
        for index in range(remainder):
            targets[order[index % len(order)]] += 1
        if sum(targets) != total_words:
            raise ValueError("Unable to allocate the requested full article budget.")
        return targets

    @staticmethod
    def _section_purpose(index: int, section_count: int, heading: str) -> str:
        if index == 0:
            return f"Establish the scope and reader context for {heading}."
        if index == section_count - 1:
            return f"Complete the planned coverage through {heading} without generic repetition."
        return f"Develop a distinct, useful aspect of the article through {heading}."
