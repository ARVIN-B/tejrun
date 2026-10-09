import asyncio
import unittest

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import ArticleReviewer, FinalEditor
from apps.article_agent.domain import ArticleMemory, ArticleRequest, ArticleReview, ResearchData, ReviewIssue, ReviewResult, SectionDraft, StyleProfile


class ArticleReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_article_reviewer_receives_real_prose_and_affected_units(self):
        class Llm:
            prompt = ""
            async def generate(self, prompt, **_kwargs):
                self.prompt = prompt
                return '{"passed":false,"score":4,"findings":[{"type":"repetition","severity":"high","description":"Repeated opening","affected_units":["section:1"],"recommendation":"Replace the repeated opening."}],"required_fixes":["Fix repetition"]}'
        llm = Llm()
        plan = ArticlePlanner().create_plan(ArticleRequest("Topic", 1000, ["One", "Two"], language="en"))
        sections = [SectionDraft(0, "One", "first prose " * 120), SectionDraft(1, "Two", "second prose " * 120)]
        review = await ArticleReviewer(llm, ContextBuilder()).review(
            plan, ArticleMemory(), sections, [ReviewResult(True, 9), ReviewResult(True, 9)],
            {"conclusion": "end", "FAQ": [], "common_mistakes": "mistakes", "applications": "uses"}, ResearchData(),
        )
        self.assertIn("first prose", llm.prompt)
        self.assertEqual(review.findings[0].affected_units, ["section:1"])

    async def test_final_editor_edits_only_affected_section(self):
        class Llm:
            calls = 0
            async def generate(self, _prompt, **_kwargs):
                self.calls += 1
                return "edited prose " * 100
        llm = Llm()
        plan = ArticlePlanner().create_plan(ArticleRequest("Topic", 1000, ["One", "Two"], language="en"))
        original = [SectionDraft(0, "One", "one " * 100), SectionDraft(1, "Two", "two " * 100)]
        review = ArticleReview(False, 5, [ReviewIssue("style", "medium", "fix", ["section:1"], "Improve style")], required_fixes=["fix"])
        edited = await FinalEditor(llm, ContextBuilder()).edit(plan, original, review, StyleProfile(language="en"))
        self.assertEqual(llm.calls, 1)
        self.assertEqual(edited[0].content, original[0].content)
        self.assertNotEqual(edited[1].content, original[1].content)
