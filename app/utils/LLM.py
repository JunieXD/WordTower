from app.utils.config import settings
from openai import AsyncOpenAI
import json
from typing import Dict, Any

client = AsyncOpenAI(api_key=settings.ARK_API_KEY, base_url=settings.ARK_API_BASE_URL)

async def generate_text(prompt: str) -> Dict[str, Any]:
    response = await client.chat.completions.create(
        model=settings.ARK_API_MODEL_ID,
        messages=[
            {"role": "system", "content": "You are a strict **JSON Generation API**. You are NOT a conversational assistant. Your only purpose is to receive input and output valid JSON."},
            {"role": "user", "content": prompt}
        ],
        extra_body={"thinking": {"type": "disabled"}, "temperature": 0.1}
    )
    content = response.choices[0].message.content
    
    # 清理可能的 markdown 代码块标记
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]  # 移除 ```json
    elif content.startswith("```"):
        content = content[3:]  # 移除 ```
    
    if content.endswith("```"):
        content = content[:-3]  # 移除结尾的 ```
    
    content = content.strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        print(f"清理后的内容: {content}")
        raise ValueError(f"LLM 返回的内容不是有效的 JSON 格式: {e}")