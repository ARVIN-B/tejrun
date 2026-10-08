import unittest

from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import GroundingResearcher, ResearchUnavailable
from apps.article_agent.domain import ArticleRequest, ResearchData


class Provider:
    async def research(self, _plan):
        return ResearchData(facts=["verified fact"], sources=["https://example.test/source"], confidence=0.8,
                            mode="optional", status="available", provider="test")


class ResearchModeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plan = ArticlePlanner().create_plan(ArticleRequest("Research", 500, ["One"], language="en"))

    async def test_disabled_mode_is_explicit_not_empty_success(self):
        result = await GroundingResearcher("disabled").research(self.plan)
        self.assertEqual((result.mode, result.status), ("disabled", "disabled"))

    async def test_optional_unavailable_mode_is_explicit(self):
        result = await GroundingResearcher("optional").research(self.plan)
        self.assertEqual(result.status, "unavailable")
        self.assertTrue(result.error)

    async def test_required_unavailable_fails_safely(self):
        with self.assertRaisesRegex(ResearchUnavailable, "unavailable"):
            await GroundingResearcher("required").research(self.plan)

    async def test_configured_provider_requires_provenance(self):
        result = await GroundingResearcher("required", Provider()).research(self.plan)
        self.assertEqual(result.status, "available")
        self.assertEqual(result.sources, ["https://example.test/source"])
