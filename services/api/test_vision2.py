import asyncio
from app.core.config import Settings
from app.services.vision import extract_garments_with_vision
import httpx

async def main():
    settings = Settings()
    settings.gmi_vision_model = 'Qwen/Qwen3.5-35B-A3B'
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://picsum.photos/400/400")
        img_bytes = resp.content

    print("Calling vision model with Qwen3.5-35B-A3B...")
    res = await extract_garments_with_vision(img_bytes, 400, 400, settings)
    print(res)

asyncio.run(main())
