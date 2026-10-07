import unittest

from apps.article_agent.domain import (
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
    def test_article_request_normalizes_headings_and_keywords(self) -> None:
        request = ArticleRequest(
            title="  Django Guide  ",
            word_count=1_500,
            headings=[" Introduction ", "introduction", "Deployment"],
            keywords=[" Django ", "django", " PostgreSQL "],
        )

        self.assertEqual(request.title, "Django Guide")
        self.assertEqual(request.headings, ["Introduction", "Deployment"])
        self.assertEqual(request.keywords, ["Django", "PostgreSQL"])

    def test_article_request_rejects_missing_heading(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one heading"):
            ArticleRequest(title="Topic", word_count=500, headings=[])

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
                        "target_words": 200,
                        "minimum_words": 150,
                        "maximum_words": 250,
                    }
                ],
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
                target_words=500,
                minimum_words=400,
                maximum_words=600,
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
        )
        memory = ArticleMemory(section_summaries=["x" * 1_000 for _ in range(40)])
        builder = ContextBuilder(ContextBudgets(writer_context_limit=2_000))

        context = builder.build_section_context(
            plan, sections[1], memory, ResearchData(), StyleProfile(language="en")
        )

        self.assertLessEqual(len(context), 2_000)
        self.assertNotIn("full previous article", context)

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

    def test_planner_preserves_headings_and_uses_weighted_budgets(self) -> None:
        request = ArticleRequest(
            title="Distributed systems",
            word_count=2_000,
            headings=["Introduction", "Consistency", "Operations", "Conclusion"],
            keywords=["consistency"],
            language="en",
        )

        plan = ArticlePlanner().create_plan(request)

        self.assertEqual([section.heading for section in plan.sections], request.headings)
        self.assertEqual(sum(section.target_words for section in plan.sections), 1_560)
        self.assertGreater(plan.sections[1].target_words, plan.sections[0].target_words)


if __name__ == "__main__":
    unittest.main()
