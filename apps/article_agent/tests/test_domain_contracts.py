import unittest
import json

from apps.article_agent.domain import (
    ArticleAllocation,
    ArticleBudget,
    ArticleMemory,
    ArticlePlan,
    ArticleRequest,
    QualityReport,
    SectionDraft,
    SectionPlan,
)
from apps.article_agent.domain.serialization import (
    ContractValidationError,
    article_plan_from_dict,
    review_result_from_dict,
)
from apps.article_agent.application.context_builder import ContextBudgets, ContextBuilder
from apps.article_agent.application.memory import MemoryBudget, MemoryUpdater
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.domain import ResearchData, StyleProfile


class DomainContractTests(unittest.TestCase):
    @staticmethod
    def _budget(section_count: int, total_words: int = 200) -> ArticleBudget:
        targets = [total_words // (section_count + 4)] * (section_count + 4)
        targets[-1] += total_words - sum(targets)
        units = [
            *( (f"section:{index}", "section") for index in range(section_count) ),
            ("conclusion", "conclusion"), ("faq", "faq"),
            ("common_mistakes", "common_mistakes"), ("applications", "applications"),
        ]
        return ArticleBudget(total_words=total_words, allocations=[
            ArticleAllocation(unit_id=unit_id, unit_type=unit_type, target_words=target,
                              minimum_words=max(1, target - 1), maximum_words=target + 1, priority=index)
            for index, ((unit_id, unit_type), target) in enumerate(zip(units, targets, strict=True))
        ])

    def test_article_request_normalizes_headings_and_keywords(self) -> None:
        request = ArticleRequest(
            title="  Django Guide  ",
            word_count=1_500,
            headings=[" Introduction ", "Architecture", "Deployment"],
            keywords=[" Django ", "django", " PostgreSQL "],
        )

        self.assertEqual(request.title, "Django Guide")
        self.assertEqual(request.headings, ["Introduction", "Architecture", "Deployment"])
        self.assertEqual(request.keywords, ["Django", "PostgreSQL"])

    def test_article_request_rejects_missing_heading(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one heading"):
            ArticleRequest(title="Topic", word_count=500, headings=[])

    def test_article_request_rejects_duplicate_headings_without_changing_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "headings must not contain duplicates"):
            ArticleRequest(title="Topic", word_count=500, headings=["Intro", "intro"])

    def test_article_plan_requires_sequential_section_indexes(self) -> None:
        section = SectionPlan(
            index=1,
            heading="Introduction",
            purpose="Set context",
            key_points=["Scope"],
            target_words=200,
            minimum_words=150,
            maximum_words=250,
        )

        with self.assertRaisesRegex(ValueError, "sequential"):
            ArticlePlan(
                title="Topic",
                goal="Explain",
                audience="General",
                tone="Professional",
                language="en",
                primary_topic="Topic",
                keywords=[],
                sections=[section],
                budget=self._budget(1),
            )

    def test_memory_normalization_is_compact_and_deduplicated(self) -> None:
        memory = ArticleMemory(
            covered_topics=[" caching ", "Caching", "security"],
            claims_made=["Use timeouts", "use timeouts"],
        ).normalized()

        self.assertEqual(memory.covered_topics, ["caching", "security"])
        self.assertEqual(memory.claims_made, ["Use timeouts"])

    def test_quality_report_calculates_relative_difference(self) -> None:
        report = QualityReport(
            passed=True,
            target_word_count=1_000,
            actual_word_count=950,
            tolerance=0.1,
        )

        self.assertEqual(report.relative_word_difference, 0.05)

    def test_article_plan_contract_rejects_missing_required_fields(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "Missing required field: goal"):
            article_plan_from_dict({"title": "Topic", "sections": []})

    def test_article_plan_contract_ignores_safe_extra_fields(self) -> None:
        plan = article_plan_from_dict(
            {
                "title": "Topic",
                "goal": "Explain",
                "audience": "General",
                "tone": "Professional",
                "language": "en",
                "primary_topic": "Topic",
                "keywords": [],
                "sections": [
                    {
                        "index": 0,
                        "heading": "Introduction",
                        "purpose": "Set context",
                        "key_points": ["Scope"],
                        "target_words": 40,
                        "minimum_words": 39,
                        "maximum_words": 41,
                    }
                ],
                "budget": {
                    "total_words": 200,
                    "allocations": [
                        {"unit_id": "section:0", "unit_type": "section", "target_words": 40, "minimum_words": 39, "maximum_words": 41, "priority": 0},
                        {"unit_id": "conclusion", "unit_type": "conclusion", "target_words": 40, "minimum_words": 39, "maximum_words": 41, "priority": 1},
                        {"unit_id": "faq", "unit_type": "faq", "target_words": 40, "minimum_words": 39, "maximum_words": 41, "priority": 2},
                        {"unit_id": "common_mistakes", "unit_type": "common_mistakes", "target_words": 40, "minimum_words": 39, "maximum_words": 41, "priority": 3},
                        {"unit_id": "applications", "unit_type": "applications", "target_words": 40, "minimum_words": 39, "maximum_words": 41, "priority": 4},
                    ],
                },
                "untrusted_extra": "ignored",
            }
        )

        self.assertEqual(plan.sections[0].heading, "Introduction")

    def test_review_contract_rejects_malformed_issue(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "Missing required field: severity"):
            review_result_from_dict(
                {
                    "passed": False,
                    "score": 5,
                    "issues": [{"type": "repetition", "description": "Repeated idea"}],
                }
            )

    def test_writer_context_stays_bounded_for_a_large_synthetic_article(self) -> None:
        sections = [
            SectionPlan(
                index=index,
                heading=f"Section {index}",
                purpose="Explain a distinct aspect",
                key_points=["A key point"],
                target_words=181,
                minimum_words=180,
                maximum_words=182,
            )
            for index in range(40)
        ]
        plan = ArticlePlan(
            title="Large Article",
            goal="Explain a complex topic",
            audience="General",
            tone="Professional",
            language="en",
            primary_topic="Topic",
            keywords=["topic"],
            sections=sections,
            budget=self._budget(40, total_words=8_000),
        )
        memory = ArticleMemory(section_summaries=["x" * 1_000 for _ in range(40)])
        builder = ContextBuilder(ContextBudgets(writer_context_limit=2_000))

        context = builder.build_section_context(
            plan, sections[1], memory, ResearchData(), StyleProfile(language="en")
        )

        self.assertLessEqual(len(context), 2_000)
        self.assertNotIn("full previous article", context)

    def test_context_budget_never_returns_invalid_json(self) -> None:
        builder = ContextBuilder(ContextBudgets(writer_context_limit=40))
        context = builder._bounded_json({"task": "required", "memory": {"x": "y" * 10000}}, 40)
        self.assertEqual(json.loads(context)["task"], "required")

    def test_memory_updater_keeps_compact_summaries_and_bounded_entries(self) -> None:
        updater = MemoryUpdater(MemoryBudget(max_items_per_field=2, max_summary_characters=40))
        section = SectionPlan(
            index=0,
            heading="Caching",
            purpose="Explain caching",
            key_points=["cache invalidation"],
            target_words=200,
            minimum_words=150,
            maximum_words=250,
        )
        draft = SectionDraft(
            section_index=0,
            heading="Caching",
            content="word " * 100,
        )
        memory = ArticleMemory(covered_topics=["old-a", "old-b"])

        updated = updater.update(memory, section, draft, claims=["Use invalidation"])

        self.assertEqual(updated.covered_topics, ["old-b", "Caching"])
        self.assertLessEqual(len(updated.section_summaries[-1]), 50)
        self.assertEqual(updated.claims_made, ["Use invalidation"])

    def test_planner_allocates_the_complete_article_budget_before_writing(self) -> None:
        request = ArticleRequest(
            title="Distributed systems",
            word_count=2_000,
            headings=["Introduction", "Consistency", "Operations", "Conclusion"],
            keywords=["consistency"],
            language="en",
        )

        plan = ArticlePlanner().create_plan(request)

        self.assertEqual([section.heading for section in plan.sections], request.headings)
        self.assertEqual(plan.budget.total_words, request.word_count)
        self.assertEqual(sum(item.target_words for item in plan.budget.allocations), request.word_count)
        self.assertEqual(
            {item.unit_type for item in plan.budget.allocations},
            {"section", "conclusion", "faq", "common_mistakes", "applications"},
        )
        self.assertTrue(all(item.minimum_words <= item.target_words <= item.maximum_words for item in plan.budget.allocations))
        self.assertEqual(sum(section.target_words for section in plan.sections), sum(
            item.target_words for item in plan.budget.allocations if item.unit_type == "section"
        ))

    def test_planner_budget_is_feasible_and_exact_for_required_sizes_and_heading_counts(self) -> None:
        for total_words in (500, 1_000, 5_000, 10_000, 20_000):
            for heading_count in (1, 3, 10):
                with self.subTest(total_words=total_words, heading_count=heading_count):
                    request = ArticleRequest(
                        title="Planning test", word_count=total_words,
                        headings=[f"Heading {index}" for index in range(heading_count)], language="en",
                    )
                    budget = ArticlePlanner().create_plan(request).budget
                    self.assertEqual(sum(item.target_words for item in budget.allocations), total_words)
                    self.assertLessEqual(sum(item.minimum_words for item in budget.allocations), total_words)
                    self.assertGreaterEqual(sum(item.maximum_words for item in budget.allocations), total_words)


if __name__ == "__main__":
    unittest.main()
