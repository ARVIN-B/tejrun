"""Django persistence adapter around the asynchronous ArticlePipeline."""

import asyncio
from dataclasses import asdict

from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.db import connections
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
from apps.article_agent.models import ArticleJob, ArticleSection, JobStatus


class ArticleJobExecutionService:
    """The sole controlled sync/async boundary used by the Celery task."""

    def execute(self, job_id: int) -> None:
        asyncio.run(self._execute(job_id))

    async def _execute(self, job_id: int) -> None:
        job = await sync_to_async(ArticleJob.objects.select_related("article").get)(pk=job_id)
        if job.status in {JobStatus.CANCELLED, JobStatus.COMPLETED}:
            return
        if job.status == JobStatus.CANCEL_REQUESTED:
            await self._mark_cancelled(job_id)
            return
        await self._mark_started(job_id)
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
        try:
            pipeline = ArticlePipeline(
                planner=ArticlePlanner(), researcher=GroundingResearcher(),
                writer=SectionWriter(llm, context_builder), reviewer=SectionReviewer(llm, context_builder),
                reviser=RevisionService(llm, context_builder), memory_updater=MemoryUpdater(),
                article_reviewer=ArticleReviewer(llm, context_builder), final_editor=FinalEditor(llm, context_builder),
                supplement_writer=SupplementWriter(llm, context_builder), quality_gate=QualityGate(),
                renderer=DocxGenerator(), context_builder=context_builder,
                update_stage=lambda status, progress, stage, section: self._update_stage(job_id, status, progress, stage, section),
                persist_plan=lambda plan: self._persist_plan(job_id, plan),
                persist_section=lambda draft, review: self._persist_section(article.pk, draft, review),
                persist_memory=lambda updated: self._persist_memory(job_id, updated),
                cancelled=lambda: self._cancel_requested(job_id),
            )
            result = await pipeline.run(request, memory, completed_sections)
            if await self._cancel_requested(job_id):
                await self._mark_cancelled(job_id)
                return
            await self._persist_result(job_id, result.article, result.document, quality_report_to_dict(result.quality_report))
        except PipelineCancelled:
            await self._mark_cancelled(job_id)
        except PipelineQualityError:
            raise
        finally:
            await llm.close()
            # The Celery event-loop bridge uses a dedicated sync thread for ORM
            # calls. Close that thread's connection before the worker/task ends.
            await sync_to_async(connections.close_all, thread_sensitive=True)()

    @staticmethod
    async def _mark_started(job_id: int) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id).update)(started_at=timezone.now())

    @staticmethod
    async def _update_stage(job_id: int, status: str, progress: int, stage: str, section: int) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id).exclude(status=JobStatus.CANCEL_REQUESTED).update)(
            status=status, progress=progress, current_stage=stage, current_section=section, updated_at=timezone.now()
        )

    @staticmethod
    async def _persist_plan(job_id: int, plan) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id).update)(
            plan_payload=article_plan_to_dict(plan), total_sections=len(plan.sections), updated_at=timezone.now()
        )

    @staticmethod
    async def _persist_section(article_id: int, draft, review: dict) -> None:
        await sync_to_async(ArticleSection.objects.update_or_create)(
            article_id=article_id, position=draft.section_index,
            defaults={"heading": draft.heading, "content": draft.content, "review_payload": review},
        )

    @staticmethod
    async def _persist_memory(job_id: int, memory: ArticleMemory) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id).update)(
            memory_payload=asdict(memory), updated_at=timezone.now()
        )

    @staticmethod
    async def _cancel_requested(job_id: int) -> bool:
        job = await sync_to_async(ArticleJob.objects.only("status").get)(pk=job_id)
        return job.status == JobStatus.CANCEL_REQUESTED

    @staticmethod
    async def _mark_cancelled(job_id: int) -> None:
        await sync_to_async(ArticleJob.objects.filter(pk=job_id).update)(
            status=JobStatus.CANCELLED, current_stage="Cancelled", updated_at=timezone.now()
        )

    @staticmethod
    async def _persist_result(job_id: int, article: dict, document: bytes, report: dict) -> None:
        def save() -> None:
            job = ArticleJob.objects.get(pk=job_id)
            job.result_payload = {"article": article, "quality_report": report}
            job.output_file.save(f"article-{job.article_id}.docx", ContentFile(document), save=False)
            job.status, job.progress, job.current_stage, job.completed_at = JobStatus.COMPLETED, 100, "Completed", timezone.now()
            job.save(update_fields=["result_payload", "output_file", "status", "progress", "current_stage", "completed_at", "updated_at"])
        await sync_to_async(save, thread_sensitive=True)()
