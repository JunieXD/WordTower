from app.utils.config import settings
import random

def get_question_prompt(type: str, target_word: str | list[str]) -> str | None:
    correct_slot = random.choice(['A', 'B', 'C', 'D'])
    if type == settings.QUESTION_TYPES[0]:
        return f"""
## 任务
请根据目标单词 "{target_word}" 和 指定的正确选项位置 "{correct_slot}" 生成一个 JSON 格式的词汇测验。
## 约束条件
1. Story:
   - 必须使用 CEFR A2 (简单高中英语) 或更简单的词汇和句型（ {target_word} 除外）。
   - 篇幅约 40-60 词，{target_word} 恰好出现一次，语境线索必须指向唯一确定的含义。
2. Options (Content Rules):
   - 内容要求:
     * 包含 1 个正确义，3 个干扰项。必须将【正确项】放置在选项 "{correct_slot}" 中。将【干扰项】随机填入剩余的三个选项位置。
     * 干扰项优先选一词多义（Polysemy），若无多义则选形近词（Look-alike）。
   - 格式清洗 (Output Hygiene):
     * 选项内容只能是纯中文短语（如 "属于"）。
     * 严禁出现括号、备注、拼音、英文原词或说明性文字（如 "（干扰项）", "错误义项"）。
     * 检查：确保没有两个选项的中文意思是相同的。
3. Format: 仅输出 JSON。
## Example 1 (多义词策略)
Input:
target_word: "capital"
correct_slot: "C"
Output:
{{
  "target_word": "capital",
  "story": "Mr. Thompson wanted to open a new bakery in the town center. He had a wonderful recipe for bread and a great location picked out. However, he faced a major problem before he could start. He did not have enough money in the bank to buy the ovens and pay the rent. He needed to find a partner who could provide the necessary capital to launch his business.",
  "options": {{
    "A": "首都；首府",
    "B": "大写字母",
    "C": "启动资金",
    "D": "柱顶"
  }},
  "correct_option": "C",
  "explanation": "文中提到 Mr. Thompson 想开店但没有足够的钱（money）买设备和付房租，因此这里的 capital 指的是商业活动所需的'资金'。选项 A（城市）、B（字母格式）和 D（建筑术语）均不符合语境。"
}}
## Example 2 (形近词策略 - 当目标词无足够多义项时)
Input:
target_word: "environment"
correct_slot: "B"
Output:
{{
  "target_word": "environment",
  "story": "Sally loves to hike in the mountains every weekend. She enjoys the fresh air, the tall green trees, and the clean rivers. She believes it is important to protect the natural environment because animals need a safe home to live in. If we keep the forest clean, the earth will stay healthy for a long time.",
  "options": {{
    "A": "娱乐",
    "B": "环境",
    "C": "信封",
    "D": "参与"
  }},
  "correct_option": "B",
  "explanation": "文中提到的 fresh air, trees, rivers 以及 animals 的家，均指向大自然。选项 A、C、D 分别是与 environment 拼写或发音相近的词汇（Entertainment/Envelope/Engagement），但含义完全不符。"
}}
## JSON 结构
{{
  "target_word": "英文单词",
  "story": "英文故事",
  "options": {{
    "A": "中文释义",
    "B": "中文释义",
    "C": "中文释义",
    "D": "中文释义"
  }},
  "correct_option": "A/B/C/D",
  "explanation": "中文解析：结合文中简单词汇线索，解释为何选此义，而非其他多义项。"
}}
"""
    elif type == settings.QUESTION_TYPES[1]:
        return f"""
## 任务
使用以下所有目标单词创建一个“完形填空”段落测验：{target_word}。

## 约束条件
1. 数量严格匹配:
    - 输入数量 = 填空数量： 如果输入的 `target_word` 列表包含 N 个单词，生成的段落必须包含恰好 N 个占位符。
    - 一一对应： 每个目标单词必须使用一次且仅一次。严禁遗漏单词或重复使用单词。
    - 顺序编号： 占位符必须从 `____[1]____` 编号到 `____[N]____`。
2. 叙事连贯性： 撰写一个连贯、逻辑通顺的英语段落（150-200 词），自然地包含所有目标单词。必须使用 CEFR A2 (简单高中英语) 或更简单的词汇和句型（ 目标单词除外）。
3. 语境线索 (CRITICAL):
  - 不要只是把单词放在通用的句子中。
  - 对于每个空格，周围的文本必须提供指向缺失单词的具体线索（如定义、同义词、反义词或因果逻辑）。
  - 错误示例： "He looked at the ____[1]____."
  - 正确示例： "The sun was setting and the sky turned pink, creating a beautiful ____[1]____." (语境暗示了 'view' 或 'scenery')。
4. 逻辑唯一性： 确保在提供的目标单词中，只有正确的单词在其特定空格中在逻辑上是通顺的。
5. 单词形式： 必须按原样使用提供的单词（不要更改时态或词性，除非语法绝对不通顺，但即便如此也要尽量保持原词）。

## Example (4-Word Logic Chain)
Input: 
target_word: ["recipe", "ingredients", "confused", "flavor"]

Output:
{{
  "cloze_text": "Chef Tony wanted to bake a special cake, but he lost the paper with the instructions. Without the ____[1]____, he did not know the correct steps to follow. He looked at the flour, sugar, and eggs on the table, feeling ____[2]____ about how much to use. He decided to guess the amounts of the ____[3]____ and mixed them all together. Luckily, the final result was delicious and the ____[4]____ tasted like sweet strawberries.",
  "shuffled_options": ["ingredients", "flavor", "recipe", "confused"],
  "correct_sequence": ["recipe", "confused", "ingredients", "flavor"],
  "chinese_translation": "托尼大厨想烤一个特别的蛋糕，但他弄丢了写着说明的那张纸。没有食谱，他不知道该遵循的正确步骤。他看着桌子上的面粉、糖和鸡蛋，对该用多少感到困惑。他决定猜测原料的用量，并把它们混合在一起。幸运的是，最终结果很美味，味道尝起来像甜草莓。"
}}

## JSON 结构
{{
"cloze_text": "字符串（包含 [n] 占位符的英文文本）",
"shuffled_options": ["字符串", "字符串", ...], // 随机排序的输入单词列表
"correct_sequence": ["字符串", "字符串", ...], // 对应 [1], [2] 等空格的正确答案顺序
"chinese_translation": "字符串（完整的中文故事翻译。不要留空，不要包含括号或占位符。）"
}}
"""
    elif type == settings.QUESTION_TYPES[2]:
        return f"""
## 任务
基于目标单词 "{target_word}" 创建一个翻译任务。

## 约束条件
- 中文原句：创建一个自然、现代的中文句子（10-20 字），其中的逻辑要紧密贴合 target_word 的含义。
- 参考译文：提供该中文句子的标准英语翻译，且必须使用 target_word。
- 难度：中文句子应清晰易懂，使用简单常见的词汇（CEFR A2 级别，简单高中词汇），避免过于诗意化或使用生僻古语。

## Example
Input:
target_word: "efficient"

Output:
{
  "target_word": "efficient",
  "chinese_sentence": "这台新打印机非常高效，每分钟能打印五十页。",
  "reference_answer": "This new printer is very efficient and can print fifty pages per minute"
}

## JSON 结构
{{
"target_word": "字符串",
"chinese_sentence": "字符串（供用户翻译的中文句子）",
"reference_answer": "字符串（使用目标单词的理想英文翻译）"
}}
"""
    else:
        return None

