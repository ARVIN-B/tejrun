import asyncio
import json

from django.test import SimpleTestCase, override_settings

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import SectionWriter
from apps.article_agent.domain import ArticleMemory, ArticleRequest, ResearchData, StyleProfile


class RecordingGenerator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []

    async def generate(self, prompt: str, *, operation="writing", output_tokens=None) -> str:
        self.calls.append((prompt, output_tokens))
        return "prose " * 20


class ContextSafetyTests(SimpleTestCase):
    @override_settings(
        ARTICLE_AGENT_GROQ_TOKENS_PER_MINUTE=8_000,
        ARTICLE_AGENT_GROQ_SAFETY_MARGIN=0.90,
        ARTICLE_AGENT_LLM_PROMPT_OVERHEAD_TOKENS=512,
    )
    def test_context_is_reduced_to_fit_the_local_tpm_reservation(self) -> None:
        builder = ContextBuilder()
        # 7,200 effective TPM - 2,048 completion - 512 prompt headroom.
        self.assertEqual(builder.limit_for_output_tokens(2_048, 14_000), 9_280)

    @override_settings(
        ARTICLE_AGENT_LLM_CONTEXT_WINDOW_TOKENS=2048,
        ARTICLE_AGENT_LLM_CONTEXT_SAFETY_TOKENS=128,
        ARTICLE_AGENT_LLM_PROMPT_OVERHEAD_TOKENS=256,
        ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS=2048,
        ARTICLE_AGENT_OUTPUT_TOKENS_PER_WORD=2.0,
        ARTICLE_AGENT_OUTPUT_TOKEN_BUFFER=128,
    )
    def test_large_section_is_split_and_never_reuses_full_prior_prose(self) -> None:
        plan = ArticlePlanner().create_plan(
            ArticleRequest(
                title="Long form", word_count=10_000, headings=["Only section"], language="en"
            )
        )
        generator = RecordingGenerator()
        writer = SectionWriter(generator, ContextBuilder())

        content = asyncio.run(
            writer.write_content(
                plan,
                plan.sections[0],
                ArticleMemory(section_summaries=["prior summary " * 100]),
                ResearchData(),
                StyleProfile(language="en"),
            )
        )

        self.assertGreater(len(generator.calls), 1)
        self.assertEqual(len(writer.contexts), len(generator.calls))
        for context, (_, output_tokens) in zip(writer.contexts, generator.calls, strict=True):
            self.assertLessEqual(
                len(context.encode("utf-8")),
                writer.context_builder.limit_for_output_tokens(
                    output_tokens, writer.context_builder.budgets.writer_context_limit
                ),
            )
            self.assertIsInstance(json.loads(context), dict)
        self.assertGreater(content.count("prose"), 20)
