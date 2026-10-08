import asyncio
from io import BytesIO

from django.test import SimpleTestCase, override_settings

from apps.article_agent.application.article_pipeline import ArticlePipeline, QualityGate
from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.memory import MemoryUpdater
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import (
    ArticleReviewer, FinalEditor, GroundingResearcher, RevisionService,
    SectionReviewer, SectionWriter, SupplementWriter,
)
from apps.article_agent.domain import ArticleMemory, ArticleRequest


class FakeLlm:
    def __init__(self):
        self.review_calls = 0
        self.prompts = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "Review this one section" in prompt:
            self.review_calls += 1
            if self.review_calls == 1:
                return '{"passed":false,"score":5,"issues":[{"type":"coverage","severity":"medium","description":"Add detail"}],"strengths":[],"required_fixes":["Add detail"]}'
            return '{"passed":true,"score":9,"issues":[],"strengths":["clear"],"required_fixes":[]}'
        if "Revise only this section" in prompt:
            return ("REVISED_SECTION_CONTENT bounded memory " * 600)
        if "Review article-level" in prompt:
            return '{"passed":true,"score":9,"findings":[],"required_fixes":[]}'
        if "Write a concise conclusion" in prompt:
            return "concise conclusion"
        if "EXACTLY four useful FAQ" in prompt:
            return "Question: One?\nAnswer: One.\nQuestion: Two?\nAnswer: Two.\nQuestion: Three?\nAnswer: Three.\nQuestion: Four?\nAnswer: Four."
        if "common-mistakes" in prompt:
            return "avoid repetition"
        if "applications section" in prompt:
            return "practical application"
        return "useful bounded memory section content words"


class FakeRenderer:
    def __init__(self):
        self.articles = []

    def generate(self, article: dict) -> BytesIO:
        self.articles.append(article)
        return BytesIO(b"docx")


@override_settings(ARTICLE_AGENT_MAX_SECTION_REVISIONS=2, ARTICLE_AGENT_WORD_COUNT_TOLERANCE=1.0)
class ArticlePipelineIntegrationTests(SimpleTestCase):
    def test_real_pipeline_executes_all_services_with_bounded_writer_context(self) -> None:
        async def run():
            llm, renderer, builder = FakeLlm(), FakeRenderer(), ContextBuilder()
            stages, plans, persisted, memories = [], [], [], []
            pipeline = ArticlePipeline(
                planner=ArticlePlanner(), researcher=GroundingResearcher(),
                writer=SectionWriter(llm, builder), reviewer=SectionReviewer(llm, builder),
                reviser=RevisionService(llm, builder), memory_updater=MemoryUpdater(),
                article_reviewer=ArticleReviewer(llm, builder), final_editor=FinalEditor(llm, builder),
                supplement_writer=SupplementWriter(llm, builder), quality_gate=QualityGate(1.0),
                renderer=renderer, context_builder=builder,
                update_stage=lambda *args: record(stages, args),
                persist_plan=lambda plan: record(plans, plan),
                persist_section=lambda draft, review: record(persisted, (draft, review)),
                persist_memory=lambda memory: record(memories, memory),
                cancelled=lambda: false(),
            )
            request = ArticleRequest(
                title="Bounded article", word_count=1200,
                headings=["First required heading", "Second required heading"],
                keywords=["bounded", "memory"], language="en",
            )
            result = await pipeline.run(request, ArticleMemory())
            return result, llm, renderer, stages, plans, persisted, memories, request, builder

        result, llm, renderer, stages, plans, persisted, memories, request, builder = asyncio.run(run())
        self.assertTrue(result.quality_report.passed)
        self.assertEqual([item[0].heading for item in persisted if "passed" in item[1]], request.headings)
        self.assertEqual([section["heading"] for section in renderer.articles[0]["sections"]], request.headings)
        self.assertEqual(len(renderer.articles[0]["FAQ"]), 4)
        self.assertEqual(len(memories), 2)
        self.assertIn("researching", [stage[0] for stage in stages])
        self.assertIn("reviewing", [stage[0] for stage in stages])
        self.assertIn("revising", [stage[0] for stage in stages])
        self.assertIn("final_review", [stage[0] for stage in stages])
        self.assertIn("editing", [stage[0] for stage in stages])
        self.assertIn("quality_check", [stage[0] for stage in stages])
        self.assertIn("rendering", [stage[0] for stage in stages])
        writer_prompts = [prompt for prompt in llm.prompts if "Write only the requested section" in prompt]
        self.assertEqual(len(writer_prompts), 2)
        self.assertTrue(all(("REVISED_SECTION_CONTENT " * 600) not in prompt for prompt in writer_prompts))
        self.assertTrue(all(len(prompt) <= builder.budgets.writer_context_limit + 500 for prompt in writer_prompts))


async def record(target, value):
    target.append(value)


async def false():
    return False
