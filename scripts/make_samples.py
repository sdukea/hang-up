"""Generate the demo workers' spoken answers with real-world background noise.

    uv run python -m scripts.make_samples            # only missing files
    uv run python -m scripts.make_samples --force    # regenerate everything

Each answer is synthesized with Timbre at 16 kHz, padded with a little
silence, and mixed with a soundscape that matches where the worker is
speaking (kitchen, street, home, a phone by the road).

Output:
  out/samples-wav/<id>/<question>.wav   full-quality WAV, for scripts.stream_file
  frontend/samples/<id>/<question>.m4a  AAC (~6x smaller) that the demo
                                        decodes in the browser and streams to Prisma

Encoding uses macOS `afconvert`. Compression doesn't change what Prisma hears.
"""

import argparse
import array
import asyncio
import io
import math
import random
import subprocess
import wave
from pathlib import Path

from backend import config, tts
from backend.questions import QUESTION_IDS
from backend.samples import SAMPLES

RATE = 16000
OUT = config.ROOT / "frontend" / "samples"
WAV_OUT = config.ROOT / "out" / "samples-wav"

# Speech-to-noise ratio per scene, in dB. Low enough to be realistic, high
# enough that a person standing there would still follow the conversation.
SNR_DB = {"kitchen": 14, "street_night": 12, "roadside_phone": 9, "home_tv": 13, "traffic": 10}


# ---------- signal helpers ----------

def lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / RATE)
    y, prev = [0.0] * len(x), 0.0
    for i, v in enumerate(x):
        prev = (1 - a) * v + a * prev
        y[i] = prev
    return y


def highpass(x, cutoff):
    low = lowpass(x, cutoff)
    return [v - lv for v, lv in zip(x, low)]


def rms(x):
    return math.sqrt(sum(v * v for v in x) / max(1, len(x))) or 1e-9


def white(n, rng):
    return [rng.gauss(0, 1) for _ in range(n)]


def brown(n, rng, leak=0.995):
    y, acc = [0.0] * n, 0.0
    for i in range(n):
        acc = leak * acc + rng.gauss(0, 1)
        y[i] = acc
    return y


def add_event(base, event, start):
    for i, v in enumerate(event):
        j = start + i
        if 0 <= j < len(base):
            base[j] += v


def envelope(n, attack, release):
    a, r = max(1, int(attack * RATE)), max(1, int(release * RATE))
    return [min(1.0, i / a, (n - i) / r) for i in range(n)]


# ---------- sound events ----------

def horn(rng):
    dur = rng.uniform(0.25, 0.7)
    n = int(dur * RATE)
    f1, f2 = rng.choice([(420, 520), (350, 440), (480, 600)])
    env = envelope(n, 0.02, 0.05)
    return [0.6 * env[i] * (math.copysign(1, math.sin(2 * math.pi * f1 * i / RATE))
                            + 0.7 * math.copysign(1, math.sin(2 * math.pi * f2 * i / RATE))) for i in range(n)]


def passing_vehicle(rng):
    dur = rng.uniform(2.0, 4.0)
    n = int(dur * RATE)
    rumble = lowpass(brown(n, rng), 300)
    peak = rms(rumble)
    return [math.sin(math.pi * i / n) ** 2 * v / peak * 1.5 for i, v in enumerate(rumble)]


def clink(rng):
    n = int(0.25 * RATE)
    f = rng.uniform(2200, 4200)
    return [math.exp(-i / (0.04 * RATE)) * math.sin(2 * math.pi * f * i / RATE) * 1.2 for i in range(n)]


def cooker_whistle(rng):
    n = int(rng.uniform(1.4, 2.2) * RATE)
    hiss = highpass(white(n, rng), 1500)
    env = envelope(n, 0.15, 0.3)
    return [env[i] * (0.9 * math.sin(2 * math.pi * (1900 + 60 * math.sin(2 * math.pi * 6 * i / RATE)) * i / RATE)
                      + 0.5 * hiss[i]) for i in range(n)]


# ---------- scenes ----------

