"""Application service executed by a Celery adapter, never by a web view."""
import asyncio

from django.core.files.base import ContentFile
from django.utils import timezone

from apps.article_agent.application.planning import ArticlePlanner
from apps.article_agent.application.use_cases.generate_article import ArticleGenerator
from apps.article_agent.domain import ArticleRequest
from apps.article_agent.domain.serialization import article_plan_to_dict
from apps.article_agent.infrastructure.document.docx_generator import DocxGenerator
from apps.article_agent.models import ArticleJob, ArticleSection, JobStatus


class ArticleJobExecutionService:
    def execute(self, job_id: int) -> None:
        job = ArticleJob.objects.select_related("article").get(pk=job_id)
        if job.status in {JobStatus.CANCELLED, JobStatus.COMPLETED}:
            return
        job.started_at = job.started_at or timezone.now()
        job.update_progress(JobStatus.PLANNING, 10, "Planning article")
        article = job.article
        request = ArticleRequest(title=article.title, word_count=article.word_count, headings=article.headings, keywords=article.keywords, language=article.language)
        plan = ArticlePlanner().create_plan(request)
        job.plan_payload, job.total_sections = article_plan_to_dict(plan), len(plan.sections)
        job.save(update_fields=["plan_payload", "total_sections", "started_at", "updated_at"])
        if self._cancelled(job.pk): return
        job.update_progress(JobStatus.WRITING, 20, "Writing article")
        payload = {"title": article.title, "word_count": article.word_count, "keywords": article.keywords, "sections": [{"heading": item.heading, "content": ""} for item in plan.sections], "conclusion": "", "FAQ": [{"question": "", "answer": ""} for _ in range(4)], "common_mistakes": "", "applications": ""}
        final_article = asyncio.run(ArticleGenerator().generate(payload))
        if self._cancelled(job.pk): return
        for position, section in enumerate(final_article["sections"]):
            ArticleSection.objects.update_or_create(article=article, position=position, defaults={"heading": section["heading"], "content": section.get("content", "")})
        job.current_section = len(plan.sections)
        job.update_progress(JobStatus.RENDERING, 95, "Rendering DOCX")
        document = DocxGenerator().generate(final_article)
        job.output_file.save(f"article-{article.pk}.docx", ContentFile(document.getvalue()), save=False)
        job.save(update_fields=["output_file", "current_section", "updated_at"])
        job.mark_completed()

    @staticmethod
    def _cancelled(job_id: int) -> bool:
        job = ArticleJob.objects.only("status").get(pk=job_id)
        if job.status != JobStatus.CANCEL_REQUESTED: return False
        job.status, job.current_stage = JobStatus.CANCELLED, "Cancelled"
        job.save(update_fields=["status", "current_stage", "updated_at"])
        return True
