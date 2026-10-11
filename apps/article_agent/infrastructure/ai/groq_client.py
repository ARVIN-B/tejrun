"""Groq-compatible model client with bounded routing and quota accounting."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.article_agent.infrastructure.rate_limit import (
    QuotaLimit,
    RateLimitExceeded,
    RateLimitPolicy,
    RedisGroqLimiter,
)

from autogen_core import CancellationToken
from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

logger = logging.getLogger(__name__)
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")


class ProviderRateLimitError(RuntimeError):
    """A real HTTP 429 returned by the provider, not a local limiter event."""

    def __init__(self, *, model: str, retry_after: int | None, detail: str) -> None:
        self.model, self.retry_after = model, retry_after
        super().__init__(
            f"provider_rate_limit:model={model}; retry-after: {retry_after or 0}; {detail}"
        )


class ProviderTransientError(RuntimeError):
    """A normalized timeout/5xx/provider-capacity error safe for job retry."""

    def __init__(self, *, model: str, detail: str) -> None:
        self.model = model
        super().__init__(f"provider_transient:model={model}; {detail}")


class ProviderEmptyResponseError(ProviderTransientError):
    """The provider completed a request but returned no usable text."""

    def __init__(self, *, model: str, finish_reason: str) -> None:
        super().__init__(
            model=model, detail=f"empty_response:finish_reason={finish_reason}"
        )


class ProviderContextLimitError(RuntimeError):
    """A request was rejected locally before it could exceed model context."""

    def __init__(
        self, *, model: str, operation: str, input_tokens: int, output_tokens: int
    ) -> None:
        self.model, self.operation = model, operation
        self.input_tokens, self.output_tokens = input_tokens, output_tokens
        self.context_window = settings.ARTICLE_AGENT_LLM_CONTEXT_WINDOW_TOKENS
        super().__init__(
            "provider_context_limit_prevented: "
            f"model={model}; operation={operation}; estimated_input_tokens={input_tokens}; "
            f"requested_output_tokens={output_tokens}; context_window_tokens={self.context_window}; "
            f"safety_tokens={settings.ARTICLE_AGENT_LLM_CONTEXT_SAFETY_TOKENS}. "
            "The request was not sent. Reduce context or split the operation."
        )


@dataclass(frozen=True, slots=True)
class ModelRoute:
    primary: str
    fallbacks: tuple[str, ...]
    review_model: str | None = None

    def candidates(self, operation: str) -> tuple[str, ...]:
        initial = (
            self.review_model
            if operation in {"section_review", "article_review", "format"}
            and self.review_model
            else self.primary
        )
        return tuple(dict.fromkeys((initial, self.primary, *self.fallbacks)))


def _positive_optional(value: Any, field_name: str) -> int | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer.")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return parsed


def _quota_from_config(raw: Mapping[str, Any], *, model: str) -> QuotaLimit:
    allowed = {"concurrency", "rpm", "tpm", "input_tpm", "output_tpm"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(
            f"Unsupported model quota fields for {model}: {', '.join(sorted(unknown))}"
        )
    return QuotaLimit(
        concurrency=_positive_optional(raw.get("concurrency"), "concurrency"),
        requests_per_window=_positive_optional(raw.get("rpm"), "rpm"),
        tokens_per_window=_positive_optional(raw.get("tpm"), "tpm"),
        input_tokens_per_window=_positive_optional(raw.get("input_tpm"), "input_tpm"),
        output_tokens_per_window=_positive_optional(
            raw.get("output_tpm"), "output_tpm"
        ),
    )


class GroqClient:
    """One job-scoped client; all created model/Redis clients close together."""

    def __init__(self) -> None:
        self.route = self._route_from_settings()
        self.model_limits = self._model_limits_from_settings()
        account = QuotaLimit(
            concurrency=settings.ARTICLE_AGENT_GROQ_CONCURRENCY,
            requests_per_window=settings.ARTICLE_AGENT_GROQ_REQUESTS_PER_MINUTE,
            tokens_per_window=settings.ARTICLE_AGENT_GROQ_TOKENS_PER_MINUTE,
            input_tokens_per_window=settings.ARTICLE_AGENT_GROQ_INPUT_TOKENS_PER_MINUTE,
            output_tokens_per_window=settings.ARTICLE_AGENT_GROQ_OUTPUT_TOKENS_PER_MINUTE,
        ).with_margin(settings.ARTICLE_AGENT_GROQ_SAFETY_MARGIN)
        self.limiter = RedisGroqLimiter.from_url(
            settings.REDIS_URL,
            RateLimitPolicy(
                account=account,
                model_limits={
                    model: quota.with_margin(settings.ARTICLE_AGENT_GROQ_SAFETY_MARGIN)
                    for model, quota in self.model_limits.items()
                },
                lease_seconds=settings.ARTICLE_AGENT_GROQ_LEASE_SECONDS,
                key_prefix=(
                    f"article-agent:groq:{settings.ARTICLE_AGENT_GROQ_QUOTA_NAMESPACE}"
                ),
            ),
        )
        self._model_clients: dict[object, OpenAIChatCompletionClient] = {}

    @staticmethod
    def _route_from_settings() -> ModelRoute:
        primary = settings.ARTICLE_AGENT_PRIMARY_MODEL
        configured = (primary, *settings.ARTICLE_AGENT_FALLBACK_MODELS)
        if any(not _MODEL_NAME.fullmatch(model) for model in configured):
            raise ValueError(
                "Article Agent model names contain unsupported characters."
            )
        fallbacks = tuple(
            model
            for model in settings.ARTICLE_AGENT_FALLBACK_MODELS
            if model != primary
        )
        if len(set(fallbacks)) != len(fallbacks):
            raise ValueError(
                "ARTICLE_AGENT_FALLBACK_MODELS must not contain duplicates."
            )
        review_model = settings.ARTICLE_AGENT_REVIEW_MODEL or None
        if review_model and review_model not in {primary, *fallbacks}:
            raise ValueError(
                "ARTICLE_AGENT_REVIEW_MODEL must be the primary or a configured fallback model."
            )
        return ModelRoute(
            primary=primary, fallbacks=fallbacks, review_model=review_model
        )

    @staticmethod
    def _model_limits_from_settings() -> dict[str, QuotaLimit]:
        result: dict[str, QuotaLimit] = {}
        for model, raw in settings.ARTICLE_AGENT_GROQ_MODEL_LIMITS.items():
            if not isinstance(model, str) or not _MODEL_NAME.fullmatch(model):
                raise ValueError(
                    "ARTICLE_AGENT_GROQ_MODEL_LIMITS contains an invalid model name."
                )
            if not isinstance(raw, Mapping):
                raise ValueError(f"Quota configuration for {model} must be an object.")
            result[model] = _quota_from_config(raw, model=model)
        return result

    def _client_for(
        self, model: str, *, credential_slot: int = 1
    ) -> OpenAIChatCompletionClient:
        key = (model, credential_slot)
        # Compatibility for injected test adapters that use a model-only key.
        if key not in self._model_clients and model in self._model_clients:
            return self._model_clients[model]
        if key not in self._model_clients:
            environment_key = "LLM_API_KEY_2" if credential_slot == 2 else "LLM_API_KEY"
            api_key = os.getenv(environment_key)
            if not api_key:
                raise RuntimeError(
                    f"provider_credential_missing: credential_slot={credential_slot}; "
                    f"environment_variable={environment_key}"
                )
            self._model_clients[key] = OpenAIChatCompletionClient(
                model=model,
                api_key=api_key,
                base_url=os.getenv("LLM_BASE_URL"),
                model_info={
                    "vision": False,
                    "function_calling": False,
                    "json_output": False,
                    "family": "unknown",
                    "structured_output": False,
                },
                max_tokens=settings.ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS,
            )
        return self._model_clients[key]

    @staticmethod
    def _secondary_credential_available() -> bool:
        return (
            settings.ARTICLE_AGENT_ENABLE_SECONDARY_API_KEY_FALLBACK
            and bool(os.getenv("LLM_API_KEY_2"))
        )

    @staticmethod
    def estimate_input_tokens(prompt: str) -> int:
        """Use UTF-8 bytes/2 as a conservative model-agnostic estimate.

        Actual usage reconciles successful calls. Failed calls keep the full
        reservation because the provider may already have consumed it.
        """
        return max(1, math.ceil(len(prompt.encode("utf-8")) / 2))

    @staticmethod
    def _usage(result: Any) -> tuple[int, int] | None:
        usage = getattr(result, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            return prompt_tokens, completion_tokens
        return None

    @staticmethod
    def _headers(error: Exception) -> Mapping[str, str]:
        response = getattr(error, "response", None)
        headers = (
            getattr(response, "headers", None) or getattr(error, "headers", None) or {}
        )
        return headers if isinstance(headers, Mapping) else {}

    @classmethod
    def _status(cls, error: Exception) -> int | None:
        response = getattr(error, "response", None)
        status = getattr(error, "status_code", None) or getattr(
            response, "status_code", None
        )
        return status if isinstance(status, int) else None

    @classmethod
    def _retry_after(cls, error: Exception) -> int | None:
        raw = cls._headers(error).get("retry-after")
        try:
            return max(1, int(float(raw))) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_transient(cls, error: Exception) -> bool:
        if isinstance(error, ProviderTransientError):
            return True
        status = cls._status(error)
        if status in {429, 498} or (status is not None and 500 <= status < 600):
            return True
        return isinstance(error, (TimeoutError, asyncio.TimeoutError))

    def _can_fallback(self, error: Exception) -> bool:
        if isinstance(error, RateLimitExceeded):
            return error.cause.startswith("model_")
        status = self._status(error)
        if status == 429:
            return settings.ARTICLE_AGENT_FALLBACK_ON_PROVIDER_429
        return (
            self._is_transient(error)
            and settings.ARTICLE_AGENT_FALLBACK_ON_TRANSIENT_FAILURES
        )

    async def _reserve_with_retry(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        model: str,
    ):
        max_retries = 3

        for attempt in range(max_retries + 1):
            try:
                return await self.limiter.reserve(
                    input_tokens,
                    output_tokens,
                    model=model,
                )
            except RateLimitExceeded as error:
                # محدودیت حساب با عوض کردن مدل حل نمی‌شود.
                if not error.cause.startswith("account_"):
                    raise

                if attempt >= max_retries:
                    raise

                delay = error.retry_after + 1

                logger.warning(
                    "Local rate limit reached: cause=%s; "
                    "retry_in=%s seconds; attempt=%s/%s",
                    error.cause,
                    delay,
                    attempt + 1,
                    max_retries,
                )

                await asyncio.sleep(delay)

        raise RuntimeError("Rate-limit retry loop ended unexpectedly.")

    def _quota_output_ceiling(self, input_tokens: int, model: str) -> int | None:
        """Maximum output that can ever fit one local reservation.

        This is distinct from remaining capacity in the current minute: the
        Redis reservation still decides that and may return RateLimitExceeded.
        Here we only avoid an impossible per-call ReservationTooLarge error.
        """
        policy = getattr(self.limiter, "policy", None)
        if policy is None:
            return None
        quotas = (policy.account, policy.model_limit_for(model))
        ceilings: list[int] = []
        for quota in quotas:
            if quota.tokens_per_window:
                ceilings.append(quota.tokens_per_window - input_tokens)
            if quota.input_tokens_per_window and input_tokens > quota.input_tokens_per_window:
                return 0
            if quota.output_tokens_per_window:
                ceilings.append(quota.output_tokens_per_window)
        return min(ceilings) if ceilings else None

    async def generate(
        self,
        prompt: str,
        *,
        operation: str = "writing",
        output_tokens: int | None = None,
        _credential_slot: int = 1,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Refusing to send an empty provider prompt.")
        output_tokens = output_tokens or settings.ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS
        output_tokens = min(
            settings.ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS, max(1, output_tokens)
        )
        input_tokens = self.estimate_input_tokens(prompt)
        candidates = self.route.candidates(operation)
        if (
            input_tokens
            + output_tokens
            + settings.ARTICLE_AGENT_LLM_CONTEXT_SAFETY_TOKENS
            > settings.ARTICLE_AGENT_LLM_CONTEXT_WINDOW_TOKENS
        ):
            raise ProviderContextLimitError(
                model=candidates[0],
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        last_error: Exception | None = None
        for index, model in enumerate(candidates):
            quota_ceiling = self._quota_output_ceiling(input_tokens, model)
            if quota_ceiling is not None:
                if quota_ceiling < 1:
                    raise RuntimeError(
                        "provider_quota_input_too_large: "
                        f"model={model}; operation={operation}; estimated_input_tokens={input_tokens}; "
                        "the configured one-minute token quota cannot fit the prompt. "
                        "Context compaction must be increased or the configured quota must be corrected."
                    )
                if output_tokens > quota_ceiling:
                    logger.info(
                        "Reducing Article Agent completion reservation for model=%s operation=%s from=%s to=%s to fit configured TPM.",
                        model,
                        operation,
                        output_tokens,
                        quota_ceiling,
                    )
                    output_tokens = quota_ceiling
            for empty_attempt in range(
                settings.ARTICLE_AGENT_EMPTY_RESPONSE_RETRIES + 1
            ):
                reservation = None
                try:
                    # reservation = await self.limiter.reserve(
                    #     input_tokens, output_tokens, model=model
                    # )
                    reservation = await self._reserve_with_retry(
                        input_tokens,
                        output_tokens,
                        model=model,
                    )
                    
                    
                    result = await asyncio.wait_for(
                        self._client_for(
                            model, credential_slot=_credential_slot
                        ).create(
                            messages=[UserMessage(content=prompt, source="user")],
                            # extra_create_args={"max_tokens": output_tokens},
                            extra_create_args={
                                "max_tokens": output_tokens,
                                "reasoning_effort": "low",  # ← این خط را اضافه کن
                            },
                            cancellation_token=CancellationToken(),
                        ),
                        timeout=settings.ARTICLE_AGENT_LLM_TIMEOUT_SECONDS,
                    )
                    usage = self._usage(result)
                    if usage is None:
                        # The configured bound remains reserved when usage metadata
                        # is unavailable; do not optimistically free quota.
                        await self.limiter.release(reservation)
                    else:
                        await self.limiter.settle(
                            reservation,
                            actual_input_tokens=usage[0],
                            actual_output_tokens=usage[1],
                        )
                    content = result.content
                    if not isinstance(content, str) or not content.strip():
                        raise ProviderEmptyResponseError(
                            model=model,
                            finish_reason=str(
                                getattr(result, "finish_reason", "unknown")
                            ),
                        )
                    if index:
                        logger.warning(
                            "Article Agent selected fallback model=%s operation=%s reason=%s",
                            model,
                            operation,
                            (
                                type(last_error).__name__
                                if last_error
                                else "configured_route"
                            ),
                        )
                    else:
                        logger.info(
                            "Article Agent selected model=%s operation=%s",
                            model,
                            operation,
                        )
                    return content
                except asyncio.CancelledError:
                    if reservation is not None:
                        await self.limiter.release(reservation)
                    raise
                except Exception as error:
                    if reservation is not None and not reservation.released:
                        await self.limiter.release(reservation)
                    last_error = error
                    if (
                        isinstance(error, ProviderEmptyResponseError)
                        and empty_attempt
                        < settings.ARTICLE_AGENT_EMPTY_RESPONSE_RETRIES
                    ):
                        logger.warning(
                            "Article Agent received an empty provider response; retrying model=%s operation=%s",
                            model,
                            operation,
                        )
                        continue
                    if (
                        self._status(error) == 429
                        and _credential_slot == 1
                        and self._secondary_credential_available()
                    ):
                        logger.warning(
                            "Provider HTTP 429 for model=%s operation=%s; retrying once with credential_slot=2.",
                            model,
                            operation,
                        )
                        return await self.generate(
                            prompt,
                            operation=operation,
                            output_tokens=output_tokens,
                            _credential_slot=2,
                        )
                    if index + 1 < len(candidates) and self._can_fallback(error):
                        logger.warning(
                            "Article Agent fallback candidate after model=%s operation=%s reason=%s",
                            model,
                            operation,
                            type(error).__name__,
                        )
                        break

                    if self._status(error) == 429:
                        headers = self._headers(error)

                        # فقط هدرهای مرتبط با محدودیت و شناسه درخواست
                        rate_limit_headers = {
                            key: value
                            for key, value in headers.items()
                            if (
                                "ratelimit" in key.lower()
                                or key.lower() == "retry-after"
                                or "request-id" in key.lower()
                            )
                        }

                        response = getattr(error, "response", None)
                        body = getattr(error, "body", None)

                        # تلاش برای خواندن بدنه پاسخ در صورت در دسترس نبودن error.body
                        if body is None and response is not None:
                            try:
                                body = response.text
                            except Exception:
                                body = None

                        logger.warning(
                            "Groq 429 diagnostics: model=%s operation=%s "
                            "retry_after=%s headers=%s body=%r",
                            model,
                            operation,
                            self._retry_after(error),
                            rate_limit_headers,
                            str(body)[:2000] if body is not None else None,
                        )

                        raise ProviderRateLimitError(
                            model=model,
                            retry_after=self._retry_after(error),
                            detail=(
                                f"{type(error).__name__}: "
                                f"{str(body or error)[:2_000]}"
                            ),
                        ) from error

                    if self._is_transient(error):
                        if isinstance(error, ProviderTransientError):
                            raise
                        raise ProviderTransientError(
                            model=model,
                            detail=f"{type(error).__name__}: {str(error)[:2_000]}",
                        ) from error
                    raise
        raise AssertionError("Model route produced no candidates.")

    async def close(self) -> None:
        try:
            await asyncio.gather(
                *(client.close() for client in set(self._model_clients.values()))
            )
        finally:
            await self.limiter.close()
