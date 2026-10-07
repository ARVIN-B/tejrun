"""Stable domain contracts used by the article generation pipeline.

These dataclasses deliberately have no Django, Celery, or LLM-provider
dependencies. Persistence and provider-specific serialization belong to later
layers of the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DEFAULT_LANGUAGE = "fa"
DEFAULT_AUDIENCE = "general"
DEFAULT_TONE = "professional, natural, informative"


def _non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _unique_strings(values: list[str]) -> list[str]:
    """Normalize, de-duplicate, and preserve the first occurrence."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


@dataclass(slots=True)
class ArticleRequest:
    title: str
    word_count: int
    headings: list[str]
    keywords: list[str] = field(default_factory=list)
    language: str = DEFAULT_LANGUAGE
    audience: str = DEFAULT_AUDIENCE
    tone: str = DEFAULT_TONE
    purpose: str = "inform"

    def __post_init__(self) -> None:
        self.title = _non_empty(self.title, "title")
        if self.word_count <= 0:
            raise ValueError("word_count must be greater than zero.")
        self.headings = _unique_strings(self.headings)
        if not self.headings:
            raise ValueError("At least one heading is required.")
        self.keywords = _unique_strings(self.keywords)
        self.language = _non_empty(self.language, "language")
        self.audience = _non_empty(self.audience, "audience")
        self.tone = _non_empty(self.tone, "tone")
        self.purpose = _non_empty(self.purpose, "purpose")


@dataclass(slots=True)
class SectionPlan:
    index: int
    heading: str
    purpose: str
    key_points: list[str]
    target_words: int
    minimum_words: int
    maximum_words: int
    must_include: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)
    dependencies: list[int] = field(default_factory=list)
    research_requirements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("index must be zero or greater.")
        self.heading = _non_empty(self.heading, "heading")
        self.purpose = _non_empty(self.purpose, "purpose")
        self.key_points = _unique_strings(self.key_points)
        if not self.key_points:
            raise ValueError("A section plan requires at least one key point.")
        if self.minimum_words <= 0:
            raise ValueError("minimum_words must be greater than zero.")
        if not self.minimum_words <= self.target_words <= self.maximum_words:
            raise ValueError("target_words must be within the section word range.")
        self.must_include = _unique_strings(self.must_include)
        self.must_avoid = _unique_strings(self.must_avoid)
        self.research_requirements = _unique_strings(self.research_requirements)
        if any(dependency < 0 for dependency in self.dependencies):
            raise ValueError("dependencies cannot contain negative indexes.")


@dataclass(slots=True)
class ArticlePlan:
    title: str
    goal: str
    audience: str
    tone: str
    language: str
    primary_topic: str
    keywords: list[str]
    sections: list[SectionPlan]
    global_constraints: list[str] = field(default_factory=list)
    seo_intent: str = "informational"
    coverage_requirements: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = _non_empty(self.title, "title")
        self.goal = _non_empty(self.goal, "goal")
        self.audience = _non_empty(self.audience, "audience")
        self.tone = _non_empty(self.tone, "tone")
        self.language = _non_empty(self.language, "language")
        self.primary_topic = _non_empty(self.primary_topic, "primary_topic")
        if not self.sections:
            raise ValueError("An article plan requires at least one section.")
        expected_indexes = list(range(len(self.sections)))
        if [section.index for section in self.sections] != expected_indexes:
            raise ValueError("Section indexes must be sequential and start at zero.")
        self.keywords = _unique_strings(self.keywords)
        self.global_constraints = _unique_strings(self.global_constraints)
        self.coverage_requirements = _unique_strings(self.coverage_requirements)
        self.seo_intent = _non_empty(self.seo_intent, "seo_intent")


@dataclass(slots=True)
class StyleProfile:
    language: str = DEFAULT_LANGUAGE
    tone: str = DEFAULT_TONE
    audience: str = DEFAULT_AUDIENCE
    sentence_variation: Literal["low", "medium", "high"] = "high"
    paragraph_variation: Literal["low", "medium", "high"] = "high"
    filler_tolerance: Literal["low", "medium", "high"] = "low"
    repetition_tolerance: Literal["low", "medium", "high"] = "low"
    avoid_generic_openings: bool = True
    avoid_generic_conclusions: bool = True
    avoid_unsupported_claims: bool = True


