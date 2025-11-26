from app.utils.config import settings

def get_question_prompt(type: str, target_word: str | list[str]) -> str | None:
    if type == settings.QUESTION_TYPES[0]:
        return f"""
## Role
You are a strict JSON API. Output ONLY valid JSON. Do not output markdown blocks (```json), conversational text, or internal thinking. Start with `{{` and end with `}}`.

## Task
Generate a vocabulary quiz for the target word: "{target_word}".

## Constraints
1.  **Story:** Write an engaging English story (~100 words). The target word must appear **EXACTLY ONCE**.
2.  **Context:** The surrounding context must strongly imply the meaning of the word (strong inference clues).
3.  **Language:** Story in English. Options and Explanation in **Simplified Chinese**.
4.  **Components:** 4 options (1 correct, 3 distractors).

## JSON Structure
{{
  "target_word": "String",
  "story": "String (English text)",
  "options": {{
    "A": "String (Chinese definition)",
    "B": "String (Chinese definition)",
    "C": "String (Chinese definition)",
    "D": "String (Chinese definition)"
  }},
  "correct_option": "String (A/B/C/D)",
  "explanation": "String (Chinese explanation of context clues)"
}}
"""
    elif type == settings.QUESTION_TYPES[1]:
        return f"""
## Role
You are a strict JSON API. Output ONLY valid JSON. Do not output markdown blocks (```json), conversational text, or internal thinking. Start with `{{` and end with `}}`.

## Task
Create a "Fill-in-the-Blanks" paragraph quiz using ALL of the following target words: {target_word}.

## Constraints
1.  **Narrative Cohesion:** Write a coherent, logical English paragraph (100-150 words) that naturally incorporates all the target words.
2.  **Contextual Clues (CRITICAL):** **Do not just place words in generic sentences.** For every blank, the surrounding text must provide specific clues (definitions, synonyms, antonyms, or cause-and-effect logic) that point to the missing word.
    * *Bad Example:* "He looked at the ____[1]____." (Could be anything)
    * *Good Example:* "The sun was setting and the sky turned pink, creating a beautiful ____[1]____." (Context implies 'view' or 'scenery').
3.  **Logical Uniqueness:** Ensure that among the provided target words, ONLY the correct word makes logical sense in its specific blank. Avoid ambiguity where two target words could be swapped grammatically.
4.  **Blanks:** Replace the target words in the text with numbered placeholders in the format `____[n]____`.
5.  **Word Form:** Use the words exactly as provided if possible.

## Output Rules (CRITICAL)
1.  **NO conversational text:** Do not say "Here is the JSON", "Wait", "Let me correct", or "I found a mistake".
2.  **NO internal monologue:** Perform all reasoning, shuffling, and checking silently.
3.  **Start and End:** The output must start strictly with `{{` and end with `}}`.
4.  **Valid JSON:** Ensure the JSON is parseable without errors.

## JSON Structure
{{
  "cloze_text": "String (The English text with ____[n]____ placeholders)",
  "shuffled_options": ["String", "String", ...], // The input words in a random order
  "correct_sequence": ["String", "String", ...], // The correct answer for [1], [2], etc. in order
  "chinese_translation": "String (The COMPLETE Chinese story. No blanks, no brackets.)"
}}
"""
    elif type == settings.QUESTION_TYPES[2]:
        return f"""
## Role
You are a strict JSON API. Output ONLY valid JSON. Do not output markdown blocks (```json), conversational text, or internal thinking. Start with `{{` and end with `}}`.

## Task
Create a translation challenge based on the target word: "{target_word}".

## Constraints
1.  **Source Sentence:** Create a natural, modern **Chinese sentence** (15-30 words) where the logic strongly fits the meaning of the `target_word`.
2.  **Reference:** Provide a standard English translation of that Chinese sentence that uses the `target_word`.
3.  **Difficulty:** The Chinese sentence should be clear and not overly poetic or archaic.
4.  **Format:** Output strictly valid JSON only.

## Output Rules (CRITICAL)
1.  **NO conversational text:** Do not say "Here is the JSON", "Wait", "Let me correct", or "I found a mistake".
2.  **NO internal monologue:** Perform all reasoning, shuffling, and checking silently.
3.  **Start and End:** The output must start strictly with `{{` and end with `}}`.
4.  **Valid JSON:** Ensure the JSON is parseable without errors.

## JSON Structure
{{
  "target_word": "String",
  "chinese_sentence": "String (The Chinese sentence for the user to translate)",
  "reference_answer": "String (The ideal English translation using the target word)"
}}
"""
    else:
        return None

def get_answer_check_prompt(target_word: str, chinese_sentence: str, user_input: str) -> str:
    return f"""
## Role
You are a strict JSON API. Output ONLY valid JSON. Do not output markdown blocks (```json), conversational text, or internal thinking. Start with `{{` and end with `}}`.

## Task
Evaluate the user's translation based on the `target_word` and the original `chinese_sentence`.

## Input Data
- Target Word: "{target_word}"
- Chinese Sentence: "{chinese_sentence}"
- User Input: "{user_input}"

## Evaluation Criteria
1.  **Constraint Check:** Did the user include the `target_word` (or its correct grammatical form)? If not, mark as incorrect.
2.  **Meaning:** Does the English translation accurately reflect the Chinese meaning?
3.  **Grammar:** Is the sentence grammatically correct?

## Feedback Style Guidelines (CRITICAL)
1.  **Direct Address:** ALWAYS address the user as "**你**" (You). NEVER use "用户" (The user).
2.  **Tone:**
    -   **High Score (80-100):** Be enthusiastic and praising (e.g., "太棒了！", "写得真好！").
    -   **Low Score (0-79):** Be supportive and gentle. Acknowledge the effort first, then correct the mistake (e.g., "这是一个不错的尝试，但是...", "别灰心，我们来看看怎么调整").
3.  **Content:** Combine specific corrections with encouragement. Avoid robotic reporting.

## Output Rules (Strict)
1.  **NO conversational text:** Output ONLY the JSON object.
2.  **NO internal monologue:** Do not output thinking process.
3.  **Start/End:** Start with `{{` and end with `}}`.
4.  Output strictly valid JSON only. The `feedback` must be in **Simplified Chinese**.

## JSON Structure
{{
  "is_correct": Boolean,  // true if meaning is close AND target word is used AND grammar is acceptable
  "score": Number,        // 0-100
  "feedback": "String",   // Specific feedback in Chinese. Point out grammar errors or if the word was missing.
  "better_translation": "String" // A polished version of the user's sentence (or the standard answer if user was way off)
}}
"""