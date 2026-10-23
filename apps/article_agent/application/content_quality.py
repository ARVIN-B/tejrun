"""Deterministic publication-safety checks for bounded article units.

This module deliberately does not try to identify who wrote a text.  It
protects readers from a narrower and testable set of publication risks:
unsupported operational claims, invented commercial identities, and conflicting
quantified requirements.  The LLM receives the findings for a targeted repair;
the conservative replacement is a last resort so an unsafe claim is never
silently rendered when a provider response is incomplete.
"""

from __future__ import annotations

import re
from collections import defaultdict

from apps.article_agent.application.word_budget import WordCounter
from apps.article_agent.domain import ArticlePlan, ResearchData, ReviewIssue, SectionDraft


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?؟])\s+|\n+")
_NUMBER = r"(?:\d+|[۰-۹]+|صفر|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|یازده|دوازده)"
_SENSITIVE_UNIT = r"(?:روز|ماه|سال|ساعت|درصد|ریال|تومان|کیلووات|مگاوات|ولت|آمپر|وات)"
_QUANTIFIED_CLAIM = re.compile(rf"{_NUMBER}\s*{_SENSITIVE_UNIT}", re.IGNORECASE)
_NAMED_OFFICIAL_ENTITY = re.compile(
    r"(?:سازمان|وزارت|سامانه|اداره|شرکت|برند|مجموعه|گروه)\s+"
    r"(?:[«\"])?([آ-یA-Za-z][\w‌آ-یA-Za-z]*(?:\s+[آ-یA-Za-z][\w‌آ-یA-Za-z]*){0,3})"
)
_OPERATIONAL_REQUIREMENT = re.compile(
    r"(?:مهلت\s+(?:ثبت[‌ ]نام|ارسال|پرداخت)|(?:ثبت[‌ ]نام|پرداخت|ارائه)\s+.*(?:الزامی|اجباری)|"
    r"باید\s+(?:ظرف|تا\s+پایان)|ضمانت[‌ ]نامه|ودیعه)",
    re.IGNORECASE,
)
_CLAIM_PARTS = re.compile(
    rf"(?P<prefix>.{{0,72}}?)(?P<value>{_NUMBER})\s+(?P<unit>{_SENSITIVE_UNIT})(?P<suffix>.{{0,72}})",
    re.IGNORECASE,
)
_ENTITY_STOPWORDS = {
    "در", "این", "آن", "یک", "های", "ها", "برای", "کننده", "مناقصه",
    "ثبت", "نام", "مسئول", "مربوط", "باید", "است", "های", "عمومی",
}
_SUBJECT_STOPWORDS = _ENTITY_STOPWORDS | {
    "و", "یا", "از", "به", "با", "را", "که", "تا", "هر", "همان", "نیز",
    "شرایط", "مدارک", "مورد", "نیاز", "بررسی", "فراخوان", "رسمی",
}


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in _SENTENCE_BOUNDARY.split(text) if item.strip()]


def _normalized(value: str) -> str:
    return " ".join(WordCounter.normalize(value).casefold().split())


def _tokens(value: str) -> set[str]:
    return {
        token for token in _normalized(value).split()
        if len(token) > 1 and token not in _SUBJECT_STOPWORDS
    }


