import tempfile
from io import BytesIO
from unittest.mock import ANY, AsyncMock, patch

from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings

from apps.article_agent.application.article_pipeline import PipelineResult
from apps.article_agent.application.job_execution import ArticleJobExecutionService
from apps.article_agent.domain import QualityReport
from apps.article_agent.models import Article, ArticleJob, JobStatus
from apps.article_agent.tasks import _is_rate_limited, _is_transient_provider_error, _retry_delay, generate_article_task
from apps.article_agent.infrastructure.ai.groq_client import ProviderEmptyResponseError, ProviderRateLimitError
from apps.article_agent.infrastructure.rate_limit import RateLimitExceeded


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
    def test_celery_task_invokes_execution_service_with_job_id_only(self, execute) -> None:
        generate_article_task.apply(args=(self.job.pk,)).get()
        execute.assert_called_once_with(self.job.pk, task_id=ANY)

    def test_task_contract_has_exactly_one_broker_argument(self) -> None:
        import inspect
        parameters = list(inspect.signature(generate_article_task.run).parameters)
        # ``run`` is already bound by Celery, so ``self`` is not exposed to
        # callers. The broker contract is exactly one positional argument.
        self.assertEqual(parameters, ["job_id"])

    @override_settings(ARTICLE_AGENT_MAX_RETRIES=1)
    @patch("apps.article_agent.tasks.generate_article_task.retry", side_effect=Retry())
    @patch("apps.article_agent.tasks.ArticleJobExecutionService.execute", side_effect=TimeoutError("timeout"))
    def test_provider_retry_reuses_the_one_job_id_task_contract(self, execute, retry) -> None:
        self.job.celery_task_id = "retry-contract-task"
        self.job.save(update_fields=["celery_task_id"])
        generate_article_task.apply(args=(self.job.pk,), task_id="retry-contract-task")
        execute.assert_called_once_with(self.job.pk, task_id="retry-contract-task")
        self.assertEqual(retry.call_args.args, ())
        self.assertIn("countdown", retry.call_args.kwargs)

    @patch("apps.article_agent.application.job_execution.GroqClient")
    @patch("apps.article_agent.application.job_execution.ArticlePipeline")
    def test_duplicate_execution_version_is_claimed_once(self, pipeline_class, client_class) -> None:
        client_class.return_value.close = AsyncMock()
        pipeline_class.return_value.run = AsyncMock(return_value=PipelineResult(
            article={"title": "Pipeline title", "sections": [], "conclusion": "end", "FAQ": [], "common_mistakes": "mistakes", "applications": "uses"},
            document=b"docx", quality_report=QualityReport(True, 100, 100, 0.25),
        ))
        service = ArticleJobExecutionService()
        service.execute(self.job.pk)
        service.execute(self.job.pk)
        pipeline_class.return_value.run.assert_awaited_once()

    def test_stale_execution_cannot_update_current_job_stage(self) -> None:
        self.job.execution_version = 2
        self.job.save(update_fields=["execution_version"])
        import asyncio
        asyncio.run(ArticleJobExecutionService._update_stage(self.job.pk, 1, JobStatus.WRITING, 50, "stale", 0))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.QUEUED)

    def test_stale_celery_task_identity_cannot_claim_current_job(self) -> None:
        import asyncio
        self.job.celery_task_id = "current-task"
        self.job.save(update_fields=["celery_task_id"])
        claimed = asyncio.run(
            ArticleJobExecutionService._claim_execution(
                self.job.pk, self.job.execution_version, "stale-task"
            )
        )
        self.assertFalse(claimed)
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

    def test_local_limiter_and_provider_429_remain_distinct(self) -> None:
        local = RateLimitExceeded("model_tokens", 17)
        provider = ProviderRateLimitError(model="primary", retry_after=9, detail="Http429")
        self.assertTrue(_is_transient_provider_error(local))
        self.assertTrue(_is_transient_provider_error(provider))
        self.assertNotEqual(type(local), type(provider))

    def test_empty_provider_response_is_retryable_not_a_budget_acceptance(self) -> None:
        error = ProviderEmptyResponseError(model="primary", finish_reason="stop")
        self.assertTrue(_is_transient_provider_error(error))

    @override_settings(ARTICLE_AGENT_RETRY_BACKOFF_SECONDS=10)
    @patch("apps.article_agent.tasks.random.randint", return_value=3)
    def test_transient_errors_use_jittered_provider_aware_backoff(self, randint) -> None:
        error = TimeoutError("retry-after: 45")
        self.assertTrue(_is_transient_provider_error(error))
        self.assertEqual(_retry_delay(error, 0), 48)
        self.assertEqual(_retry_delay(RuntimeError("429"), 2), 43)
        self.assertEqual(randint.call_count, 2)

    @override_settings(ARTICLE_AGENT_RETRY_BACKOFF_SECONDS=60)
    @patch("apps.article_agent.tasks.random.randint", return_value=1)
    def test_limiter_retry_delay_uses_blocking_quota_time(self, _randint) -> None:
        self.assertEqual(_retry_delay(RateLimitExceeded("account_tokens", 11), 3), 12)
        self.assertEqual(
            _retry_delay(ProviderRateLimitError(model="primary", retry_after=7, detail="429"), 3), 8
        )
