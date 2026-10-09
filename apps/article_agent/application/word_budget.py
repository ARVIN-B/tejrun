"""Word counting utilities without word-budget enforcement."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from apps.article_agent.domain import ArticleAllocation, ArticleBudget


class BudgetError(RuntimeError):
    """Raised only for invalid internal allocation state."""


class WordCounter:
    _zero_width = re.compile(r"[\u200b\u200c\u200d\ufeff]")
    _word = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)

    @classmethod
    def normalize(cls, text: str) -> str:
        return cls._zero_width.sub(" ", text).replace("\u00a0", " ")

    @classmethod
    def count_text(cls, text: str) -> int:
        return len(cls._word.findall(cls.normalize(text)))

    @classmethod
    def count_faq(cls, entries: list[dict[str, str]]) -> int:
        return sum(
            cls.count_text(entry.get("question", ""))
            + cls.count_text(entry.get("answer", ""))
            for entry in entries
        )

    @classmethod
    def count_faq_text(cls, text: str) -> int:
        total = 0
        for line in text.splitlines():
            label, separator, value = line.partition(":")
            if separator and label.strip().casefold() in {
                "question",
                "answer",
                "سوال",
                "سؤال",
                "پاسخ",
            }:
                total += cls.count_text(value)
        return total


Repair = Callable[[str, ArticleAllocation], Awaitable[str]]


class BudgetManager:
    """Track generated word counts without enforcing target ranges."""

    def __init__(self, budget: ArticleBudget, *, max_repairs: int = 0) -> None:
        self.budget = budget
        self.max_repairs = 0

    def reserve(self, unit_id: str) -> ArticleAllocation:
        allocation = self.budget.allocation_for(unit_id)

        if allocation.status == "accepted":
            return allocation

        if allocation.status == "reserved":
            raise BudgetError(f"Unit {unit_id} is already reserved.")

        allocation.status = "reserved"
        self.budget.reserved_words += allocation.target_words
        return allocation

    async def generate_and_accept(
        self,
        unit_id: str,
        generate: Callable[[], Awaitable[str]],
        repair: Repair,
        *,
        count: Callable[[str], int] = WordCounter.count_text,
    ) -> str:
        """Generate once; word count never triggers a repair or failure."""
        self.reserve(unit_id)
        output = await generate()
        self.accept(unit_id, count(output))
        return output.strip()

    def accept(self, unit_id: str, actual_words: int) -> None:
        allocation = self.budget.allocation_for(unit_id)

        if allocation.status != "reserved":
            raise BudgetError(f"Unit {unit_id} must be reserved before acceptance.")

        allocation.generated_words = actual_words
        allocation.status = "accepted"
        self.budget.consumed_words += actual_words
        self.budget.reserved_words = max(
            0, self.budget.reserved_words - allocation.target_words
        )

    def restore_accepted(self, unit_id: str, actual_words: int) -> None:
        allocation = self.budget.allocation_for(unit_id)

        if allocation.status == "accepted":
            return

        allocation.status = "reserved"
        self.budget.reserved_words += allocation.target_words
        self.accept(unit_id, actual_words)

    def replace_accepted(self, unit_id: str, actual_words: int) -> None:
        allocation = self.budget.allocation_for(unit_id)

        if allocation.status != "accepted":
            raise BudgetError(f"Unit {unit_id} must be accepted before replacement.")

        self.budget.consumed_words += actual_words - allocation.generated_words
        allocation.generated_words = actual_words

    async def repair_accepted(
        self,
        unit_id: str,
        output: str,
        repair: Repair,
        *,
        count: Callable[[str], int] = WordCounter.count_text,
    ) -> str:
        """Keep the supplied text; do not rewrite it to satisfy word limits."""
        self.replace_accepted(unit_id, count(output))
        return output.strip()
