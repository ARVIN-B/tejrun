"""Deterministic signals for useful, non-template article prose."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass

from apps.article_agent.application.word_budget import WordCounter
from apps.article_agent.domain import ReviewIssue, SectionDraft


@dataclass(frozen=True, slots=True)
class StyleMetrics:
    generic_opening_count: int
    generic_transition_count: int
    repeated_phrase_count: int
    repeated_sentence_pattern_count: int
    sentence_length_variance: float
    paragraph_length_variance: float
    keyword_stuffing_score: float
    template_phrase_score: float
    repeated_example_count: int
    repeated_structure_count: int
    meta_language_count: int

    def to_dict(self) -> dict:
        return asdict(self)


class HumanStyleAnalyzer:
    """Flags mechanical patterns for targeted editorial review, not detection evasion."""

    generic_openings = ("in today's world", "in this article", "nowadays", "امروزه", "در این مقاله")
    generic_transitions = ("moreover", "furthermore", "in conclusion", "علاوه بر این", "در نهایت")
    template_phrases = ("it is important to note", "needless to say", "به طور کلی", "لازم به ذکر است")
    meta_language = ("as an ai", "language model", "prompt", "i cannot")

    def analyze(self, text: str, keywords: list[str] | None = None) -> StyleMetrics:
        normalized = " ".join(text.casefold().split())
        words = WordCounter.count_text(text)
        sentences = [item.strip() for item in re.split(r"[.!?؟]+", text) if WordCounter.count_text(item)]
        paragraphs = [item for item in re.split(r"\n\s*\n", text) if WordCounter.count_text(item)]
        phrase_counts = Counter(" ".join(WordCounter.normalize(text).casefold().split()[index:index + 4])
                                for index in range(max(0, len(WordCounter.normalize(text).split()) - 3)))
        sentence_patterns = Counter(" ".join(WordCounter.normalize(sentence).casefold().split()[:3]) for sentence in sentences)
        sentence_lengths = [WordCounter.count_text(item) for item in sentences]
        paragraph_lengths = [WordCounter.count_text(item) for item in paragraphs]
        keyword_occurrences = sum(normalized.count(keyword.casefold()) for keyword in (keywords or []) if keyword)
        variance = lambda values: 0.0 if len(values) < 2 else sum((value - sum(values) / len(values)) ** 2 for value in values) / len(values)
        return StyleMetrics(
            generic_opening_count=sum(normalized.startswith(phrase) for phrase in self.generic_openings),
            generic_transition_count=sum(normalized.count(phrase) for phrase in self.generic_transitions),
            repeated_phrase_count=sum(count - 1 for phrase, count in phrase_counts.items() if phrase.strip() and count > 1),
            repeated_sentence_pattern_count=sum(count - 1 for phrase, count in sentence_patterns.items() if phrase.strip() and count > 1),
            sentence_length_variance=variance(sentence_lengths), paragraph_length_variance=variance(paragraph_lengths),
            keyword_stuffing_score=keyword_occurrences / max(1, words),
            template_phrase_score=sum(normalized.count(phrase) for phrase in self.template_phrases) / max(1, len(sentences)),
            repeated_example_count=max(0, len(re.findall(r"\b(?:for example|مثال)\b", normalized)) - 1),
            repeated_structure_count=sum(count - 1 for count in Counter(item.split(":", 1)[0] for item in paragraphs if ":" in item).values() if count > 1),
            meta_language_count=sum(normalized.count(phrase) for phrase in self.meta_language),
        )

    def review_findings(
        self, sections: list[SectionDraft], keywords: list[str]
    ) -> list[ReviewIssue]:
        """Create bounded, actionable editorial findings from deterministic signals.

        The thresholds are deliberately conservative.  They flag visible
        template language and keyword stuffing rather than treating ordinary
        grammar, clean formatting, or document metadata as authorship signals.
        """
        findings: list[ReviewIssue] = []
        for section in sections:
            metrics = self.analyze(section.content, keywords)
            unit_id = f"section:{section.section_index}"
            if metrics.generic_opening_count:
                findings.append(ReviewIssue(
                    type="generic_opening", severity="medium",
                    description="The section starts with a generic template opening.",
                    affected_units=[unit_id],
                    recommendation="Open with the specific decision, condition, or distinction addressed by this heading.",
                ))
            if metrics.template_phrase_score >= 0.08:
                findings.append(ReviewIssue(
                    type="template_language", severity="medium",
                    description="The section uses repeated template-style connective language.",
                    affected_units=[unit_id],
                    recommendation="Replace template transitions with a direct connection between the surrounding ideas.",
                ))
            if metrics.generic_transition_count > 2:
                findings.append(ReviewIssue(
                    type="generic_transitions", severity="medium",
                    description="The section repeatedly uses generic transition phrases.",
                    affected_units=[unit_id],
                    recommendation="Keep only transitions that express a real logical relationship and write the rest directly.",
                ))
            if (
                metrics.repeated_phrase_count >= 2
                or metrics.repeated_sentence_pattern_count >= 2
                or metrics.repeated_structure_count >= 2
            ):
                findings.append(ReviewIssue(
                    type="repetitive_structure", severity="medium",
                    description="The section repeats a phrase or sentence/list structure enough to sound mechanical.",
                    affected_units=[unit_id],
                    recommendation="Keep the strongest occurrence and replace the repeated structure with a distinct explanation, condition, or example already supported by the context.",
                ))
            if metrics.keyword_stuffing_score > 0.045:
                findings.append(ReviewIssue(
                    type="keyword_stuffing", severity="medium",
                    description="Keyword density is high enough to reduce natural readability.",
                    affected_units=[unit_id],
                    recommendation="Keep the keyword where it clarifies meaning and replace repeated occurrences with precise natural references.",
                ))
            if metrics.meta_language_count:
                findings.append(ReviewIssue(
                    type="process_language", severity="high",
                    description="The section exposes model or prompt process language.",
                    affected_units=[unit_id],
                    recommendation="Remove all model, prompt, or generation-process references from reader-facing prose.",
                ))
        findings.extend(self._cross_section_repetition_findings(sections))
        return findings

    @staticmethod
    def _cross_section_repetition_findings(
        sections: list[SectionDraft],
    ) -> list[ReviewIssue]:
        """Catch exact repeated long phrases across headings without semantic guessing."""
        seen: dict[str, int] = {}
        repeated_pairs: set[tuple[int, int]] = set()
        for section in sections:
            words = WordCounter.normalize(section.content).casefold().split()
            phrases = {
                " ".join(words[index:index + 8])
                for index in range(max(0, len(words) - 7))
            }
            for phrase in phrases:
                prior_index = seen.get(phrase)
                if prior_index is not None and prior_index != section.section_index:
                    repeated_pairs.add(tuple(sorted((prior_index, section.section_index))))
                else:
                    seen[phrase] = section.section_index
        return [
            ReviewIssue(
                type="cross_section_repetition",
                severity="medium",
                description="Two headings contain the same long phrase, which risks duplicated coverage.",
                affected_units=[f"section:{left}", f"section:{right}"],
                recommendation="Keep the explanation under the heading where it belongs and replace the duplicate with a distinct point for the other heading.",
            )
            for left, right in sorted(repeated_pairs)
        ]
