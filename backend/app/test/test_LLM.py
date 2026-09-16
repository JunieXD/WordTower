"""Manual ECNU smoke test: uv run python -m app.test.test_LLM.

Uses the same JSON mode and concurrency limiter as production. Unit-test
discovery never makes a network request.
"""

if __name__ == "__main__":
    import asyncio
    import json

    from app.utils.LLM import client, generate_text

    async def main():
        try:
            result = await generate_text(
                'Return a JSON object with exactly these values: '
                '{"ok": true, "model": "ecnu-plus", "message": "连接成功"}'
            )
            assert result == {"ok": True, "model": "ecnu-plus", "message": "连接成功"}, result
            print(json.dumps(result, ensure_ascii=False))
        finally:
            await client.close()

    asyncio.run(main())
