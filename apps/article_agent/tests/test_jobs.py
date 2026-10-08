from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.article_agent.models import Article, ArticleJob, JobStatus


class ArticleJobEndpointTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(username="owner", password="pass")
        self.other_user = get_user_model().objects.create_user(username="other", password="pass")
        self.client.force_login(self.user)

    @patch("apps.article_agent.presentation.web.views.generate_article_task.apply_async")
    def test_create_job_normalizes_keywords_and_returns_immediately(self, apply_async) -> None:
        apply_async.return_value.id = "task-1"
        response = self.client.post(
            reverse("article_job_create"),
            {"title": "AI in medicine", "word_count": 1200, "headings": ["Introduction", "Use cases"], "keywords": " AI - medicine - ai - "},
        )

        self.assertEqual(response.status_code, 201)
        job = ArticleJob.objects.get()
        self.assertEqual(job.article.keywords, ["AI", "medicine"])
        self.assertEqual(job.status, JobStatus.QUEUED)
        apply_async.assert_called_once()

    def test_other_user_cannot_read_or_download_job(self) -> None:
        article = Article.objects.create(owner=self.user, title="Private", word_count=1000, headings=["One"], keywords=[])
        job = ArticleJob.objects.create(article=article)
        self.client.force_login(self.other_user)

        self.assertEqual(self.client.get(reverse("article_job_status", args=[job.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("article_job_download", args=[job.pk])).status_code, 404)

    def test_queued_job_can_be_cancelled(self) -> None:
        article = Article.objects.create(owner=self.user, title="Cancel", word_count=1000, headings=["One"], keywords=[])
        job = ArticleJob.objects.create(article=article)

        response = self.client.post(reverse("article_job_cancel", args=[job.pk]))

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    def test_article_dashboard_has_accessible_modal_live_progress_and_empty_state(self) -> None:
        response = self.client.get(reverse("article_agent"))
        self.assertContains(response, 'id="article-modal"')
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, 'name="headings_text"')
        self.assertContains(response, 'setInterval(poll,3000)')

    @patch("apps.article_agent.presentation.web.views.generate_article_task.apply_async")
    def test_failed_job_can_be_retried_but_completed_job_cannot(self, apply_async) -> None:
        apply_async.return_value.id = "task-2"
        article = Article.objects.create(owner=self.user, title="Retry", word_count=1000, headings=["One"], keywords=[])
        job = ArticleJob.objects.create(article=article, status=JobStatus.FAILED)

        self.assertEqual(self.client.post(reverse("article_job_retry", args=[job.pk])).status_code, 200)
        job.status = JobStatus.COMPLETED
        job.save()
        self.assertEqual(self.client.post(reverse("article_job_retry", args=[job.pk])).status_code, 409)

    @patch("apps.article_agent.presentation.web.views.generate_article_task.apply_async")
    def test_retry_increments_execution_version_and_tasks_receive_it(self, apply_async) -> None:
        apply_async.return_value.id = "task-3"
        article = Article.objects.create(owner=self.user, title="Retry safely", word_count=1000, headings=["One"], keywords=[])
        job = ArticleJob.objects.create(article=article, status=JobStatus.FAILED, execution_version=4)
        response = self.client.post(reverse("article_job_retry", args=[job.pk]))
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.execution_version, 5)
        apply_async.assert_called_once_with(args=[job.pk, 5], queue="article_generation")
