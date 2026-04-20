from __future__ import annotations

import httpx


async def deliver_webhook(url: str, payload: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10) as client:
        return await client.post(url, json=payload)
