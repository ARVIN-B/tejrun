"""Bounded generation and deterministic fallback for web SEO metadata."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.conf import settings

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.services import TextGenerator
from apps.article_agent.domain import ArticlePlan, SectionDraft


class SeoMetadataService:
    def __init__(self, llm: TextGenerator, context_builder: ContextBuilder) -> None:
        self.llm, self.context_builder = llm, context_builder

    async def generate(self, plan: ArticlePlan, sections: list[SectionDraft], opinions: list[Any]) -> dict[str, Any]:
        context = self.context_builder._bounded_json({
            "article": self.context_builder._article_metadata(plan),
            "section_summaries": [{"heading": item.heading, "excerpt": item.content[:300]} for item in sections],
            "seo_findings": [finding.recommendation for opinion in opinions if opinion.role == "seo" for finding in opinion.findings][:5],
        }, self.context_builder.limit_for_output_tokens(settings.ARTICLE_AGENT_METADATA_MAX_OUTPUT_TOKENS, self.context_builder.budgets.memory_context_limit))
        prompt = (
            "برای انتشار وب فارسی، فقط یک JSON object با کلیدهای meta_title و meta_description بده. "
            "هر دو طبیعی، دقیق، بدون HTML/Markdown و بدون keyword stuffing باشند. نام برند را فقط اگر طبیعی و مفید است بیاور. "
            f"meta_title حداکثر {settings.ARTICLE_AGENT_META_TITLE_MAX_LENGTH} نویسه و meta_description حداکثر "
            f"{settings.ARTICLE_AGENT_META_DESCRIPTION_MAX_LENGTH} نویسه باشد. از ادعا یا واقعیت خارج از CONTEXT خودداری کن.\n\nCONTEXT:\n{context}"
        )
        try:
            raw = await self.llm.generate(prompt, operation="seo_metadata", output_tokens=settings.ARTICLE_AGENT_METADATA_MAX_OUTPUT_TOKENS)
            metadata = self._validate(raw)
            return {**metadata, "source": "generated", "validation": self._lengths(metadata)}
        except Exception as error:
            logging.getLogger(__name__).warning("SEO metadata fallback used: %s", error)
            metadata = self._fallback(plan)
            return {**metadata, "source": "fallback", "warning": f"metadata_generation_failed:{type(error).__name__}", "validation": self._lengths(metadata)}

    @staticmethod
    def _clean(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("metadata_values_must_be_strings")
        value = re.sub(r"<[^>]+>", "", value)
        value = re.sub(r"[`*_#]", "", value)
        return " ".join(value.split())

    def _validate(self, raw: str) -> dict[str, str]:
        text = raw.strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("metadata_json_missing")
        data = json.loads(text[start:end + 1])
        title, description = self._clean(data.get("meta_title")), self._clean(data.get("meta_description"))
        if not title or not description:
            raise ValueError("metadata_values_empty")
        if len(title) > settings.ARTICLE_AGENT_META_TITLE_MAX_LENGTH or len(description) > settings.ARTICLE_AGENT_META_DESCRIPTION_MAX_LENGTH:
            raise ValueError("metadata_length_exceeded")
        return {"meta_title": title, "meta_description": description}

    @staticmethod
    def _fallback(plan: ArticlePlan) -> dict[str, str]:
        suffix = f" | {plan.brand_name}" if plan.brand_name else ""
        title = (plan.title + suffix)[:settings.ARTICLE_AGENT_META_TITLE_MAX_LENGTH].rstrip(" ،|-:")
        keyword_text = "، ".join(plan.keywords[:3])
        description = f"راهنمای {plan.title}"
        if keyword_text:
            description += f"؛ نکات کلیدی: {keyword_text}"
        if plan.brand_name:
            description += f"؛ {plan.brand_name}"
        return {"meta_title": title, "meta_description": description[:settings.ARTICLE_AGENT_META_DESCRIPTION_MAX_LENGTH].rstrip(" ،|-:")}

    @staticmethod
    def _lengths(metadata: dict[str, str]) -> dict[str, int]:
        return {"title_length": len(metadata["meta_title"]), "description_length": len(metadata["meta_description"])}