@dataclass(slots=True)
class ResearchData:
    facts: list[str] = field(default_factory=list)
    statistics: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one.")
        self.facts = _unique_strings(self.facts)
        self.statistics = _unique_strings(self.statistics)
        self.examples = _unique_strings(self.examples)
        self.claims = _unique_strings(self.claims)
        self.sources = _unique_strings(self.sources)


@dataclass(slots=True)
class ArticleMemory:
    covered_topics: list[str] = field(default_factory=list)
    section_summaries: list[str] = field(default_factory=list)
    important_facts: list[str] = field(default_factory=list)
    claims_made: list[str] = field(default_factory=list)
    examples_used: list[str] = field(default_factory=list)
    terms_introduced: list[str] = field(default_factory=list)
    avoid_repeating: list[str] = field(default_factory=list)
    style_notes: list[str] = field(default_factory=list)
    open_threads: list[str] = field(default_factory=list)

    def normalized(self) -> ArticleMemory:
        """Return a normalized copy; budget enforcement belongs to MemoryUpdater."""
        return ArticleMemory(
            covered_topics=_unique_strings(self.covered_topics),
            section_summaries=_unique_strings(self.section_summaries),
            important_facts=_unique_strings(self.important_facts),
            claims_made=_unique_strings(self.claims_made),
            examples_used=_unique_strings(self.examples_used),
            terms_introduced=_unique_strings(self.terms_introduced),
            avoid_repeating=_unique_strings(self.avoid_repeating),
            style_notes=_unique_strings(self.style_notes),
            open_threads=_unique_strings(self.open_threads),
        )


@dataclass(slots=True)
class SectionDraft:
    section_index: int
    heading: str
    content: str
    word_count: int = 0
    revision_number: int = 0

    def __post_init__(self) -> None:
        if self.section_index < 0:
            raise ValueError("section_index must be zero or greater.")
        self.heading = _non_empty(self.heading, "heading")
        self.content = _non_empty(self.content, "content")
        if self.revision_number < 0:
            raise ValueError("revision_number must be zero or greater.")
        self.word_count = len(self.content.split()) if self.word_count == 0 else self.word_count
        if self.word_count <= 0:
            raise ValueError("word_count must be greater than zero.")


@dataclass(slots=True)
class ReviewIssue:
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str

    def __post_init__(self) -> None:
        self.type = _non_empty(self.type, "type")
        self.description = _non_empty(self.description, "description")


@dataclass(slots=True)
class ReviewResult:
    passed: bool
    score: float
    issues: list[ReviewIssue] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 10:
            raise ValueError("score must be between zero and ten.")
        self.strengths = _unique_strings(self.strengths)
        self.required_fixes = _unique_strings(self.required_fixes)


@dataclass(slots=True)
class ArticleReview:
    passed: bool
    score: float
    findings: list[ReviewIssue] = field(default_factory=list)
    section_scores: dict[int, float] = field(default_factory=dict)
    required_fixes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 10:
            raise ValueError("score must be between zero and ten.")
        if any(index < 0 or not 0 <= score <= 10 for index, score in self.section_scores.items()):
            raise ValueError("section_scores must use non-negative indexes and scores from zero to ten.")
        self.required_fixes = _unique_strings(self.required_fixes)


@dataclass(slots=True)
class QualityReport:
    passed: bool
    target_word_count: int
    actual_word_count: int
    tolerance: float
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.target_word_count <= 0 or self.actual_word_count < 0:
            raise ValueError("Word counts must be valid.")
        if not 0 <= self.tolerance <= 1:
            raise ValueError("tolerance must be between zero and one.")
        self.warnings = _unique_strings(self.warnings)

    @property
    def relative_word_difference(self) -> float:
        return abs(self.target_word_count - self.actual_word_count) / self.target_word_count


@dataclass(slots=True)
class FinalArticle:
    title: str
    sections: list[SectionDraft]
    conclusion: str = ""
    faq: list[tuple[str, str]] = field(default_factory=list)
    common_mistakes: str = ""
    applications: str = ""
    quality_report: QualityReport | None = None

    def __post_init__(self) -> None:
        self.title = _non_empty(self.title, "title")
        if not self.sections:
            raise ValueError("A final article requires at least one section.")
