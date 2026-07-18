import unittest

from app.utils.LLM import precheck_translation_answer


class TranslationAnswerPrecheckTests(unittest.TestCase):
    def test_precheck_rejects_copying_chinese_sentence(self):
        result = precheck_translation_answer(
            target_word="nowhere",
            chinese_sentence="这个小镇偏僻得连风都找不到停下的地方。",
            user_input="这个小镇偏僻得连风都找不到停下的地方。",
        )

        self.assertIsNotNone(result)
        self.assertFalse(result["is_correct"])
        self.assertEqual(result["score"], 0)
        self.assertIn("原中文句子", result["feedback"])

    def test_precheck_rejects_answers_containing_chinese(self):
        result = precheck_translation_answer(
            target_word="efficient",
            chinese_sentence="这台机器运行非常高效。",
            user_input="This machine is very efficient，很不错。",
        )

        self.assertIsNotNone(result)
        self.assertFalse(result["is_correct"])
        self.assertEqual(result["score"], 0)
        self.assertIn("包含中文", result["feedback"])

    def test_precheck_rejects_answers_missing_target_word(self):
        result = precheck_translation_answer(
            target_word="nowhere",
            chinese_sentence="这个小镇偏僻得连风都找不到停下的地方。",
            user_input="This small town is so remote that even the wind cannot stop.",
        )

        self.assertIsNotNone(result)
        self.assertFalse(result["is_correct"])
        self.assertEqual(result["score"], 20)
        self.assertIn("没有使用目标单词", result["feedback"])

    def test_precheck_allows_normal_english_answer(self):
        result = precheck_translation_answer(
            target_word="nowhere",
            chinese_sentence="这个小镇偏僻得连风都找不到停下的地方。",
            user_input="This small town is so remote that even the wind has nowhere to stop.",
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
