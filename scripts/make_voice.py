"""Voice Dadi's pre-recorded lines with Timbre, skipping any already made.

    uv run python -m scripts.make_voice           # only missing lines
    uv run python -m scripts.make_voice --force   # all of them
"""

import argparse
import asyncio

from backend import config, tts
from backend.lines import LINES, PAPPU_LINES

OUT = config.ROOT / "frontend" / "audio"


async def main(force: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for key, text in LINES.items():
        path = OUT / f"{key}.mp3"
        if path.exists() and not force:
            continue
        voice = config.PAPPU_VOICE if key in PAPPU_LINES else config.DADI_VOICE
        path.write_bytes(await tts.synthesize(text, "hi-IN", voice=voice, model=config.TTS_MODEL, speed=config.DADI_SPEED))
        made += 1
        print(key)
    print(f"Made {made}; total {len(LINES)} lines")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    asyncio.run(main(parser.parse_args().force))