def scene_noise(scene, n, rng):
    if scene in ("traffic", "street_night", "roadside_phone"):
        bed = lowpass(brown(n, rng), 400)
        g = 1 / rms(bed)
        noise = [v * g for v in bed]
        hiss = highpass(white(n, rng), 2000)
        for i in range(n):
            noise[i] += 0.15 * hiss[i]
        busy = {"traffic": (0.5, 0.35), "street_night": (0.25, 0.12), "roadside_phone": (0.6, 0.45)}[scene]
        seconds = n / RATE
        for _ in range(int(seconds * busy[0])):
            add_event(noise, passing_vehicle(rng), rng.randrange(n))
        for _ in range(int(seconds * busy[1])):
            add_event(noise, horn(rng), rng.randrange(n))
        return noise
    if scene == "kitchen":
        bed = lowpass(brown(n, rng), 600)
        g = 0.6 / rms(bed)
        noise = [v * g for v in bed]
        for _ in range(int(n / RATE * 0.6)):
            add_event(noise, clink(rng), rng.randrange(n))
        if rng.random() < 0.45:  # the cooker whistles on some answers
            add_event(noise, cooker_whistle(rng), rng.randrange(int(n * 0.2), int(n * 0.7)))
        return noise
    if scene == "home_tv":
        # TV dialogue: band-limited noise shaped like syllables; fan: hum + whoosh.
        tv = highpass(lowpass(white(n, rng), 3000), 300)
        syl, phase, rate = [0.0] * n, 0.0, 4.5
        for i in range(n):
            if i % (RATE // 4) == 0:
                rate = rng.uniform(3, 6)
            phase += 2 * math.pi * rate / RATE
            syl[i] = max(0.0, math.sin(phase)) ** 2
        fan = lowpass(white(n, rng), 800)
        g_tv, g_fan = 1 / rms(tv), 0.5 / rms(fan)
        return [tv[i] * g_tv * syl[i] + fan[i] * g_fan * (1 + 0.2 * math.sin(2 * math.pi * 0.7 * i / RATE))
                + 0.15 * math.sin(2 * math.pi * 100 * i / RATE) for i in range(n)]
    raise ValueError(scene)


def phone_band(x):
    """Cheap phone mic: 300–3400 Hz and a little soft clipping."""
    y = lowpass(highpass(x, 300), 3400)
    return [math.tanh(1.5 * v) / 1.5 for v in y]


# ---------- assembly ----------

def read_wav(data: bytes) -> list[float]:
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
        return [v / 32768 for v in array.array("h", w.readframes(w.getnframes()))]


def write_wav(path: Path, x: list[float]) -> None:
    peak = max(1e-9, max(abs(v) for v in x))
    gain = min(1.0, 0.9 / peak)
    pcm = array.array("h", (int(max(-1, min(1, v * gain)) * 32767) for v in x))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def mix(speech: list[float], scene: str, rng: random.Random) -> list[float]:
    lead, trail = [0.0] * int(0.4 * RATE), [0.0] * int(0.8 * RATE)
    speech = lead + speech + trail
    noise = scene_noise(scene, len(speech), rng)
    target = rms([v for v in speech if v]) / (10 ** (SNR_DB[scene] / 20))
    g = target / rms(noise)
    out = [s + g * n for s, n in zip(speech, noise)]
    return phone_band(out) if scene == "roadside_phone" else out


async def main(force: bool) -> None:
    for sample in SAMPLES:
        for index, (qid, text) in enumerate(zip(QUESTION_IDS, sample["answers"])):
            wav_path = WAV_OUT / sample["id"] / f"{qid}.wav"
            m4a_path = OUT / sample["id"] / f"{qid}.m4a"
            if force or not wav_path.exists():
                wav = await tts.synthesize(text, sample["language"], voice=sample["voice"],
                                           model=sample["model"], sample_rate=RATE, speed=sample["speed"])
                rng = random.Random(f"{sample['id']}-{qid}")
                write_wav(wav_path, mix(read_wav(wav), sample["scene"], rng))
            if force or not m4a_path.exists():
                m4a_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "40000",
                                str(wav_path), str(m4a_path)], check=True)
                print(f"{m4a_path.relative_to(config.ROOT)}  {m4a_path.stat().st_size // 1024} KB  {sample['scene']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="regenerate files that already exist")
    asyncio.run(main(parser.parse_args().force))
