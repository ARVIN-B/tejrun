import logging
import re

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.article_agent.application.job_execution import ArticleJobExecutionService
from apps.article_agent.models import ArticleJob, JobStatus

logger = logging.getLogger(__name__)


def _is_rate_limited(error: Exception) -> bool:
    text = str(error).lower()
    return "ratelimit" in error.__class__.__name__.lower() or "429" in text or "rate limit" in text


def _is_transient_provider_error(error: Exception) -> bool:
    text = str(error).lower()
    return _is_rate_limited(error) or isinstance(error, TimeoutError) or any(
        phrase in text for phrase in ("timeout", "temporarily unavailable", "connection reset", "connection error")
    )


def _retry_delay(error: Exception, retry_number: int) -> int:
    delay = settings.ARTICLE_AGENT_RETRY_BACKOFF_SECONDS * (2 ** retry_number)
    match = re.search(r"retry[- ]after[^0-9]*(\d+)", str(error), flags=re.IGNORECASE)
    return max(delay, int(match.group(1))) if match else delay


@shared_task(bind=True, autoretry_for=(), queue="article_generation")
def generate_article_task(self, job_id: int) -> None:
    try:
        ArticleJobExecutionService().execute(job_id)
    except Exception as error:
        if _is_transient_provider_error(error) and self.request.retries < settings.ARTICLE_AGENT_MAX_RETRIES:
            ArticleJob.objects.filter(pk=job_id).update(status=JobStatus.QUEUED, current_stage="Waiting to retry after provider rate limit", retry_count=self.request.retries + 1, updated_at=timezone.now())
            countdown = _retry_delay(error, self.request.retries)
            logger.warning("Article job %s has a transient provider failure; retrying in %s seconds", job_id, countdown)
            raise self.retry(exc=error, countdown=countdown, max_retries=settings.ARTICLE_AGENT_MAX_RETRIES)
        logger.exception("Article job %s failed", job_id)
        ArticleJob.objects.filter(pk=job_id).update(status=JobStatus.FAILED, current_stage="Failed", error_code="provider_error" if _is_transient_provider_error(error) else "generation_error", error_message="Article generation encountered a temporary problem. Please retry.", updated_at=timezone.now())
        raise
