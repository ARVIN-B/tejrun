"""The real production Article Agent orchestration pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Awaitable, Callable, Protocol

from django.conf import settings

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.memory import MemoryUpdater
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import (
    ArticleReviewer, FinalEditor, NoopResearcher, Researcher, RevisionService,
    SectionReviewer, SectionWriter, SupplementWriter,
)
from apps.article_agent.domain import ArticleMemory, ArticleRequest, QualityReport, ReviewResult, SectionDraft, StyleProfile


class PipelineQualityError(RuntimeError):
    pass


class PipelineCancelled(RuntimeError):
    pass


class DocumentRenderer(Protocol):
    def generate(self, article: dict): ...


@dataclass(slots=True)
class PipelineResult:
    article: dict
    document: bytes
    quality_report: QualityReport


class QualityGate:
    def __init__(self, tolerance: float | None = None) -> None:
        self.tolerance = tolerance if tolerance is not None else settings.ARTICLE_AGENT_WORD_COUNT_TOLERANCE

    def evaluate(self, request: ArticleRequest, sections: list[SectionDraft], payload: dict, critical_issues: list[str], reviews_passed: bool) -> QualityReport:
        headings = [section.heading for section in sections]
        word_count = sum(section.word_count for section in sections) + sum(len(str(value).split()) for value in payload.values())
        article_text = " ".join([*(section.content for section in sections), *(str(value) for value in payload.values())]).casefold()
        checks = {
            "headings_preserved": headings == request.headings,
            "headings_unique": len(headings) == len(set(item.casefold() for item in headings)),
            "sections_non_empty": all(section.content.strip() for section in sections),
            "word_count_within_tolerance": abs(word_count - request.word_count) / request.word_count <= self.tolerance,
            "conclusion_present": bool(payload.get("conclusion")),
            "faq_present": bool(payload.get("FAQ")),
            "common_mistakes_present": bool(payload.get("common_mistakes")),
            "applications_present": bool(payload.get("applications")),
            "no_critical_issues": not critical_issues,
            "section_reviews_passed": reviews_passed,
            "keywords_covered": all(keyword.casefold() in article_text for keyword in request.keywords),
        }
        return QualityReport(
            passed=all(checks.values()), target_word_count=request.word_count,
            actual_word_count=word_count, tolerance=self.tolerance, checks=checks,
            warnings=critical_issues,
        )


class ArticlePipeline:
    """Runs every required generation stage in order using bounded context."""

    def __init__(
        self, *, planner: ArticlePlanner, researcher: Researcher, writer: SectionWriter,
        reviewer: SectionReviewer, reviser: RevisionService, memory_updater: MemoryUpdater,
        article_reviewer: ArticleReviewer, final_editor: FinalEditor, supplement_writer: SupplementWriter,
        quality_gate: QualityGate, renderer: DocumentRenderer, context_builder: ContextBuilder,
        update_stage: Callable[[str, int, str, int], Awaitable[None]],
        persist_plan: Callable[[object], Awaitable[None]],
        persist_section: Callable[[SectionDraft, dict], Awaitable[None]],
        persist_memory: Callable[[ArticleMemory], Awaitable[None]],
        cancelled: Callable[[], Awaitable[bool]],
    ) -> None:
        self.planner, self.researcher, self.writer, self.reviewer, self.reviser = planner, researcher, writer, reviewer, reviser
        self.memory_updater, self.article_reviewer, self.final_editor = memory_updater, article_reviewer, final_editor
        self.supplement_writer, self.quality_gate, self.renderer, self.context_builder = supplement_writer, quality_gate, renderer, context_builder
        self.update_stage, self.persist_plan, self.persist_section = update_stage, persist_plan, persist_section
        self.persist_memory, self.cancelled = persist_memory, cancelled

    async def run(
        self, request: ArticleRequest, initial_memory: ArticleMemory | None = None,
        completed_sections: dict[int, SectionDraft] | None = None,
    ) -> PipelineResult:
        await self._ensure_not_cancelled()
        await self.update_stage("planning", 5, "Planning article", 0)
        plan = self.planner.create_plan(request)
        await self.persist_plan(plan)
        await self.update_stage("researching", 10, "Researching article", 0)
        research = await self.researcher.research(plan)
        memory = (initial_memory or ArticleMemory()).normalized()
        completed_sections = completed_sections or {}
        style = StyleProfile(language=request.language, tone=request.tone, audience=request.audience)
        accepted: list[SectionDraft] = []
        reviews = []
        for section in plan.sections:
            await self._ensure_not_cancelled()
            if section.index in completed_sections:
                accepted.append(completed_sections[section.index])
                reviews.append(ReviewResult(passed=True, score=10))
                continue
            progress = 15 + int(50 * section.index / max(1, len(plan.sections)))
            await self.update_stage("writing", progress, f"Writing section {section.index + 1}", section.index)
            draft = await self.writer.write(plan, section, memory, research, style)
            review = await self._review_with_revisions(plan, section, draft, memory, style, progress)
            draft, review = review
            await self.persist_section(draft, {"passed": review.passed, "score": review.score, "required_fixes": review.required_fixes, "issues": [asdict(issue) for issue in review.issues]})
            memory = self.memory_updater.update(memory, section, draft)
            await self.persist_memory(memory)
            accepted.append(draft); reviews.append(review)
        await self._ensure_not_cancelled()
        await self.update_stage("writing", 68, "Generating conclusion and practical sections", len(plan.sections))
        faq_text = await self.supplement_writer.generate(plan, memory, "faq")
        payload = {
            "conclusion": await self.supplement_writer.generate(plan, memory, "conclusion"),
            "FAQ": self._parse_faq(faq_text),
            "common_mistakes": await self.supplement_writer.generate(plan, memory, "common_mistakes"),
            "applications": await self.supplement_writer.generate(plan, memory, "applications"),
        }
        await self._ensure_not_cancelled()
        await self.update_stage("final_review", 80, "Reviewing complete article", len(plan.sections))
        article_review = await self.article_reviewer.review(plan, memory, accepted, reviews, payload)
        await self.update_stage("editing", 87, "Editing accepted sections", len(plan.sections))
        edited = await self.final_editor.edit(plan, accepted, article_review, style)
        for section in edited:
            await self.persist_section(section, {"edited": True})
        await self._ensure_not_cancelled()
        await self.update_stage("quality_check", 93, "Running quality checks", len(plan.sections))
        critical = [issue.description for issue in article_review.findings if issue.severity == "critical"]
        report = self.quality_gate.evaluate(request, edited, payload, critical, all(review.passed for review in reviews))
        if not report.passed:
            raise PipelineQualityError("; ".join(key for key, value in report.checks.items() if not value))
        await self.update_stage("rendering", 97, "Rendering DOCX", len(plan.sections))
        article = {"title": request.title, "sections": [{"heading": section.heading, "content": section.content} for section in edited], **payload}
        document = self.renderer.generate(article)
        return PipelineResult(article=article, document=document.getvalue(), quality_report=report)

    async def _review_with_revisions(self, plan, section, draft, memory, style, progress):
        review = None
        for attempt in range(settings.ARTICLE_AGENT_MAX_SECTION_REVISIONS + 1):
            await self._ensure_not_cancelled()
            await self.update_stage("reviewing", progress + 3, f"Reviewing section {section.index + 1}", section.index)
            review = await self.reviewer.review(plan, section, draft, memory, style)
            if review.passed:
                return draft, review
            if attempt == settings.ARTICLE_AGENT_MAX_SECTION_REVISIONS:
                return draft, review
            await self.update_stage("revising", progress + 5, f"Revising section {section.index + 1}", section.index)
            draft = await self.reviser.revise(plan, section, draft, review, memory, style)
        raise AssertionError("unreachable")

    async def _ensure_not_cancelled(self) -> None:
        if await self.cancelled():
            raise PipelineCancelled()

    @staticmethod
    def _parse_faq(raw: str) -> list[dict[str, str]]:
        """Convert the bounded FAQ contract into the existing DOCX representation."""
        entries: list[dict[str, str]] = []
        question = ""
        for line in raw.splitlines():
            normalized = line.strip()
            lowered = normalized.casefold()
            if lowered.startswith("question:") or normalized.startswith("سوال:") or normalized.startswith("سؤال:"):
                question = normalized.split(":", 1)[1].strip()
            elif (lowered.startswith("answer:") or normalized.startswith("پاسخ:")) and question:
                entries.append({"question": question, "answer": normalized.split(":", 1)[1].strip()})
                question = ""
        return entries
