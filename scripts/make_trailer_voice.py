"""Voice the trailer's lines (?trailer=1) with Timbre into frontend/audio/trailer/, skipping any already made.

    uv run python -m scripts.make_trailer_voice [--force]

Each person keeps their in-game voice; pace differs a little so they feel different on the phone.
The mirror caller is a stranger's voice using the player's own words.
"""

import argparse
import asyncio

from backend import config, tts
from backend.trailer import STEPS

OUT = config.ROOT / "frontend" / "audio" / "trailer"
DADI, PINKY, DADAJI = ("Chitra", "timbre-v2.5", 0.95), ("Zahira", "timbre-v2.5", 1.1), ("Prakash", "timbre-v3.0", 0.92)
PLAYER, STRANGER = ("Vikrant", "timbre-v2.5", 1.05), ("Deepak", "timbre-v2.5", 0.98)

LINES = {
    "d_hello": (DADI, "हैलो?"),
    **{s["clip"]: (DADI, s["reply"]) for s in STEPS},
    **{s["id"]: (PLAYER, s["said"]) for s in STEPS},
    "d_not_otp": (DADI, "ये OTP नहीं था, बेटा।"),
    "p_check": (PINKY, "Wait. मैं ये check करती हूँ।"),
    "j_ref": (DADAJI, "Reference number बताइए।"),
    "m_1": (STRANGER, "हेलो? मैं बैंक से बोल रहा हूँ।"),
    "m_2": (STRANGER, "आपका खाता आज बंद हो जाएगा। घबराइए मत, मैं आपकी मदद के लिए हूँ।"),
    "m_3": (STRANGER, "बस आपके फ़ोन पर एक OTP आया होगा। वो बता दीजिए।"),
}


async def main(force: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, ((voice, model, speed), text) in LINES.items():
        path = OUT / f"{key}.mp3"
        if path.exists() and not force:
            continue
        for attempt in range(6):
            try:
                path.write_bytes(await tts.synthesize(text, config.TTS_LANGS["hi"], voice=voice, model=model, speed=speed))
                break
            except tts.TTSError:
                await asyncio.sleep(3 + 3 * attempt)
        print(key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    asyncio.run(main(parser.parse_args().force))
