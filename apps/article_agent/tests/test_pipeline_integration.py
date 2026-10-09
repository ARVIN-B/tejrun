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
from apps.article_agent.domain import ArticleReview, ReviewResult, SectionDraft


class FakeLlm:
    def __init__(self):
        self.review_calls = 0
        self.prompts = []

    async def generate(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        if "Review this one section" in prompt:
            self.review_calls += 1
            if self.review_calls == 1:
                return '{"passed":false,"score":5,"issues":[{"type":"coverage","severity":"medium","description":"Add detail"}],"strengths":[],"required_fixes":["Add detail"]}'
            return '{"passed":true,"score":9,"issues":[],"strengths":["clear"],"required_fixes":[]}'
        if "Revise only this section" in prompt:
            return ("REVISED_SECTION_CONTENT bounded memory " * 45)
        if "Repair this article unit" in prompt and '"kind":"faq"' in prompt:
            answer = "answer " * 52
            return "\n".join(f"Question: Question {index}?\nAnswer: {answer}" for index in range(4))
        if "Repair this article unit" in prompt and '"kind":"conclusion"' in prompt:
            return "conclusion " * 160
        if "Repair this article unit" in prompt:
            return "practical " * 125
        if "Repair the entire section's length" in prompt or "Repair this article unit" in prompt:
            return "repaired budget compliant section content " * 55
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


@override_settings(ARTICLE_AGENT_MAX_SECTION_REVISIONS=2, ARTICLE_AGENT_WORD_COUNT_TOLERANCE=4.0)
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
                persist_checkpoint=lambda checkpoint: record(memories, checkpoint),
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
        self.assertTrue(all(item["status"] == "accepted" for item in result.quality_report.unit_accounting.values()))
        self.assertEqual(len(memories), 3)
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

    def test_renderer_failure_resumes_from_section_and_extra_checkpoints_without_regeneration(self) -> None:
        class Writer:
            calls = 0
            async def write_content(self, _plan, section, *_args):
                self.calls += 1; return "section " * section.target_words
            async def repair(self, _plan, _section, content, _allocation, _style): return content
        class Reviewer:
            async def review(self, *_args): return ReviewResult(True, 9)
        class Reviser:
            async def revise(self, *_args): raise AssertionError("revision should not be needed")
        class Supplements:
            calls = 0
            async def generate(self, plan, _memory, kind):
                self.calls += 1
                if kind == "faq": return "\n".join(f"Question: Q{index}?\nAnswer: " + "answer " * 30 for index in range(4))
                return "extra " * plan.budget.allocation_for(kind).target_words
            async def repair(self, _plan, _memory, _kind, content, _allocation): return content
        class ArticleReviewerStub:
            async def review(self, *_args): return ArticleReview(True, 9)
        class Editor:
            async def edit(self, _plan, sections, *_args): return sections
        class Renderer:
            calls = 0
            def generate(self, _article):
                self.calls += 1
                if self.calls == 1: raise RuntimeError("renderer unavailable")
                return BytesIO(b"docx")

        async def run():
            writer, supplements, renderer = Writer(), Supplements(), Renderer()
            persisted, checkpoints = [], []
            async def noop(*_args): return None
            def pipeline():
                return ArticlePipeline(
                    planner=ArticlePlanner(), researcher=GroundingResearcher(), writer=writer, reviewer=Reviewer(), reviser=Reviser(),
                    memory_updater=MemoryUpdater(), article_reviewer=ArticleReviewerStub(), final_editor=Editor(), supplement_writer=supplements,
                    quality_gate=QualityGate(1.0), renderer=renderer, context_builder=ContextBuilder(),
                    update_stage=noop, persist_plan=noop,
                    persist_section=lambda draft, review: record(persisted, (draft, review)), persist_memory=noop,
                    persist_checkpoint=lambda checkpoint: record(checkpoints, checkpoint), cancelled=lambda: false(),
                )
            request = ArticleRequest("Resume", 500, ["Section"], language="en")
            with self.assertRaisesRegex(RuntimeError, "renderer unavailable"):
                await pipeline().run(request)
            completed_sections = {draft.section_index: draft for draft, review in persisted if review.get("passed")}
            result = await pipeline().run(request, completed_sections=completed_sections, checkpoint=checkpoints[-1])
            return writer.calls, supplements.calls, renderer.calls, result

        writer_calls, supplement_calls, renderer_calls, result = asyncio.run(run())
        self.assertEqual(writer_calls, 1)
        self.assertEqual(supplement_calls, 4)
        self.assertEqual(renderer_calls, 2)
        self.assertEqual(result.document, b"docx")


async def record(target, value):
    target.append(value)


async def false():
    return False
