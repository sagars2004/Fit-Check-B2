import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.services.vision import extract_garments_with_vision


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
async def call_gmi(settings):
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://picsum.photos/400/400")
        img_bytes = resp.content
    print("Calling vision model...")
    res = await extract_garments_with_vision(img_bytes, 400, 400, settings)
    if not res:
        raise Exception("Failed")
    return res


async def main():
    settings = Settings()
    try:
        res = await call_gmi(settings)
        print("Success:", res)
    except Exception:
        print("Final failure")


asyncio.run(main())
