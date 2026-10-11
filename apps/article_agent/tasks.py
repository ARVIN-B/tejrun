import logging
import random
import re

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.article_agent.application.job_execution import ArticleJobExecutionService
from apps.article_agent.infrastructure.ai.groq_client import (
    ProviderRateLimitError,
    ProviderTransientError,
)
from apps.article_agent.infrastructure.rate_limit import RateLimitExceeded
from apps.article_agent.models import ArticleJob, JobStatus

logger = logging.getLogger(__name__)


def _error_details(error: Exception, *, limit: int = 500) -> str:
    """Safe, actionable diagnostics for the dashboard and worker logs."""
    detail = " ".join(str(error).split()) or error.__class__.__name__
    return f"{error.__class__.__name__}: {detail}"[:limit]


def _is_rate_limited(error: Exception) -> bool:
    if isinstance(error, (RateLimitExceeded, ProviderRateLimitError)):
        return True
    text = str(error).lower()
    return (
        "ratelimit" in error.__class__.__name__.lower()
        or "429" in text
        or "rate limit" in text
    )


def _is_transient_provider_error(error: Exception) -> bool:
    if isinstance(
        error, (RateLimitExceeded, ProviderRateLimitError, ProviderTransientError)
    ):
        return True
    text = str(error).lower()
    return (
        _is_rate_limited(error)
        or isinstance(error, TimeoutError)
        or any(
            phrase in text
            for phrase in (
                "timeout",
                "temporarily unavailable",
                "connection reset",
                "connection error",
            )
        )
    )


def _retry_delay(error: Exception, retry_number: int) -> int:
    delay = settings.ARTICLE_AGENT_RETRY_BACKOFF_SECONDS
    if isinstance(error, RateLimitExceeded):
        # Local limiter times are derived from the blocking quota's lease or
        # fixed-window TTL, not the unrelated request-counter TTL.
        floor = error.retry_after
    elif isinstance(error, ProviderRateLimitError) and error.retry_after:
        # Provider Retry-After is authoritative when Groq actually returned 429.
        floor = error.retry_after
    else:
        floor = delay
    match = re.search(r"retry[- ]after[^0-9]*(\d+)", str(error), flags=re.IGNORECASE)
    if match:
        floor = max(floor, int(match.group(1)))
    # Break synchronized retries across workers while respecting Retry-After.
    return floor + random.randint(0, max(1, floor // 5))


@shared_task(bind=True, autoretry_for=(), queue="article_generation")
def generate_article_task(self, job_id: int) -> None:
    """Execute one persisted job. Broker contract: exactly one ``job_id``."""
    task_id = self.request.id
    try:
        ArticleJobExecutionService().execute(job_id, task_id=task_id)
    except Exception as error:
        if (
            _is_transient_provider_error(error)
            and self.request.retries < settings.ARTICLE_AGENT_MAX_RETRIES
        ):
            reason = (
                "internal quota"
                if isinstance(error, RateLimitExceeded)
                else (
                    "provider rate limit"
                    if isinstance(error, ProviderRateLimitError)
                    else "transient provider failure"
                )
            )
            ArticleJob.objects.filter(pk=job_id, celery_task_id=task_id).update(
                status=JobStatus.QUEUED,
                current_stage=f"Waiting to retry after {reason}",
                retry_count=self.request.retries + 1,
                updated_at=timezone.now(),
            )
            countdown = _retry_delay(error, self.request.retries)
            logger.warning(
                "Article job %s has %s; retrying in %s seconds; diagnostics=%s",
                job_id,
                reason,
                countdown,
                _error_details(error),
            )
            raise self.retry(
                exc=error,
                countdown=countdown,
                max_retries=settings.ARTICLE_AGENT_MAX_RETRIES,
            )
        logger.exception("Article job %s failed; diagnostics=%s", job_id, _error_details(error))
        ArticleJob.objects.filter(pk=job_id, celery_task_id=task_id).update(
            status=JobStatus.FAILED,
            current_stage="Failed",
            error_code=(
                "provider_error"
                if _is_transient_provider_error(error)
                else "generation_error"
            ),
            error_message=_error_details(error),
            updated_at=timezone.now(),
        )
        raise
