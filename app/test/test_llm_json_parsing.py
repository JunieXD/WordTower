import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.utils.LLM import _call_llm, _parse_json_response


class LLMJsonParsingTests(unittest.TestCase):
    def test_parse_json_response_repairs_unescaped_quotes_inside_string_values(self):
        raw_content = """
{
    "is_correct": false,
    "score": 50,
    "feedback": "这是一个不错的尝试，不过还存在一些问题。首先你没有使用目标单词nowhere，而是写成了no where，正确的拼写应该是nowhere。其次句子语法存在小问题，"so far"在这里语义不够准确，原句想表达的是偏僻到找不到落脚处，另外"seems"的主语应该用it指代前面的情况。",
    "better_translation": "This small town is so remote that it seems even the wind has nowhere to stop."
}
""".strip()

        parsed = _parse_json_response(raw_content)

        self.assertEqual(parsed["is_correct"], False)
        self.assertEqual(parsed["score"], 50)
        self.assertIn('"so far"', parsed["feedback"])
        self.assertIn('"seems"', parsed["feedback"])
        self.assertEqual(
            parsed["better_translation"],
            "This small town is so remote that it seems even the wind has nowhere to stop.",
        )

    def test_parse_json_response_repairs_trailing_commas_comments_python_literals_and_smart_quotes(self):
        raw_content = """
{
    “is_correct”: True,
    "score": 88,
    // 模型偶尔会夹带注释
    "feedback": "整体不错",
    "better_translation": None,
}
""".strip()

        parsed = _parse_json_response(raw_content)

        self.assertEqual(parsed["is_correct"], True)
        self.assertEqual(parsed["score"], 88)
        self.assertEqual(parsed["feedback"], "整体不错")
        self.assertIsNone(parsed["better_translation"])

    def test_parse_json_response_repairs_raw_newlines_inside_string_values(self):
        raw_content = """
{
    "is_correct": false,
    "score": 60,
    "feedback": "第一行
第二行",
    "better_translation": "ok"
}
""".strip()

        parsed = _parse_json_response(raw_content)

        self.assertEqual(parsed["feedback"], "第一行\n第二行")


class LLMCallRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_call_llm_retries_after_unrecoverable_invalid_json(self):
        responses = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"is_correct": false, "score": ')
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"is_correct": false, "score": 50, "feedback": "ok", "better_translation": "ok"}'
                        )
                    )
                ]
            ),
        ]

        with patch(
            "app.utils.LLM.client.chat.completions.create",
            new=AsyncMock(side_effect=responses),
        ) as create_mock:
            parsed = await _call_llm("test prompt")

        self.assertEqual(parsed["score"], 50)
        self.assertEqual(create_mock.await_count, 2)


if __name__ == "__main__":
    unittest.main()