def get_answer_check_prompt(target_word: str, chinese_sentence: str, user_input: str) -> str:
    return f"""
## 任务
基于 target_word（目标单词）和原始的 chinese_sentence（中文原句）来评估用户的翻译。
## 输入数据
目标单词: "{target_word}"
中文原句: "{chinese_sentence}"
用户输入: "{user_input}"
## 评估标准
- 约束检查：用户是否包含了 target_word（或其正确的语法形式）？如果没有，标记为错误。
- 语义：英文翻译是否准确反映了中文原意？
- 语法：句子的语法是否正确？
- 以上都达到可以接受的水平，即可判定为正确。
- 如果翻译得很准确，分数可以打到 100 分。
## 反馈风格指南
直接称呼：务必在反馈中称呼用户为“你”。严禁使用第三人称“用户”或“The user”。
语气：
- 高分 (80-100)：热情洋溢，充满赞赏（例如：“太棒了！”，“写得真好！”）。
- 低分 (0-79)：提供支持，语气温和。先肯定用户的尝试，然后再纠正错误（例如：“这是一个不错的尝试，但是……”，“别灰心，我们来看看怎么调整”）。
- 内容：将具体的修改建议与鼓励结合起来。避免像机器人一样生硬地汇报错误。
## JSON Structure (JSON 结构)
{{
"is_correct": Boolean,  // true：如果含义接近 且 使用了目标单词 且 语法可接受
"score": Number,        // 0-100
"feedback": "String",   // 中文的具体反馈。指出语法错误或是否漏掉了单词。
"better_translation": "String" // 用户句子的润色版本（如果用户偏差太大，则提供标准答案）
}}
"""