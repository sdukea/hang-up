"""Voice Dadi's pre-recorded lines with Timbre, skipping any already made.

    uv run python -m scripts.make_voice             # only missing lines
    uv run python -m scripts.make_voice --force     # all of them
    uv run python -m scripts.make_voice --lang en   # the English lines, into audio/en
"""

import argparse
import asyncio

from backend import config, tts
from backend.lines import LINES, LINES_EN, PAPPU_LINES

AUDIO = config.ROOT / "frontend" / "audio"


async def main(force: bool, lang: str) -> None:
    lines, out = (LINES_EN, AUDIO / "en") if lang == "en" else (LINES, AUDIO)
    out.mkdir(parents=True, exist_ok=True)
    made = 0
    for key, text in lines.items():
        path = out / f"{key}.mp3"
        if path.exists() and not force:
            continue
        voice = config.PAPPU_VOICE if key in PAPPU_LINES else config.DADI_VOICE
        path.write_bytes(await tts.synthesize(text, config.TTS_LANGS[lang], voice=voice, model=config.TTS_MODEL, speed=config.DADI_SPEED))
        made += 1
        print(key)
    print(f"Made {made}; total {len(lines)} lines")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--lang", choices=["hi", "en"], default="hi")
    args = parser.parse_args()
    asyncio.run(main(args.force, args.lang))
