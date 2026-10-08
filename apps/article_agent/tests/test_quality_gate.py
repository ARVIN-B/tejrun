from django.test import SimpleTestCase
from types import SimpleNamespace

from apps.article_agent.application.article_pipeline import QualityGate
from apps.article_agent.domain import ArticleRequest, SectionDraft


class QualityGateTests(SimpleTestCase):
    def setUp(self) -> None:
        self.request = ArticleRequest(title="Topic", word_count=20, headings=["One", "Two"], language="en")
        self.sections = [
            SectionDraft(0, "One", "one two three four"),
            SectionDraft(1, "Two", "five six seven eight"),
        ]
        self.payload = {"conclusion": "nine", "FAQ": [{"question": f"q{index}", "answer": f"a{index}"} for index in range(4)], "common_mistakes": "ten", "applications": "eleven twelve"}
        self.gate = QualityGate(0.5)

    def test_valid_article_passes(self) -> None:
        self.assertTrue(self.gate.evaluate(self.request, self.sections, self.payload, [], True).passed)

    def test_missing_heading_empty_section_and_duplicate_heading_fail(self) -> None:
        broken = [
            SimpleNamespace(heading="One", content="content", word_count=1),
            SimpleNamespace(heading="One", content="", word_count=0),
        ]
        report = self.gate.evaluate(self.request, broken, self.payload, [], True)
        self.assertFalse(report.passed)
        self.assertFalse(report.checks["headings_preserved"])
        self.assertFalse(report.checks["sections_non_empty"])

    def test_word_count_and_critical_issue_block_completion(self) -> None:
        report = self.gate.evaluate(self.request, self.sections, self.payload, ["unsafe claim"], False)
        self.assertFalse(report.passed)
        self.assertFalse(report.checks["no_critical_issues"])
        self.assertFalse(report.checks["section_reviews_passed"])

    def test_missing_required_keyword_blocks_completion(self) -> None:
        request = ArticleRequest(title="Topic", word_count=20, headings=["One", "Two"], keywords=["required-keyword"], language="en")
        report = self.gate.evaluate(request, self.sections, self.payload, [], True)
        self.assertFalse(report.passed)
        self.assertFalse(report.checks["keywords_covered"])

    def test_keyword_validation_normalizes_persian_zero_width_characters(self) -> None:
        request = ArticleRequest(title="Topic", word_count=20, headings=["One", "Two"], keywords=["سلام‌دنیا"], language="en")
        sections = [SectionDraft(0, "One", "سلام دنیا one two"), SectionDraft(1, "Two", "five six seven eight")]
        self.assertTrue(self.gate.evaluate(request, sections, self.payload, [], True).checks["keywords_covered"])

    def test_faq_count_must_be_exactly_four(self) -> None:
        payload = {**self.payload, "FAQ": [{"question": "q", "answer": "a"}] * 3}
        report = self.gate.evaluate(self.request, self.sections, payload, [], True)
        self.assertFalse(report.passed)

    def test_failed_article_review_blocks_completion(self) -> None:
        report = self.gate.evaluate(self.request, self.sections, self.payload, [], True, article_review_passed=False)
        self.assertFalse(report.passed)
        self.assertFalse(report.checks["article_review_passed"])
