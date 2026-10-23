from django.test import SimpleTestCase

from apps.article_agent.application.content_quality import ContentSafetyValidator
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.style import HumanStyleAnalyzer
from apps.article_agent.domain import ArticleRequest, ResearchData, SectionDraft


class ContentSafetyValidatorTests(SimpleTestCase):
    def setUp(self) -> None:
        self.plan = ArticlePlanner().create_plan(
            ArticleRequest(
                "راهنمای مناقصه", 600, ["شرایط ثبت نام"], language="fa"
            )
        )
        self.validator = ContentSafetyValidator()

    def test_unsupported_deadline_and_invented_provider_are_replaced_conservatively(self) -> None:
        original = "شرکت تجران اعلام کرده مهلت ثبت نام 7 روز است."
        safe, findings = self.validator.sanitize_text(
            self.plan, original, ResearchData(), unit_id="section:0"
        )
        self.assertTrue(findings)
        self.assertNotIn("تجران", safe)
        self.assertNotIn("7 روز", safe)
        self.assertIn("فراخوان", safe)

    def test_exact_claim_is_retained_only_when_available_research_supports_it(self) -> None:
        text = "مهلت ثبت نام 7 روز است."
        research = ResearchData(
            claims=[text], sources=["https://example.test/notice"],
            mode="required", status="available",
        )
        safe, findings = self.validator.sanitize_text(
            self.plan, text, research, unit_id="section:0"
        )
        self.assertEqual(safe, text)
        self.assertEqual(findings, [])

    def test_conflicting_unverified_quantities_are_not_left_in_separate_sections(self) -> None:
        sections = [
            SectionDraft(0, "الف", "ارائه صورت مالی دو سال اخیر لازم است."),
            SectionDraft(1, "ب", "ارائه صورت مالی سه سال اخیر لازم است."),
        ]
        sanitized, findings = self.validator.sanitize_contradictions(
            self.plan, sections, ResearchData()
        )
        self.assertTrue(findings)
        self.assertNotIn("دو سال", sanitized[0].content)
        self.assertNotIn("سه سال", sanitized[1].content)

    def test_planner_gives_definition_documents_and_process_headings_distinct_scopes(self) -> None:
        plan = ArticlePlanner().create_plan(
            ArticleRequest(
                "مناقصه", 1200,
                ["مناقصه چیست", "مدارک لازم", "مراحل ثبت نام"],
                language="fa",
            )
        )
        self.assertIn("checklist", " ".join(plan.sections[0].key_points).casefold())
        self.assertIn("document", " ".join(plan.sections[1].key_points).casefold())
        self.assertIn("order", " ".join(plan.sections[2].key_points).casefold())


class StyleQualityFindingTests(SimpleTestCase):
    def test_flags_actionable_template_opening_not_clean_grammar_or_metadata(self) -> None:
        sections = [
            SectionDraft(0, "One", "In this article, the reader will learn one practical point."),
        ]
        findings = HumanStyleAnalyzer().review_findings(sections, [])
        self.assertEqual(findings[0].type, "generic_opening")
        self.assertEqual(findings[0].affected_units, ["section:0"])

    def test_flags_exact_repetition_across_headings_for_targeted_editing(self) -> None:
        repeated = "This is the same detailed practical explanation for every reader"
        findings = HumanStyleAnalyzer().review_findings(
            [
                SectionDraft(0, "One", repeated + " in the first section."),
                SectionDraft(1, "Two", repeated + " in the second section."),
            ],
            [],
        )
        repetition = next(item for item in findings if item.type == "cross_section_repetition")
        self.assertEqual(repetition.affected_units, ["section:0", "section:1"])
