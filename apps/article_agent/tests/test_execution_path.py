import tempfile
from io import BytesIO
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings

from apps.article_agent.application.article_pipeline import PipelineResult
from apps.article_agent.application.job_execution import ArticleJobExecutionService
from apps.article_agent.domain import QualityReport
from apps.article_agent.models import Article, ArticleJob, JobStatus
from apps.article_agent.tasks import _is_rate_limited, _is_transient_provider_error, _retry_delay, generate_article_task


class ExecutionPathTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        user = get_user_model().objects.create_user(username="pipeline-owner", password="pass")
        article = Article.objects.create(owner=user, title="Pipeline title", word_count=100, headings=["Heading"], keywords=[])
        self.job = ArticleJob.objects.create(article=article)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch("apps.article_agent.application.job_execution.GroqClient")
    @patch("apps.article_agent.application.job_execution.ArticlePipeline")
    def test_execution_service_uses_article_pipeline_and_marks_job_completed(self, pipeline_class, client_class) -> None:
        client_class.return_value.close = AsyncMock()
        pipeline = pipeline_class.return_value
        pipeline.run = AsyncMock(return_value=PipelineResult(
            article={"title": "Pipeline title", "sections": [{"heading": "Heading", "content": "content"}], "conclusion": "end", "FAQ": [], "common_mistakes": "mistakes", "applications": "uses"},
            document=b"docx", quality_report=QualityReport(True, 100, 100, 0.25),
        ))

        ArticleJobExecutionService().execute(self.job.pk)

        self.job.refresh_from_db()
        pipeline.run.assert_awaited_once()
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertTrue(self.job.output_file.name)

    @patch("apps.article_agent.tasks.ArticleJobExecutionService.execute")
    def test_celery_task_invokes_execution_service(self, execute) -> None:
        generate_article_task.apply(args=(self.job.pk,)).get()
        execute.assert_called_once_with(self.job.pk, self.job.execution_version)

    @patch("apps.article_agent.application.job_execution.GroqClient")
    @patch("apps.article_agent.application.job_execution.ArticlePipeline")
    def test_duplicate_execution_version_is_claimed_once(self, pipeline_class, client_class) -> None:
        client_class.return_value.close = AsyncMock()
        pipeline_class.return_value.run = AsyncMock(return_value=PipelineResult(
            article={"title": "Pipeline title", "sections": [], "conclusion": "end", "FAQ": [], "common_mistakes": "mistakes", "applications": "uses"},
            document=b"docx", quality_report=QualityReport(True, 100, 100, 0.25),
        ))
        service = ArticleJobExecutionService()
        service.execute(self.job.pk, self.job.execution_version)
        service.execute(self.job.pk, self.job.execution_version)
        pipeline_class.return_value.run.assert_awaited_once()

    def test_stale_execution_cannot_update_current_job_stage(self) -> None:
        self.job.execution_version = 2
        self.job.save(update_fields=["execution_version"])
        import asyncio
        asyncio.run(ArticleJobExecutionService._update_stage(self.job.pk, 1, JobStatus.WRITING, 50, "stale", 0))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.QUEUED)

    def test_edit_checkpoint_keeps_the_accepted_review_marker_for_resume(self) -> None:
        import asyncio
        service = ArticleJobExecutionService()
        draft = type("Draft", (), {"section_index": 0, "heading": "Heading", "content": "accepted content"})()
        asyncio.run(service._persist_section(self.job.pk, self.job.execution_version, self.job.article_id, draft, {"passed": True}))
        asyncio.run(service._persist_section(self.job.pk, self.job.execution_version, self.job.article_id, draft, {"edited": True}))
        row = self.job.article.sections.get(position=0)
        self.assertEqual(row.review_payload, {"passed": True, "edited": True})

    def test_job_state_machine_rejects_illegal_terminal_resurrection(self) -> None:
        self.assertTrue(JobStatus.can_transition(JobStatus.QUEUED, JobStatus.PLANNING))
        self.assertTrue(JobStatus.can_transition(JobStatus.WRITING, JobStatus.CANCEL_REQUESTED))
        self.assertFalse(JobStatus.can_transition(JobStatus.COMPLETED, JobStatus.WRITING))

    def test_rate_limit_classifier_detects_429(self) -> None:
        self.assertTrue(_is_rate_limited(RuntimeError("HTTP 429 rate limit")))
        self.assertFalse(_is_rate_limited(RuntimeError("invalid request")))

    @override_settings(ARTICLE_AGENT_RETRY_BACKOFF_SECONDS=10)
    @patch("apps.article_agent.tasks.random.randint", return_value=3)
    def test_transient_errors_use_jittered_provider_aware_backoff(self, randint) -> None:
        error = TimeoutError("retry-after: 45")
        self.assertTrue(_is_transient_provider_error(error))
        self.assertEqual(_retry_delay(error, 0), 48)
        self.assertEqual(_retry_delay(RuntimeError("429"), 2), 43)
        self.assertEqual(randint.call_count, 2)
