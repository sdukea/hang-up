"""Gnani Timbre text-to-speech: REST for saved lines, SSE for live replies."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator

import httpx

from . import config


class TTSError(RuntimeError):
    pass


# Timbre allows only one active request per account (429 RATE_LIMITED
# otherwise), so every synthesis in this process goes through one queue.
_one_at_a_time = asyncio.Lock()


async def synthesize(
    text: str,
    language: str = "hi-IN",
    voice: str = config.TTS_VOICE,
    model: str = config.TTS_MODEL,
    sample_rate: int = 24000,
    speed: float = 1.0,
) -> bytes:
    """Return MP3 audio for `text`. Write numbers as words for best results."""
    payload = {
        "text": text,
        "voice": voice,
        "model": model,
        "language": language,
        "speed": speed,
        "audio_config": {
            "sample_rate": sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "container": "mp3",
            "bitrate": "64k",
        },
    }
    headers = {"X-API-Key-ID": config.require_key(), "Content-Type": "application/json"}
    async with _one_at_a_time, httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3):
            try:
                resp = await client.post(config.TTS_URL, json=payload, headers=headers)
            except httpx.HTTPError as e:
                raise TTSError(f"Could not reach Timbre: {e.__class__.__name__}") from e
            if resp.status_code != 429:
                break
            # Another process (or a request still finishing) holds the slot.
            await asyncio.sleep(1.5 * (attempt + 1))
    if resp.status_code != 200:
        raise TTSError(f"TTS failed ({resp.status_code}): {resp.text[:300]}")
    return resp.content


async def stream(
    text: str,
    language: str = "hi-IN",
    voice: str = config.TTS_VOICE,
    model: str = config.TTS_MODEL,
    speed: float = 1.0,
) -> AsyncIterator[bytes]:
    """Yield MP3 frames as Timbre makes them, so a reply starts in well under a second."""
    payload = {
        "text": text, "voice": voice, "model": model, "language": language, "speed": speed,
        "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2, "container": "mp3", "bitrate": "64k"},
    }
    headers = {"X-API-Key-ID": config.require_key(), "Content-Type": "application/json"}
    try:
        async with _one_at_a_time, httpx.AsyncClient(timeout=30) as client:
            for attempt in range(2):
                async with client.stream("POST", config.TTS_SSE_URL, json=payload, headers=headers) as resp:
                    if resp.status_code == 429 and attempt == 0:
                        await asyncio.sleep(0.8)  # another process still holds the slot
                        continue
                    if resp.status_code != 200:
                        raise TTSError(f"TTS failed ({resp.status_code})")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = json.loads(line[5:]).get("audio")
                        if chunk:
                            yield base64.b64decode(chunk)
                    return
    except (httpx.HTTPError, ValueError) as e:
        raise TTSError(f"Could not stream Timbre: {e.__class__.__name__}") from e
