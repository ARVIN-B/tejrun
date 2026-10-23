"""Bounded, role-specific advisory reviews for the production pipeline.

The coordinator deliberately does not turn an LLM into an authority: it asks
for small JSON opinions, validates them against domain contracts, and exposes
only actionable findings to the application-owned revision flow.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from django.conf import settings

from apps.article_agent.application.context_builder import ContextBuilder
from apps.article_agent.application.services import TextGenerator
from apps.article_agent.application.word_budget import WordCounter
from apps.article_agent.domain import (
    ArticleMemory, ArticlePlan, ArticleReview, ResearchData, ReviewIssue,
    ReviewResult, SectionDraft, SectionPlan, SpecialistOpinion, StyleProfile,
)
from apps.article_agent.domain.serialization import (
    ContractValidationError, specialist_opinion_from_dict,
)


ROLE_PROMPTS: dict[str, str] = {
    "seo": """نقش: استراتژیست SEO فارسی با تمرکز بر intent، ساختار محتوا و اسنیپت.
بررسی کن: هم‌خوانی عنوان و headingها با intent؛ پوشش طبیعی کلیدواژه و مترادف؛
یکتایی هدف headingها؛ خوانایی برای جست‌وجو؛ خطر keyword stuffing؛ و سازگاری متا
با موضوع و برند. وعدهٔ رتبه، حجم جست‌وجو یا آمار بیرونیِ بدون داده نساز. محل دقیق
تغییر و سود آن برای کاربر جست‌وجو را بنویس؛ تکرار برند را پیشنهاد نده مگر مفید باشد.""",
    "persian_editor": """نقش: ویراستار حرفه‌ای فارسی برای متن آموزشی و فنیِ روان.
بررسی کن: املا، نیم‌فاصله و نشانه‌گذاری؛ جملهٔ ترجمه‌زده یا AI-گونه؛ ابهام ضمیر؛
تکرار واژه یا ساختار؛ پیوستگی پاراگراف‌ها؛ تناسب لحن و طبیعی‌بودن نام برند. متن را
بی‌دلیل رسمی، کلیشه‌ای یا تبلیغاتی نکن؛ فقط اشکالِ دارای شاهد و راه‌حل کوتاه بده.""",
    "article_writer": """نقش: مقاله‌نویس فارسیِ باتجربه در محتوای آموزشیِ تصمیم‌یار.
بررسی کن آیا هر بخش وعدهٔ heading را محقق می‌کند، مسیر خواننده روشن است، توضیح و
مثال و نتیجه ترتیب منطقی دارند، گذارها طبیعی‌اند و نتیجه‌گیری تکرار مکانیکی نیست.
واقعیت، مثال واقعی یا تجربهٔ ادعاییِ خارج از context اضافه نکن؛ اگر ایراد واقعی نیست
finding نساز.""",
    "industrial_electrical": """نقش: بازبین فنی برق صنعتی با اولویت ایمنی و دقت اصطلاحات.
بررسی کن: کاربرد درست اصطلاحات، رابطهٔ علت و معلول، مرز کار تجهیزات، هشدار ایمنی و
ادعای راندمان/ظرفیت/استاندارد یا دستور عملیاتی. ادعای فنی تأییدنشده یا دستور خطرناک
را high یا critical کن و نیاز به منبع معتبر یا مهندس دارای صلاحیت را صریح بنویس.
استاندارد، عدد یا راهکار اجرایی از خودت نساز. اگر موضوع خارج از حوزه است applicable=false بده.""",
    "solar": """نقش: بازبین فنی سامانه‌های فتوولتائیک با اولویت ایمنی و کارکرد واقعی.
