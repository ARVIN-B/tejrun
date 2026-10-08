"""Django persistence adapter around the asynchronous ArticlePipeline."""

import asyncio
from dataclasses import asdict

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connections, transaction
from django.utils import timezone

from apps.article_agent.application.article_pipeline import (
    ArticlePipeline, PipelineCancelled, PipelineQualityError, QualityGate,
)
from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.memory import MemoryUpdater
from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.services import (
    ArticleReviewer, FinalEditor, GroundingResearcher, RevisionService,
    SectionReviewer, SectionWriter, SupplementWriter,
)
from apps.article_agent.domain import ArticleMemory, ArticleRequest, SectionDraft
from apps.article_agent.domain.serialization import article_plan_to_dict, quality_report_to_dict
from apps.article_agent.infrastructure.ai.groq_client import GroqClient
from apps.article_agent.infrastructure.document.docx_generator import DocxGenerator
from apps.article_agent.infrastructure.research import HttpResearchProvider
from apps.article_agent.models import ArticleJob, ArticleSection, JobStatus


class ArticleJobExecutionService:
    """The sole controlled sync/async boundary used by the Celery task."""

    def execute(self, job_id: int, execution_version: int | None = None) -> None:
        asyncio.run(self._execute(job_id, execution_version))

    async def _execute(self, job_id: int, expected_version: int | None) -> None:
        job = await sync_to_async(ArticleJob.objects.select_related("article").get)(pk=job_id)
        execution_version = expected_version if expected_version is not None else job.execution_version
        if not await self._claim_execution(job_id, execution_version):
            return
        job = await sync_to_async(ArticleJob.objects.select_related("article").get)(pk=job_id)
        article = job.article
        request = ArticleRequest(
            title=article.title, word_count=article.word_count, headings=article.headings,
            keywords=article.keywords, language=article.language,
        )
        memory = ArticleMemory(**{
            key: value for key, value in job.memory_payload.items()
            if key in ArticleMemory.__dataclass_fields__
        }).normalized()
        persisted_rows = await sync_to_async(list)(
            ArticleSection.objects.filter(article_id=article.pk).order_by("position")
        )
        completed_sections = {
            row.position: SectionDraft(row.position, row.heading, row.content)
            for row in persisted_rows if row.content and row.review_payload.get("passed")
        }
        llm = GroqClient()
        context_builder = ContextBuilder()
        http_research = HttpResearchProvider(timeout=settings.ARTICLE_AGENT_RESEARCH_TIMEOUT_SECONDS)
        try:
            pipeline = ArticlePipeline(
                planner=ArticlePlanner(), researcher=GroundingResearcher(
                    settings.ARTICLE_AGENT_RESEARCH_MODE, http_research if http_research.configured else None,
                ),
                writer=SectionWriter(llm, context_builder), reviewer=SectionReviewer(llm, context_builder),
                reviser=RevisionService(llm, context_builder), memory_updater=MemoryUpdater(),
                article_reviewer=ArticleReviewer(llm, context_builder), final_editor=FinalEditor(llm, context_builder),
                supplement_writer=SupplementWriter(llm, context_builder), quality_gate=QualityGate(),
                renderer=DocxGenerator(), context_builder=context_builder,
                update_stage=lambda status, progress, stage, section: self._update_stage(job_id, execution_version, status, progress, stage, section),
                persist_plan=lambda plan: self._persist_plan(job_id, execution_version, plan),
                persist_section=lambda draft, review: self._persist_section(job_id, execution_version, article.pk, draft, review),
                persist_memory=lambda updated: self._persist_memory(job_id, execution_version, updated),
                persist_checkpoint=lambda checkpoint: self._persist_checkpoint(job_id, execution_version, checkpoint),
                cancelled=lambda: self._cancel_requested(job_id, execution_version),
            )
            result = await pipeline.run(request, memory, completed_sections, job.checkpoint_payload)
            if await self._cancel_requested(job_id, execution_version):
                await self._mark_cancelled(job_id, execution_version)
                return
            await self._persist_result(job_id, execution_version, result.article, result.document, quality_report_to_dict(result.quality_report))
        except PipelineCancelled:
            await self._mark_cancelled(job_id, execution_version)
        except PipelineQualityError:
            raise
        finally:
            await llm.close()
            # The Celery event-loop bridge uses a dedicated sync thread for ORM
            # calls. Close that thread's connection before the worker/task ends.
            await sync_to_async(connections.close_all, thread_sensitive=True)()

    @staticmethod
    async def _claim_execution(job_id: int, execution_version: int) -> bool:
        def claim() -> bool:
            with transaction.atomic():
                job = ArticleJob.objects.select_for_update().get(pk=job_id)
                if job.execution_version != execution_version:
                    return False
                if job.status == JobStatus.CANCEL_REQUESTED:
                    job.status, job.current_stage = JobStatus.CANCELLED, "Cancelled"
                    job.save(update_fields=["status", "current_stage", "updated_at"])
                    return False
                if job.status != JobStatus.QUEUED:
                    return False
                job.status, job.current_stage, job.started_at = JobStatus.PLANNING, "Planning article", timezone.now()
                job.save(update_fields=["status", "current_stage", "started_at", "updated_at"])
                return True
        return await sync_to_async(claim, thread_sensitive=True)()

    @staticmethod
    async def _update_stage(job_id: int, execution_version: int, status: str, progress: int, stage: str, section: int) -> None:
        def update() -> None:
            with transaction.atomic():
                job = ArticleJob.objects.select_for_update().filter(pk=job_id, execution_version=execution_version).first()
                if not job or job.status == JobStatus.CANCEL_REQUESTED:
                    return
                if not JobStatus.can_transition(job.status, status):
                    raise RuntimeError(f"illegal_job_transition:{job.status}:{status}")
                job.status = status
                job.progress = max(job.progress, min(progress, 100))
                job.current_stage, job.current_section = stage, section
                job.save(update_fields=["status", "progress", "current_stage", "current_section", "updated_at"])
        await sync_to_async(update, thread_sensitive=True)()

    @staticmethod
    async def _persist_plan(job_id: int, execution_version: int, plan) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id, execution_version=execution_version).update)(
            plan_payload=article_plan_to_dict(plan), total_sections=len(plan.sections), updated_at=timezone.now()
        )

    @staticmethod
    async def _persist_section(job_id: int, execution_version: int, article_id: int, draft, review: dict) -> None:
        def persist() -> None:
            with transaction.atomic():
                if not ArticleJob.objects.filter(pk=job_id, execution_version=execution_version).exists():
                    return
                row, _created = ArticleSection.objects.get_or_create(
                    article_id=article_id, position=draft.section_index,
                    defaults={"heading": draft.heading, "content": draft.content,
                              "review_payload": review, "execution_version": execution_version},
                )
                if not _created:
                    row.heading, row.content = draft.heading, draft.content
                    row.review_payload = {**row.review_payload, **review}
                    row.execution_version = execution_version
                    row.save(update_fields=["heading", "content", "review_payload", "execution_version"])
        await sync_to_async(persist, thread_sensitive=True)()

    @staticmethod
    async def _persist_memory(job_id: int, execution_version: int, memory: ArticleMemory) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id, execution_version=execution_version).update)(
            memory_payload=asdict(memory), updated_at=timezone.now()
        )

    @staticmethod
    async def _persist_checkpoint(job_id: int, execution_version: int, checkpoint: dict) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id, execution_version=execution_version).update)(
            checkpoint_payload=checkpoint, updated_at=timezone.now()
        )

    @staticmethod
    async def _cancel_requested(job_id: int, execution_version: int) -> bool:
        job = await sync_to_async(ArticleJob.objects.only("status", "execution_version").get)(pk=job_id)
        return job.execution_version != execution_version or job.status == JobStatus.CANCEL_REQUESTED

    @staticmethod
    async def _mark_cancelled(job_id: int, execution_version: int) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id, execution_version=execution_version).update)(
            status=JobStatus.CANCELLED, current_stage="Cancelled", updated_at=timezone.now()
        )

    @staticmethod
    async def _persist_result(job_id: int, execution_version: int, article: dict, document: bytes, report: dict) -> None:
        def save() -> None:
            with transaction.atomic():
                job = ArticleJob.objects.select_for_update().get(pk=job_id)
                if job.execution_version != execution_version or job.status == JobStatus.CANCEL_REQUESTED:
                    return
                job.result_payload = {"article": article, "quality_report": report}
                job.output_file.save(f"article-{job.article_id}.docx", ContentFile(document), save=False)
                job.status, job.progress, job.current_stage, job.completed_at = JobStatus.COMPLETED, 100, "Completed", timezone.now()
                job.save(update_fields=["result_payload", "output_file", "status", "progress", "current_stage", "completed_at", "updated_at"])
        await sync_to_async(save, thread_sensitive=True)()
