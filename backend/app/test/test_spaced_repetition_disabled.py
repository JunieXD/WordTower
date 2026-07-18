import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.spaced_repetition import (
    estimate_word_next_review_days,
    rank_words_with_srs_priority,
)


class SpacedRepetitionDisabledTests(unittest.TestCase):
    @patch("app.services.spaced_repetition.settings.SRS_ENABLED", False)
    @patch("app.services.spaced_repetition.random.shuffle")
    def test_disabled_srs_only_shuffles_candidates(self, shuffle_mock):
        words = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        result = rank_words_with_srs_priority(None, None, words)

        self.assertEqual(result, words)
        self.assertIsNot(result, words)
        shuffle_mock.assert_called_once_with(result)

    @patch("app.services.spaced_repetition.settings.SRS_ENABLED", False)
    def test_disabled_srs_does_not_query_review_history(self):
        word = SimpleNamespace(id=1)

        result = estimate_word_next_review_days(None, None, word)

        self.assertEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main()