بررسی کن: تمایز پنل، اینورتر، باتری، سازه و حفاظت؛ اثر تابش، دما، سایه، جهت و طراحی؛
ادعاهای تولید یا صرفه‌جویی؛ محدودیت نصب و نگه‌داری؛ و هشدارهای برق. ادعای عددی یا
راهنمای نصب را بدون research معتبر تأیید نکن. مورد پرخطر را high/critical و نیازمند
بررسی انسانی بنویس. اگر موضوع فتوولتائیک نیست applicable=false بده.""",
}

_ROLES = tuple(ROLE_PROMPTS)


class SpecialistReviewCoordinator:
    """Runs all enabled personas serially, with bounded context and output."""

    def __init__(self, llm: TextGenerator, context_builder: ContextBuilder) -> None:
        self.llm, self.context_builder = llm, context_builder

    @staticmethod
    def enabled_roles() -> tuple[str, ...]:
        configured = getattr(settings, "ARTICLE_AGENT_SPECIALIST_REVIEW_ROLES", _ROLES)
        return tuple(role for role in configured if role in ROLE_PROMPTS)

    async def review_section(
        self, plan: ArticlePlan, section: SectionPlan, draft: SectionDraft,
        memory: ArticleMemory, style: StyleProfile, research: ResearchData,
    ) -> list[SpecialistOpinion]:
        context = self.context_builder.build_review_context(
            plan, section, draft.content, memory, style,
            output_tokens=settings.ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_OUTPUT_TOKENS,
        )
        return await self._review_all("section", context, [f"section:{section.index}"], research)

    async def review_article(
        self, plan: ArticlePlan, memory: ArticleMemory, sections: list[SectionDraft],
        payload: dict[str, Any], research: ResearchData,
    ) -> list[SpecialistOpinion]:
        representation = {
            "task": "Review bounded article excerpts and available extras; do not infer missing prose.",
            "article": self.context_builder._article_metadata(plan),
            "sections": [
                {"unit_id": f"section:{item.section_index}", "heading": item.heading,
                 "opening": item.content[:500], "closing": item.content[-500:],
                 "words": WordCounter.count_text(item.content)}
                for item in sections
            ],
            "extras": {key: payload.get(key) for key in ("conclusion", "FAQ", "common_mistakes", "applications")},
            "memory": asdict(memory.normalized()), "research": asdict(research),
        }
        context = self.context_builder._bounded_json(
            representation,
            self.context_builder.limit_for_output_tokens(
                settings.ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_OUTPUT_TOKENS,
                self.context_builder.budgets.reviewer_context_limit,
            ),
        )
        return await self._review_all("article", context, [f"section:{item.section_index}" for item in sections], research)

    async def _review_all(
        self, scope: str, context: str, allowed_units: list[str], research: ResearchData,
    ) -> list[SpecialistOpinion]:
        opinions: list[SpecialistOpinion] = []
        for role in self.enabled_roles():
            prompt = self._prompt(role, scope, context, allowed_units, research)
            raw = await self.llm.generate(
                prompt, operation="specialist_review",
                output_tokens=settings.ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_OUTPUT_TOKENS,
            )
            try:
                opinion = self._parse(raw, role, scope, allowed_units)
            except (ValueError, ContractValidationError, json.JSONDecodeError) as error:
                logging.getLogger(__name__).warning(
                    "Specialist review response rejected: role=%s scope=%s error=%s response=%r",
                    role, scope, error, str(raw)[:500],
                )
                opinion = SpecialistOpinion(
                    role=role, scope=scope, applicable=False, score=0,
                    reason=f"invalid_provider_response:{error}",
                )
            opinions.append(opinion)
        return opinions

    @staticmethod
    def _prompt(role: str, scope: str, context: str, allowed_units: list[str], research: ResearchData) -> str:
        schema = {
            "role": role, "scope": scope, "applicable": True, "score": 0,
            "reason": "", "strengths": [], "required_fixes": [],
            "findings": [{"type": "", "severity": "low", "description": "", "affected_units": allowed_units[:1], "recommendation": ""}],
        }
        return (
            "تو بازبین مشورتی هستی، نه نویسندهٔ جایگزین و نه منبع حقیقت. فقط دادهٔ CONTEXT را "
            "ارزیابی کن؛ عدد، استاندارد، منبع یا ادعای تازه نساز. اگر موضوع در حوزه‌ات نیست، "
            "applicable=false و دلیل کوتاه بده. فقط ایرادهای مشخص و قابل اقدام را گزارش کن و متن "
            "را بازنویسی نکن. finding حداکثر "
            f"{settings.ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_FINDINGS} مورد باشد؛ affected_units فقط یکی از {allowed_units!r}. "
            "خروجی فقط یک JSON object مطابق SCHEMA باشد؛ هیچ markdown یا توضیح بیرونی نده.\n\n"
            f"{ROLE_PROMPTS[role]}\n\nSCHEMA:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"RESEARCH_STATUS: {research.status}\nCONTEXT:\n{context}"
        )

    @staticmethod
    def _parse(raw: str, role: str, scope: str, allowed_units: list[str]) -> SpecialistOpinion:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("missing_json_object")
        data = json.loads(text[start:end + 1])
        if data.get("role") != role or data.get("scope") != scope:
            raise ValueError("role_or_scope_mismatch")
        if not isinstance(data.get("applicable"), bool):
            raise ValueError("applicable_must_be_boolean")
        for finding in data.get("findings", []):
            units = finding.get("affected_units", [])
            if not isinstance(units, list) or any(unit not in allowed_units for unit in units):
                raise ValueError("invalid_affected_unit")
        if len(data.get("findings", [])) > settings.ARTICLE_AGENT_SPECIALIST_REVIEW_MAX_FINDINGS:
            raise ValueError("too_many_findings")
        return specialist_opinion_from_dict(data)


def merge_specialist_findings(
    base: ReviewResult | ArticleReview,
    opinions: list[SpecialistOpinion],
) -> ReviewResult | ArticleReview:
    """Merge expert findings into either a section or article review.

    ``ReviewResult`` stores findings as ``issues`` while ``ArticleReview`` uses
    ``findings``.  The application deliberately shares this merge operation for
    both review scopes, so selecting the collection explicitly prevents an
    article-level specialist review from failing after provider work has already
    completed.
    """
    issue_collection = base.issues if isinstance(base, ReviewResult) else base.findings
    seen = {
        (issue.type, issue.description.casefold()) for issue in issue_collection
    }
    for opinion in opinions:
        for issue in opinion.findings:
            key = (issue.type, issue.description.casefold())
            if key in seen:
                continue
            seen.add(key)
            issue_collection.append(issue)
            if issue.severity in {"high", "critical"}:
                base.required_fixes.append(issue.recommendation or issue.description)
    base.specialist_opinions = opinions
    if any(issue.severity in {"high", "critical"} for issue in issue_collection):
        base.passed = False
    return base