class ContentSafetyValidator:
    """Detect and conservatively neutralise claims that lack available support."""

    def inspect_section(
        self,
        plan: ArticlePlan,
        section: SectionDraft,
        research: ResearchData,
    ) -> list[ReviewIssue]:
        return self.inspect_text(
            plan, section.content, research, unit_id=f"section:{section.section_index}"
        )

    def inspect_text(
        self,
        plan: ArticlePlan,
        text: str,
        research: ResearchData,
        *,
        unit_id: str,
    ) -> list[ReviewIssue]:
        findings: list[ReviewIssue] = []
        for sentence in _sentences(text):
            if self._has_unapproved_brand(sentence, plan, research):
                findings.append(
                    self._issue(
                        "unapproved_brand_reference", unit_id, sentence,
                        "Remove the unverified brand or provider reference. Only the exact user-supplied brand name may be used.",
                    )
                )
                continue
            if self._needs_support(sentence) and not self._supported_by_research(sentence, research):
                findings.append(
                    self._issue(
                        "unsupported_operational_claim", unit_id, sentence,
                        "Remove the exact operational claim or rewrite it as a general instruction to verify the official project notice; do not invent a replacement number, deadline, authority, or requirement.",
                    )
                )
        return findings

    def sanitize_text(
        self,
        plan: ArticlePlan,
        text: str,
        research: ResearchData,
        *,
        unit_id: str,
    ) -> tuple[str, list[ReviewIssue]]:
        """Return prose safe to publish if targeted model repair did not resolve it."""
        findings = self.inspect_text(plan, text, research, unit_id=unit_id)
        unsafe = {self._quoted_sentence(item.description) for item in findings}
        if not unsafe:
            return text, []
        replacement = self._safe_replacement(plan.language)
        replaced = [replacement if sentence in unsafe else sentence for sentence in _sentences(text)]
        return " ".join(replaced).strip(), findings

    def sanitize_contradictions(
        self,
        plan: ArticlePlan,
        sections: list[SectionDraft],
        research: ResearchData,
    ) -> tuple[list[SectionDraft], list[ReviewIssue]]:
        """Neutralise conflicting quantified instructions without guessing which is true."""
        if research.status == "available":
            # Source-backed claims still undergo per-sentence support checks.  A
            # deterministic contradiction rule is intentionally conservative
            # only when the system lacks provenance to arbitrate the conflict.
            return sections, []
        claims: list[tuple[int, str, str, set[str]]] = []
        for section in sections:
            for sentence in _sentences(section.content):
                match = _CLAIM_PARTS.search(sentence)
                if not match:
                    continue
                subject = _tokens(match.group("prefix") + " " + match.group("suffix"))
                if subject:
                    claims.append((section.section_index, sentence, _normalized(match.group("value")), subject))
        conflicting: dict[int, set[str]] = defaultdict(set)
        findings: list[ReviewIssue] = []
        for index, (left_unit, left_sentence, left_value, left_subject) in enumerate(claims):
            for right_unit, right_sentence, right_value, right_subject in claims[index + 1:]:
                if left_value == right_value or not (left_subject & right_subject):
                    continue
                conflicting[left_unit].add(left_sentence)
                conflicting[right_unit].add(right_sentence)
                findings.append(
                    ReviewIssue(
                        type="conflicting_quantified_claim",
                        severity="high",
                        description="Conflicting quantified operational statements were removed because no verified research is available.",
                        affected_units=[f"section:{left_unit}", f"section:{right_unit}"],
                        recommendation="Verify the official source and state one supported requirement only.",
                    )
                )
        if not conflicting:
            return sections, []
        replacement = self._safe_replacement(plan.language)
        sanitized: list[SectionDraft] = []
        for section in sections:
            sentences = _sentences(section.content)
            content = " ".join(
                replacement if sentence in conflicting.get(section.section_index, set()) else sentence
                for sentence in sentences
            ).strip()
            sanitized.append(
                SectionDraft(
                    section.section_index, section.heading, content,
                    word_count=WordCounter.count_text(content),
                    revision_number=section.revision_number,
                )
            )
        return sanitized, findings

    @staticmethod
    def _issue(kind: str, unit_id: str, sentence: str, recommendation: str) -> ReviewIssue:
        return ReviewIssue(
            type=kind,
            severity="high",
            description=f"Unsafe sentence: {sentence}",
            affected_units=[unit_id],
            recommendation=recommendation,
        )

    @staticmethod
    def _quoted_sentence(description: str) -> str:
        return description.removeprefix("Unsafe sentence: ").strip()

    @staticmethod
    def _needs_support(sentence: str) -> bool:
        return bool(
            _QUANTIFIED_CLAIM.search(sentence)
            or _OPERATIONAL_REQUIREMENT.search(sentence)
            or _NAMED_OFFICIAL_ENTITY.search(sentence)
        )

    @staticmethod
    def _safe_replacement(language: str) -> str:
        if language.casefold().startswith("fa"):
            return "شرایط، مهلت‌ها و الزامات اجرایی را باید از متن رسمی فراخوان و مرجع مسئول همان پروژه بررسی کرد."
        return "Verify the applicable conditions, deadlines, and requirements against the official notice for that project."

    @staticmethod
    def _research_text(research: ResearchData) -> str:
        return " ".join(
            [*research.facts, *research.statistics, *research.examples, *research.claims]
        )

    def _supported_by_research(self, sentence: str, research: ResearchData) -> bool:
        if research.status != "available" or not research.sources:
            return False
        corpus = _normalized(self._research_text(research))
        normalized_sentence = _normalized(sentence)
        numbers = re.findall(r"\d+|[۰-۹]+", normalized_sentence)
        if numbers and not all(number in corpus for number in numbers):
            return False
        sentence_tokens = _tokens(sentence)
        research_tokens = _tokens(corpus)
        return len(sentence_tokens & research_tokens) >= 2

    def _has_unapproved_brand(
        self, sentence: str, plan: ArticlePlan, research: ResearchData
    ) -> bool:
        allowed = _normalized(plan.brand_name)
        research_text = _normalized(self._research_text(research))
        for match in _NAMED_OFFICIAL_ENTITY.finditer(sentence):
            candidate = _normalized(match.group(1))
            candidate_words = candidate.split()
            if (
                not candidate
                or candidate in _ENTITY_STOPWORDS
                or (candidate_words and candidate_words[0] in _ENTITY_STOPWORDS)
            ):
                continue
            if allowed and (candidate in allowed or allowed in candidate):
                continue
            if candidate in research_text:
                continue
            return True
        return False
