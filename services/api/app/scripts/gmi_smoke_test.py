from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.providers.gmi import GMICloudCapabilityClient


async def _run() -> None:
    result = await GMICloudCapabilityClient(get_settings()).smoke_test()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_run())
