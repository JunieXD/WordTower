import unittest

from app.services.question_generation.context_guess_graph import (
    _is_overly_similar_option_pair,
    _validate_option_distinctness,
)


class ContextGuessOptionRuleTests(unittest.TestCase):
    def test_rejects_unit_swapped_near_duplicate_options(self):
        errors = _validate_option_distinctness(
            {
                "A": "九十",
                "B": "九十年",
                "C": "九十岁",
                "D": "九十次",
            }
        )

        self.assertTrue(errors)

    def test_detects_age_suffix_variant_as_overly_similar(self):
        self.assertTrue(_is_overly_similar_option_pair("九十", "九十岁"))

    def test_allows_clearly_different_meanings(self):
        self.assertFalse(_is_overly_similar_option_pair("九十岁", "生日"))


if __name__ == "__main__":
    unittest.main()
