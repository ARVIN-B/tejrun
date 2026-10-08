import unittest

from apps.article_agent.application.style import HumanStyleAnalyzer


class HumanStyleAnalyzerTests(unittest.TestCase):
    def test_detects_intentionally_mechanical_template_prose(self):
        text = "In this article, it is important to note that the same point matters. " * 4
        metrics = HumanStyleAnalyzer().analyze(text, ["point"])
        self.assertGreater(metrics.generic_opening_count, 0)
        self.assertGreater(metrics.repeated_phrase_count, 0)
        self.assertGreater(metrics.template_phrase_score, 0)
        self.assertGreater(metrics.keyword_stuffing_score, 0)

    def test_does_not_purpose_detector_evasion(self):
        metrics = HumanStyleAnalyzer().analyze("A concrete explanation with a practical example.")
        self.assertEqual(metrics.meta_language_count, 0)
