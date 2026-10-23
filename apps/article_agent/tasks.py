import logging
import random
import re

from billiard.exceptions import SoftTimeLimitExceeded
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
        # Transient failures without a provider/local quota deadline use
        # bounded exponential backoff.  A concrete Retry-After below still
        # takes precedence when it is longer than this baseline.
        floor = delay * (2 ** max(0, retry_number))
    match = re.search(r"retry[- ]after[^0-9]*(\d+)", str(error), flags=re.IGNORECASE)
    if match:
        floor = max(floor, int(match.group(1)))
    # Break synchronized retries across workers while respecting Retry-After.
    return floor + random.randint(0, max(1, floor // 5))


@shared_task(
    bind=True,
    autoretry_for=(),
    queue="article_generation",
    soft_time_limit=settings.ARTICLE_AGENT_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.ARTICLE_AGENT_TASK_TIME_LIMIT,
)
def generate_article_task(self, job_id: int) -> None:
    """Execute one persisted job. Broker contract: exactly one ``job_id``."""
    task_id = self.request.id
    try:
        ArticleJobExecutionService().execute(job_id, task_id=task_id)
    except SoftTimeLimitExceeded as error:
        retry_limit = settings.ARTICLE_AGENT_SOFT_TIME_LIMIT_MAX_RETRIES
        if self.request.retries < retry_limit:
            countdown = settings.ARTICLE_AGENT_SOFT_TIME_LIMIT_RETRY_DELAY_SECONDS
            ArticleJob.objects.filter(pk=job_id, celery_task_id=task_id).update(
                status=JobStatus.QUEUED,
                current_stage="Time limit reached; resuming from checkpoint",
                retry_count=self.request.retries + 1,
                error_code="",
                error_message="",
                updated_at=timezone.now(),
            )
            logger.warning(
                "Article job %s reached Celery soft time limit after %s seconds; "
                "retrying from its persisted checkpoint in %s seconds "
                "(attempt %s/%s).",
                job_id,
                settings.ARTICLE_AGENT_TASK_SOFT_TIME_LIMIT,
                countdown,
                self.request.retries + 1,
                retry_limit,
            )
            raise self.retry(
                exc=error,
                countdown=countdown,
                max_retries=retry_limit,
            )

        detail = (
            "The article exceeded Celery's soft execution limit "
            f"({settings.ARTICLE_AGENT_TASK_SOFT_TIME_LIMIT} seconds) "
            f"after {retry_limit} resumable attempts."
        )
        logger.exception("Article job %s exhausted soft-time-limit retries: %s", job_id, detail)
        ArticleJob.objects.filter(pk=job_id, celery_task_id=task_id).update(
            status=JobStatus.FAILED,
            current_stage="Failed after repeated execution time limits",
            error_code="soft_time_limit_exhausted",
            error_message=detail[:500],
            updated_at=timezone.now(),
        )
        raise
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
