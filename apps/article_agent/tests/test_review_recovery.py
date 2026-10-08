import asyncio

from django.test import SimpleTestCase, override_settings

from apps.article_agent.application.article_pipeline import ArticlePipeline
from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.memory import MemoryUpdater
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import GroundingResearcher, SectionReviewer, SectionWriter, SupplementWriter
from apps.article_agent.domain import ArticleMemory, ArticleRequest, ReviewResult, StyleProfile


@override_settings(ARTICLE_AGENT_MAX_SECTION_REVISIONS=1)
class ReviewRecoveryTests(SimpleTestCase):
    def test_malformed_review_is_converted_to_a_bounded_failed_review(self):
        class Llm:
            async def generate(self, prompt):
                return "not json" if "Review this one section" in prompt else "word " * 100

        class Reviser:
            async def revise(self, _plan, section, _draft, _review, _memory, _style):
                from apps.article_agent.domain import SectionDraft
                return SectionDraft(section.index, section.heading, "fixed " * 100)

        async def run():
            planner = ArticlePlanner()
            plan = planner.create_plan(ArticleRequest("Topic", 500, ["Heading"], language="en"))
            section = plan.sections[0]
            pipeline = object.__new__(ArticlePipeline)
            pipeline.reviewer = SectionReviewer(Llm(), ContextBuilder())
            pipeline.reviser = Reviser()
            pipeline.update_stage = lambda *_args: completed()
            pipeline.cancelled = completed_false
            draft = await SectionWriter(Llm(), ContextBuilder()).write(plan, section, ArticleMemory(), await GroundingResearcher().research(plan), StyleProfile(language="en"))
            return await pipeline._review_with_revisions(plan, section, draft, ArticleMemory(), StyleProfile(language="en"), 1)

        draft, review = asyncio.run(run())
        self.assertFalse(review.passed)
        self.assertEqual(draft.revision_number, 0)


async def completed():
    return None


async def completed_false():
    return False
