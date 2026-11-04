"""Gnani Timbre text-to-speech (REST)."""

import asyncio

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
