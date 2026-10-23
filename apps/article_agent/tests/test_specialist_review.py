import asyncio
import json

from django.test import SimpleTestCase, override_settings

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.seo_metadata import SeoMetadataService
from apps.article_agent.application.specialist_review import (
    SpecialistReviewCoordinator,
    merge_specialist_findings,
)
from apps.article_agent.domain import (
    ArticleMemory,
    ArticleRequest,
    ArticleReview,
    ResearchData,
    ReviewIssue,
    ReviewResult,
    SectionDraft,
    SpecialistOpinion,
    StyleProfile,
)


class FakeGenerator:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    async def generate(self, prompt, **_kwargs):
        self.prompts.append(prompt)
        return self.response


@override_settings(
    ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_OUTPUT_TOKENS=128,
    ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_FINDINGS=2,
)
class SpecialistReviewTests(SimpleTestCase):
    def setUp(self):
        self.plan = ArticlePlanner().create_plan(
            ArticleRequest("راهنمای پنل", 500, ["مبانی"], language="fa", brand_name="برند آزمایشی")
        )
        self.section = self.plan.sections[0]
        self.draft = SectionDraft(0, self.section.heading, "متن آزمایشی " * 80)

    def test_all_five_roles_receive_bounded_section_context(self):
        response = json.dumps({
            "role": "seo", "scope": "section", "applicable": True, "score": 8,
            "reason": "", "strengths": [], "required_fixes": [], "findings": [],
        })

        class RoleAware(FakeGenerator):
            async def generate(self, prompt, **kwargs):
                self.prompts.append(prompt)
                role = next(role for role in ("seo", "persian_editor", "article_writer", "industrial_electrical", "solar") if f'"role": "{role}"' in prompt)
                return json.dumps({"role": role, "scope": "section", "applicable": True, "score": 8, "reason": "", "strengths": [], "required_fixes": [], "findings": []})

        llm = RoleAware(response)
        opinions = asyncio.run(SpecialistReviewCoordinator(llm, ContextBuilder()).review_section(
            self.plan, self.section, self.draft, ArticleMemory(), StyleProfile(language="fa"), ResearchData()
        ))
        self.assertEqual([item.role for item in opinions], ["seo", "persian_editor", "article_writer", "industrial_electrical", "solar"])
        self.assertEqual(len(llm.prompts), 5)
        self.assertTrue(all("برند آزمایشی" in prompt for prompt in llm.prompts))

    def test_malformed_one_role_becomes_diagnostic_not_unvalidated_data(self):
        llm = FakeGenerator("not json")
        opinions = asyncio.run(SpecialistReviewCoordinator(llm, ContextBuilder()).review_section(
            self.plan, self.section, self.draft, ArticleMemory(), StyleProfile(language="fa"), ResearchData()
        ))
        self.assertEqual(len(opinions), 5)
        self.assertTrue(all(item.reason.startswith("invalid_provider_response") for item in opinions))


class SpecialistMergeTests(SimpleTestCase):
    def setUp(self):
        self.high_severity_opinion = SpecialistOpinion(
            role="industrial_electrical",
            scope="article",
            applicable=True,
            score=4,
            findings=[
                ReviewIssue(
                    type="safety",
                    severity="high",
                    description="A safety warning is missing.",
                    affected_units=["section:0"],
                    recommendation="Add a qualified safety warning.",
                )
            ],
        )

    def test_merges_article_review_findings_without_attribute_error(self):
        review = ArticleReview(passed=True, score=8)

        merged = merge_specialist_findings(review, [self.high_severity_opinion])

        self.assertIs(merged, review)
        self.assertFalse(review.passed)
        self.assertEqual([item.type for item in review.findings], ["safety"])
        self.assertEqual(review.required_fixes, ["Add a qualified safety warning."])
        self.assertEqual(review.specialist_opinions, [self.high_severity_opinion])

    def test_merges_section_review_issues_without_regression(self):
        review = ReviewResult(passed=True, score=8)
        opinion = SpecialistOpinion(
            role="industrial_electrical",
            scope="section",
            applicable=True,
            score=4,
            findings=self.high_severity_opinion.findings,
        )

        merged = merge_specialist_findings(review, [opinion])

        self.assertIs(merged, review)
        self.assertFalse(review.passed)
        self.assertEqual([item.type for item in review.issues], ["safety"])


class SeoMetadataTests(SimpleTestCase):
    def setUp(self):
        self.plan = ArticlePlanner().create_plan(ArticleRequest("راهنمای انرژی", 500, ["مبانی"], language="fa", brand_name="برند"))
        self.sections = [SectionDraft(0, "مبانی", "محتوای مفید " * 50)]

    def test_valid_metadata_is_structured_and_bounded(self):
        llm = FakeGenerator('{"meta_title":"راهنمای انرژی","meta_description":"راهنمایی کوتاه و مفید برای آشنایی با انرژی."}')
        result = asyncio.run(SeoMetadataService(llm, ContextBuilder()).generate(self.plan, self.sections, []))
        self.assertEqual(result["source"], "generated")
        self.assertEqual(result["validation"]["title_length"], len(result["meta_title"]))

    def test_invalid_metadata_uses_marked_deterministic_fallback(self):
        result = asyncio.run(SeoMetadataService(FakeGenerator("bad"), ContextBuilder()).generate(self.plan, self.sections, []))
        self.assertEqual(result["source"], "fallback")
        self.assertIn("metadata_generation_failed", result["warning"])
