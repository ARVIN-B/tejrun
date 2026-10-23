import unittest

from apps.article_agent.application.word_budget import BudgetError, BudgetManager, WordCounter
from apps.article_agent.domain import ArticleAllocation, ArticleBudget


def budget() -> ArticleBudget:
    return ArticleBudget(total_words=100, allocations=[
        ArticleAllocation("section:0", "section", 60, 40, 80, 0),
        ArticleAllocation("conclusion", "conclusion", 40, 20, 60, 1),
    ])


class WordCounterTests(unittest.TestCase):
    def test_persian_zero_width_and_punctuation_are_counted_semantically(self) -> None:
        self.assertEqual(WordCounter.count_text("سلام‌دنیا، این یک آزمون است!"), 6)
        self.assertEqual(WordCounter.count_faq([{"question": "سوال؟", "answer": "پاسخ کامل."}]), 3)
        self.assertEqual(WordCounter.count_faq_text("Question: One?\nAnswer: A complete answer."), 4)


class BudgetManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_output_is_repaired_then_committed(self) -> None:
        manager = BudgetManager(budget(), max_repairs=1)

        async def generate(): return "one two"
        async def repair(_output, _allocation): return "word " * 45

        accepted = await manager.generate_and_accept("section:0", generate, repair)
        self.assertEqual(WordCounter.count_text(accepted), 45)
        self.assertEqual(manager.budget.consumed_words, 45)
        self.assertEqual(manager.budget.reserved_words, 0)
        self.assertEqual(manager.budget.allocation_for("section:0").status, "accepted")

    async def test_impossible_output_is_accepted_after_bounded_repairs(self) -> None:
        manager = BudgetManager(budget(), max_repairs=1)

        async def generate(): return "short"
        async def repair(_output, _allocation): return "still short"

        accepted = await manager.generate_and_accept("section:0", generate, repair)
        self.assertEqual(accepted, "still short")
        self.assertEqual(manager.budget.consumed_words, 2)
        self.assertEqual(manager.budget.allocation_for("section:0").status, "accepted")

    async def test_configured_repair_budget_can_recover_after_three_short_responses(self) -> None:
        """A provider that initially truncates output must get all bounded repairs."""
        manager = BudgetManager(budget(), max_repairs=3)
        repair_calls = 0

        async def generate():
            return "short"

        async def repair(_output, _allocation):
            nonlocal repair_calls
            repair_calls += 1
            if repair_calls < 3:
                return "still short"
            return "recovered " * 45

        accepted = await manager.generate_and_accept("section:0", generate, repair)
        self.assertEqual(repair_calls, 3)
        self.assertEqual(WordCounter.count_text(accepted), 45)
        self.assertEqual(manager.budget.allocation_for("section:0").status, "accepted")

    def test_reserve_allows_best_effort_continuation_after_prior_overrun(self) -> None:
        plan = budget()
        plan.consumed_words = 50
        allocation = BudgetManager(plan).reserve("section:0")
        self.assertEqual(allocation.status, "reserved")

    def test_accepts_overlong_output_without_failing_article(self) -> None:
        manager = BudgetManager(budget())
        manager.reserve("section:0")
        manager.accept("section:0", 81)
        self.assertEqual(manager.budget.allocation_for("section:0").generated_words, 81)

    def test_revision_keeps_outside_range_prose_when_repair_is_not_possible(self) -> None:
        manager = BudgetManager(budget())
        manager.restore_accepted("section:0", 50)
        manager.replace_accepted("section:0", 10)
        self.assertEqual(manager.budget.allocation_for("section:0").generated_words, 10)

    async def test_out_of_budget_revision_is_repaired_before_replacement(self) -> None:
        manager = BudgetManager(budget(), max_repairs=1)
        manager.restore_accepted("section:0", 50)
        async def repair(_output, _allocation): return "fixed " * 45
        output = await manager.repair_accepted("section:0", "too short", repair)
        self.assertEqual(WordCounter.count_text(output), 45)
        self.assertEqual(manager.budget.allocation_for("section:0").generated_words, 45)
