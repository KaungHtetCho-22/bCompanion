import asyncio
import os

from dotenv import load_dotenv


async def main() -> None:
    load_dotenv(dotenv_path=".env", override=False)
    base_url = os.getenv("SEALION_BASE_URL", "https://api.sea-lion.ai/v1")
    api_key = os.getenv("SEALION_API_KEY")
    if not api_key:
        raise SystemExit("SEALION_API_KEY is not set")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0)
    models = await client.models.list()
    for m in models.data:
        print(m.id)


if __name__ == "__main__":
    asyncio.run(main())

