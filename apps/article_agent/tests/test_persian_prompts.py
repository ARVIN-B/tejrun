import asyncio

from django.test import SimpleTestCase

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import SectionReviewer, SectionWriter, SupplementWriter
from apps.article_agent.domain import ArticleMemory, ArticleRequest, ResearchData, SectionDraft, StyleProfile


class RecordingLlm:
    def __init__(self, response: str = "متن دقیق و کاربردی " * 30) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        return self.response


class PersianPromptTests(SimpleTestCase):
    def setUp(self) -> None:
        self.plan = ArticlePlanner().create_plan(
            ArticleRequest("راهنمای آزمایشی", 500, ["مبانی"], language="fa")
        )
        self.style = StyleProfile(language="fa", audience="عمومی")

    def test_section_prompt_uses_compact_idiomatic_persian_standard(self) -> None:
        llm = RecordingLlm()
        asyncio.run(
            SectionWriter(llm, ContextBuilder()).write_content(
                self.plan, self.plan.sections[0], ArticleMemory(), ResearchData(), self.style
            )
        )
        prompt = llm.prompts[0]
        self.assertIn("فارسیِ روان و معیار", prompt)
        self.assertIn("در دنیای امروز", prompt)
        self.assertIn("داده، مثال، منبع یا تجربه نساز", prompt)

    def test_reviewer_requests_concrete_persian_quality_findings(self) -> None:
        llm = RecordingLlm("REQUIRED FIXES:\n- none")
        asyncio.run(
            SectionReviewer(llm, ContextBuilder()).review(
                self.plan,
                self.plan.sections[0],
                SectionDraft(0, "مبانی", "این یک متن فنی و دقیق است. " * 20),
                ArticleMemory(),
                self.style,
            )
        )
        self.assertIn("تکرار معنایی", llm.prompts[0])
        self.assertIn("نثر فنی و دقیق", llm.prompts[0])

    def test_faq_prompt_requests_a_real_reader_question(self) -> None:
        llm = RecordingLlm("پرسش کوتاه")
        allocation = self.plan.budget.allocation_for("faq")
        asyncio.run(SupplementWriter(llm, ContextBuilder()).generate_faq(self.plan, ArticleMemory(), allocation))
        self.assertIn("پرسش واقعی خواننده", llm.prompts[0])
