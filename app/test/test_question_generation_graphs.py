import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.db.question import generate_single_question
from app.services.question_generation.cloze_test_graph import generate_cloze_test_content
from app.services.question_generation.context_guess_graph import generate_context_guess_content
from app.services.question_generation.dispatcher import generate_question_content
from app.services.question_generation.keyword_translation_graph import generate_keyword_translation_content


class ClozeTestGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_cloze_test_content_success(self):
        target_words = ["recipe", "confused", "ingredients", "flavor"]

        async def fake_generate_text(prompt: str):
            if "完形填空草稿 Agent" in prompt:
                return {
                    "draft_text": (
                        "Chef Tony found an old [[BLANK_1:recipe]] in a drawer when he wanted to bake a cake "
                        "for his sister. He smiled because the paper explained every step in simple order. "
                        "A minute later he looked at the flour and eggs and felt [[BLANK_2:confused]] because "
                        "he had never baked alone before. His mother pointed at the sugar, milk, and butter "
                        "and said these [[BLANK_3:ingredients]] had to be measured carefully. After the cake "
                        "came out of the oven, the sweet strawberry [[BLANK_4:flavor]] filled the whole kitchen."
                    )
                }
            if "完形填空翻译 Agent" in prompt:
                return {
                    "chinese_translation": (
                        "托尼大厨想给妹妹做蛋糕时，在抽屉里找到了一份旧食谱。"
                        "他很开心，因为纸上清楚写着每一步。后来他看着面粉和鸡蛋，"
                        "因为从没独自烘焙过而感到困惑。妈妈指着糖、牛奶和黄油，"
                        "说这些原料必须仔细称量。蛋糕出炉后，甜甜的草莓味充满了整个厨房。"
                    )
                }
            return {
                "is_valid": True,
                "draft_ok": True,
                "translation_ok": True,
                "errors": [],
            }

        with patch(
            "app.services.question_generation.cloze_test_graph.generate_text",
            new=AsyncMock(side_effect=fake_generate_text),
        ):
            content = await generate_cloze_test_content(user_id=1, target_words=target_words)

        self.assertIsNotNone(content)
        self.assertEqual(content["correct_sequence"], target_words)
        self.assertEqual(Counter(content["shuffled_options"]), Counter(target_words))
        self.assertIn("____[1]____", content["cloze_text"])
        self.assertIn("____[4]____", content["cloze_text"])
        self.assertNotIn("[[BLANK_", content["cloze_text"])
        self.assertTrue(content["chinese_translation"])

    async def test_generate_cloze_test_content_retries_and_returns_none_on_invalid_draft(self):
        target_words = ["recipe", "confused", "ingredients", "flavor"]

        async def fake_generate_text(prompt: str):
            if "完形填空草稿 Agent" in prompt:
                return {
                    "draft_text": (
                        "Tony saw [[BLANK_1:recipe]] on the table and felt happy. "
                        "Later he became [[BLANK_2:confused]] in the kitchen. "
                        "He mixed the [[BLANK_3:ingredients]] together and served the cake."
                    )
                }
            if "完形填空翻译 Agent" in prompt:
                return {"chinese_translation": "托尼看到了食谱，后来感到困惑，然后把原料混合在一起。"}
            raise AssertionError("本地校验失败时不应该进入语义审核")

        with patch(
            "app.services.question_generation.cloze_test_graph.generate_text",
            new=AsyncMock(side_effect=fake_generate_text),
        ):
            content = await generate_cloze_test_content(
                user_id=1,
                target_words=target_words,
                max_retries=2,
            )

        self.assertIsNone(content)


class KeywordTranslationGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_keyword_translation_content_success(self):
        async def fake_generate_text(prompt: str):
            if "关键词翻译中文句生成 Agent" in prompt:
                return {"chinese_sentence": "这台新机器运行非常高效。"}
            if "关键词翻译参考答案 Agent" in prompt:
                return {"reference_answer": "This new machine is very efficient."}
            return {
                "is_valid": True,
                "sentence_ok": True,
                "reference_ok": True,
                "errors": [],
            }

        with patch(
            "app.services.question_generation.keyword_translation_graph.generate_text",
            new=AsyncMock(side_effect=fake_generate_text),
        ):
            content = await generate_keyword_translation_content(user_id=2, target_words=["efficient"])

        self.assertIsNotNone(content)
        self.assertEqual(content["target_word"], "efficient")
        self.assertEqual(content["chinese_sentence"], "这台新机器运行非常高效。")
        self.assertIn("efficient", content["reference_answer"].lower())


class ContextGuessGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_context_guess_content_includes_story_target_forms(self):
        async def fake_generate_text(prompt: str):
            if "基于目标单词" in prompt and '"story"' in prompt:
                return {"story": "Yesterday he went to the old station to say goodbye to his friend."}
            if "正确义项生成 Agent" in prompt:
                return {"correct_meaning": "去", "explanation": "文中描述他前往车站告别朋友，因此是“去”。"}
            if "干扰项生成 Agent" in prompt:
                return {"distractors": ["拥有", "开始", "获胜"]}
            return {
                "is_valid": True,
                "story_ok": True,
                "options_ok": True,
                "errors": [],
            }

        with (
            patch(
                "app.services.question_generation.context_guess_graph.generate_text",
                new=AsyncMock(side_effect=fake_generate_text),
            ),
            patch(
                "app.services.question_generation.context_guess_graph._lookup_dictionary_meanings_sync",
                return_value=[],
            ),
        ):
            content = await generate_context_guess_content(user_id=3, target_word="go")

        self.assertIsNotNone(content)
        self.assertEqual(content["target_word"], "go")
        self.assertEqual(content["story_target_forms"], ["went"])
        self.assertIn("went", content["story"])


class DispatcherAndQuestionFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_routes_all_types(self):
        context_mock = AsyncMock(return_value={"kind": "context"})
        cloze_mock = AsyncMock(return_value={"kind": "cloze"})
        keyword_mock = AsyncMock(return_value={"kind": "keyword"})

        with patch.dict(
            "app.services.question_generation.dispatcher.GENERATOR_REGISTRY",
            {
                "context_guess": context_mock,
                "cloze_test": cloze_mock,
                "keyword_translation": keyword_mock,
            },
            clear=False,
        ):
            context_result = await generate_question_content(1, "context_guess", ["capital"])
            cloze_result = await generate_question_content(1, "cloze_test", ["recipe", "confused"])
            keyword_result = await generate_question_content(1, "keyword_translation", ["efficient"])

        self.assertEqual(context_result["kind"], "context")
        self.assertEqual(cloze_result["kind"], "cloze")
        self.assertEqual(keyword_result["kind"], "keyword")
        context_mock.assert_awaited_once_with(1, ["capital"], 3)
        cloze_mock.assert_awaited_once_with(1, ["recipe", "confused"], 3)
        keyword_mock.assert_awaited_once_with(1, ["efficient"], 3)

    async def test_generate_single_question_uses_fallback_when_graph_returns_none(self):
        fallback_question = SimpleNamespace(id=99, type="cloze_test", content={"cloze_text": "fallback"})

        with (
            patch(
                "app.db.question._prepare_generation_data",
                return_value={
                    "q_type": "cloze_test",
                    "word_ids": [1, 2, 3, 4],
                    "word_texts": ["recipe", "confused", "ingredients", "flavor"],
                },
            ),
            patch(
                "app.db.question.generate_question_content",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.db.question._get_fallback_question",
                new=AsyncMock(return_value=fallback_question),
            ) as fallback_mock,
        ):
            result = await generate_single_question(user_id=7)

        self.assertIs(result, fallback_question)
        fallback_mock.assert_awaited_once_with(7, "cloze_test")


if __name__ == "__main__":
    unittest.main()
