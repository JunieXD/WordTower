import unittest

from app.utils.word_forms import extract_target_surface_forms, text_contains_target_form, token_matches_target


class WordFormsTests(unittest.TestCase):
    def test_token_matches_irregular_verb_form(self):
        self.assertTrue(token_matches_target("went", "go"))
        self.assertTrue(token_matches_target("gone", "go"))

    def test_text_contains_target_form_with_irregular_plural(self):
        self.assertTrue(text_contains_target_form("The children are playing outside.", "child"))

    def test_extract_target_surface_forms_returns_actual_story_form(self):
        forms = extract_target_surface_forms("Yesterday he went home, and later went back.", "go")
        self.assertEqual(forms, ["went"])


if __name__ == "__main__":
    unittest.main()
