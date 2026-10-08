"""Deterministic signals for useful, non-template article prose."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass

from apps.article_agent.application.word_budget import WordCounter


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
