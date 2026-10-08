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

    async def test_impossible_output_is_rejected_without_consumption(self) -> None:
        manager = BudgetManager(budget(), max_repairs=1)

        async def generate(): return "short"
        async def repair(_output, _allocation): return "still short"

        with self.assertRaisesRegex(BudgetError, "unit_budget_unsatisfied"):
            await manager.generate_and_accept("section:0", generate, repair)
        self.assertEqual(manager.budget.consumed_words, 0)
        self.assertEqual(manager.budget.allocation_for("section:0").status, "planned")

    def test_reserve_rejects_state_that_would_starve_remaining_units(self) -> None:
        plan = budget()
        plan.consumed_words = 50
        with self.assertRaisesRegex(BudgetError, "remaining_budget_cannot_cover_required_units"):
            BudgetManager(plan).reserve("section:0")

    def test_accept_rejects_output_that_starves_remaining_units(self) -> None:
        manager = BudgetManager(budget())
        manager.reserve("section:0")
        with self.assertRaisesRegex(BudgetError, "violates its word allocation"):
            manager.accept("section:0", 81)

    def test_revision_revalidates_the_accepted_unit_budget(self) -> None:
        manager = BudgetManager(budget())
        manager.restore_accepted("section:0", 50)
        with self.assertRaisesRegex(BudgetError, "revision violates"):
            manager.replace_accepted("section:0", 10)

    async def test_out_of_budget_revision_is_repaired_before_replacement(self) -> None:
        manager = BudgetManager(budget(), max_repairs=1)
        manager.restore_accepted("section:0", 50)
        async def repair(_output, _allocation): return "fixed " * 45
        output = await manager.repair_accepted("section:0", "too short", repair)
        self.assertEqual(WordCounter.count_text(output), 45)
        self.assertEqual(manager.budget.allocation_for("section:0").generated_words, 45)

