"""Runtime semantic counting and per-unit budget enforcement."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from apps.article_agent.domain import ArticleAllocation, ArticleBudget


class BudgetError(RuntimeError):
    """Raised when a unit cannot be safely accepted within its allocation."""


class WordCounter:
    """The single word-count definition used for prose and FAQ content.

    Persian joiners and zero-width controls are normalized to separators so
    they cannot accidentally merge otherwise distinct semantic words.
    """

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
        return sum(cls.count_text(entry.get("question", "")) + cls.count_text(entry.get("answer", "")) for entry in entries)

    @classmethod
    def count_faq_text(cls, text: str) -> int:
        """Count FAQ questions/answers, excluding formatting labels."""
        total = 0
        for line in text.splitlines():
            label, separator, value = line.partition(":")
            if separator and label.strip().casefold() in {"question", "answer", "سوال", "سؤال", "پاسخ"}:
                total += cls.count_text(value)
        return total


Repair = Callable[[str, ArticleAllocation], Awaitable[str]]


class BudgetManager:
    """Reserves, measures, repairs and commits every article unit.

    It deliberately owns acceptance: callers cannot commit non-empty but
    under/over-budget provider output by mistake.
    """

    def __init__(self, budget: ArticleBudget, *, max_repairs: int = 2) -> None:
        self.budget = budget
        self.max_repairs = max_repairs

    def reserve(self, unit_id: str) -> ArticleAllocation:
        allocation = self.budget.allocation_for(unit_id)
        if allocation.status == "accepted":
            return allocation
        if allocation.status == "reserved":
            raise BudgetError(f"Unit {unit_id} is already reserved.")
        future_minimums = sum(
            item.minimum_words for item in self.budget.allocations
            if item.unit_id != unit_id and item.status != "accepted"
        )
        if self.budget.remaining_words < allocation.minimum_words + future_minimums:
            raise BudgetError("remaining_budget_cannot_cover_required_units")
        allocation.status = "reserved"
        self.budget.reserved_words += allocation.target_words
        return allocation

    async def generate_and_accept(
        self, unit_id: str, generate: Callable[[], Awaitable[str]], repair: Repair,
        *, count: Callable[[str], int] = WordCounter.count_text,
    ) -> str:
        allocation = self.reserve(unit_id)
        output = await generate()
        for attempt in range(self.max_repairs + 1):
            actual = count(output)
            if allocation.minimum_words <= actual <= allocation.maximum_words:
                self.accept(unit_id, actual)
                return output.strip()
            if attempt == self.max_repairs:
                allocation.status = "planned"
                self.budget.reserved_words -= allocation.target_words
                raise BudgetError(f"unit_budget_unsatisfied:{unit_id}:{actual}")
            output = await repair(output, allocation)
        raise AssertionError("unreachable")

    def accept(self, unit_id: str, actual_words: int) -> None:
        allocation = self.budget.allocation_for(unit_id)
        if allocation.status != "reserved":
            raise BudgetError(f"Unit {unit_id} must be reserved before acceptance.")
        if not allocation.minimum_words <= actual_words <= allocation.maximum_words:
            raise BudgetError(f"Unit {unit_id} violates its word allocation.")
        prospective = self.budget.consumed_words + actual_words
        remaining_minimums = sum(
            item.minimum_words for item in self.budget.allocations if item.unit_id != unit_id and item.status != "accepted"
        )
        if self.budget.total_words - prospective < remaining_minimums:
            raise BudgetError("acceptance_would_starve_required_units")
        allocation.generated_words, allocation.status = actual_words, "accepted"
        self.budget.consumed_words = prospective
        self.budget.reserved_words -= allocation.target_words

    def restore_accepted(self, unit_id: str, actual_words: int) -> None:
        """Hydrate an accepted checkpoint without treating it as new generation."""
        allocation = self.budget.allocation_for(unit_id)
        if allocation.status == "accepted":
            return
        allocation.status = "reserved"
        self.budget.reserved_words += allocation.target_words
        self.accept(unit_id, actual_words)

    def replace_accepted(self, unit_id: str, actual_words: int) -> None:
        """Revalidate a revision/edit and replace its accounting atomically."""
        allocation = self.budget.allocation_for(unit_id)
        if allocation.status != "accepted":
            raise BudgetError(f"Unit {unit_id} must be accepted before replacement.")
        if not allocation.minimum_words <= actual_words <= allocation.maximum_words:
            raise BudgetError(f"Unit {unit_id} revision violates its word allocation.")
        prospective = self.budget.consumed_words - allocation.generated_words + actual_words
        if prospective > self.budget.total_words:
            raise BudgetError("revision_exceeds_total_budget")
        allocation.generated_words = actual_words
        self.budget.consumed_words = prospective

    async def repair_accepted(self, unit_id: str, output: str, repair: Repair, *, count: Callable[[str], int] = WordCounter.count_text) -> str:
        """Bring a revision or targeted edit back into its accepted range."""
        allocation = self.budget.allocation_for(unit_id)
        for attempt in range(self.max_repairs + 1):
            actual = count(output)
            if allocation.minimum_words <= actual <= allocation.maximum_words:
                self.replace_accepted(unit_id, actual)
                return output.strip()
            if attempt == self.max_repairs:
                raise BudgetError(f"accepted_unit_budget_unsatisfied:{unit_id}:{actual}")
            output = await repair(output, allocation)
        raise AssertionError("unreachable")

