if __name__ == "__main__":
    import os
    from openai import OpenAI
    from app.utils.config import settings

    client = OpenAI(
        base_url=settings.MY_API_BASE_URL,
        api_key=settings.MY_API_KEY,
    )

    response = client.chat.completions.create(
        model=settings.MY_API_MODEL_ID,
        messages=[{ "role": "user", "content": "hello" }],
        extra_body={ "thinking": { "type": "disabled" } }
    )

    print(response.choices[0])