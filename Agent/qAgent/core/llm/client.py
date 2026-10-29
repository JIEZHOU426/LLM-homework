"""Construction of the OpenAI-compatible async client."""

from __future__ import annotations

from openai import AsyncOpenAI

from ..config import Settings


def create_async_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=settings.request_timeout,
    )
