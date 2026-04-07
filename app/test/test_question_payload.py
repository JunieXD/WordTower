import unittest

from app.utils.question_payload import ensure_story_target_forms_in_payload


class QuestionPayloadTests(unittest.TestCase):
    def test_context_guess_payload_gets_missing_story_target_forms(self):
        payload = {
            "id": 1,
            "type": "context_guess",
            "content": {
                "target_word": "kick",
                "story": "Tom wanted to play, so he kicked it hard.",
                "options": {
                    "A": "踢",
                    "B": "拿",
                    "C": "放",
                    "D": "看",
                },
            },
        }

        enriched = ensure_story_target_forms_in_payload(payload)

        self.assertEqual(enriched["content"]["story_target_forms"], ["kicked"])

    def test_existing_story_target_forms_is_preserved(self):
        payload = {
            "id": 2,
            "type": "context_guess",
            "content": {
                "target_word": "go",
                "story": "Yesterday he went home.",
                "story_target_forms": ["went"],
            },
        }

        enriched = ensure_story_target_forms_in_payload(payload)

        self.assertEqual(enriched["content"]["story_target_forms"], ["went"])


if __name__ == "__main__":
    unittest.main()
