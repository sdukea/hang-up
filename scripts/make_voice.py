"""Voice Dadi's pre-recorded lines with Timbre, skipping any already made.

    uv run python -m scripts.make_voice             # only missing lines
    uv run python -m scripts.make_voice --force     # all of them
    uv run python -m scripts.make_voice --lang en   # the English lines, into audio/en
    uv run python -m scripts.make_voice --role didi # Pinky's lines, into audio/didi (and didi/en)
"""

import argparse
import asyncio

from backend import character, config, tts
from backend.lines import LINES, LINES_DADAJI, LINES_DADAJI_EN, LINES_DIDI, LINES_DIDI_EN, LINES_EN, PAPPU_LINES

AUDIO = config.ROOT / "frontend" / "audio"


async def main(force: bool, lang: str, role: str) -> None:
    sets = {"dadi": (LINES, LINES_EN), "didi": (LINES_DIDI, LINES_DIDI_EN), "dadaji": (LINES_DADAJI, LINES_DADAJI_EN)}
    lines = sets[role][1 if lang == "en" else 0]
    out = AUDIO / character.ROLES[role]["audio"] / ("en" if lang == "en" else "")
    out.mkdir(parents=True, exist_ok=True)
    made = 0
    for key, text in lines.items():
        path = out / f"{key}.mp3"
        if path.exists() and not force:
            continue
        if role == "dadi":
            voice, model = (config.PAPPU_VOICE if key in PAPPU_LINES else config.DADI_VOICE), config.TTS_MODEL
        else:
            voice, model = character.ROLES[role]["voice"], character.ROLES[role]["model"]
        path.write_bytes(await tts.synthesize(text, config.TTS_LANGS[lang], voice=voice, model=model, speed=config.DADI_SPEED))
        made += 1
        print(key)
    print(f"Made {made}; total {len(lines)} lines")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--lang", choices=["hi", "en"], default="hi")
    parser.add_argument("--role", choices=sorted(character.ROLES), default="dadi")
    args = parser.parse_args()
    asyncio.run(main(args.force, args.lang, args.role))
