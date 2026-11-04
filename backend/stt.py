"""Streaming client for Gnani Prisma speech-to-text over WebSocket.

Prisma expects raw PCM16 mono audio in frames of exactly 1,024 bytes
(512 samples), sent in real time. All configuration goes in the upgrade
headers. It replies with JSON events; `transcript` events carry final text
for one VAD segment. With partials enabled, `partial_transcript` events
stream in while someone speaks and the final event is `final_transcript`.
"""

import asyncio
import json
from collections.abc import AsyncIterator

import websockets

from . import config

FRAME_BYTES = 1024
FRAME_SAMPLES = FRAME_BYTES // 2
FINAL_EVENTS = {"transcript", "final_transcript"}


class PrismaStream:
    def __init__(
        self,
        lang: str = config.STT_LANG,
        model: str = config.STT_MODEL,
        sample_rate: int = config.STT_SAMPLE_RATE,
    ):
        self.lang = lang
        self.model = model
        self.sample_rate = sample_rate
        self._ws = None
        self._buffer = bytearray()

    @property
    def frame_seconds(self) -> float:
        return FRAME_SAMPLES / self.sample_rate

    def _headers(self) -> dict[str, str]:
        headers = {
            "x-api-key-id": config.require_key(),
            "lang_code": self.lang,
            "x-model": self.model,
            "x-sample-rate": str(self.sample_rate),
            "x-min-silence-ms": config.STT_MIN_SILENCE_MS,
            "x-max-speech-s": config.STT_MAX_SPEECH_S,
            "x-idle-timeout-sec": "300",
        }
        if self.model.startswith("prisma-v3"):
            headers["x-keyterms"] = json.dumps(config.STT_KEYTERMS)
            if config.STT_PARTIALS:
                headers["x-partials"] = "true"
        return headers

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            config.STT_URL,
            additional_headers=self._headers(),
            max_size=None,
        )

    async def send_audio(self, pcm: bytes) -> None:
        """Queue PCM16 audio and send every complete 1,024-byte frame."""
        self._buffer.extend(pcm)
        while len(self._buffer) >= FRAME_BYTES:
            frame = bytes(self._buffer[:FRAME_BYTES])
            del self._buffer[:FRAME_BYTES]
            await self._ws.send(frame)

    async def flush(self, silence_ms: int = 800) -> None:
        """Send trailing silence at real-time pace so VAD closes the last segment."""
        silence = b"\x00" * FRAME_BYTES
        for _ in range(max(1, int(silence_ms / 1000 / self.frame_seconds))):
            await self.send_audio(silence)
            await asyncio.sleep(self.frame_seconds)

    async def commit(self) -> None:
        """Flush leftover audio (zero-padded) and close the open utterance."""
        if self._buffer:
            pad = FRAME_BYTES - len(self._buffer)
            await self._ws.send(bytes(self._buffer) + b"\x00" * pad)
            self._buffer.clear()
        if self.model.startswith("prisma-v3"):
            await self._ws.send(json.dumps({"type": "commit"}))

    async def events(self) -> AsyncIterator[dict]:
        try:
            async for message in self._ws:
                if isinstance(message, str):
                    yield json.loads(message)
        except websockets.ConnectionClosed:
            return

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def __aenter__(self) -> "PrismaStream":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()


async def stream_pcm_file(stream: PrismaStream, pcm: bytes) -> None:
    """Send a whole PCM buffer at real-time pace (Prisma rejects bursts)."""
    for i in range(0, len(pcm), FRAME_BYTES):
        await stream.send_audio(pcm[i:i + FRAME_BYTES])
        await asyncio.sleep(stream.frame_seconds)
    await stream.commit()
