# Scam Dadi

**You are a fake officer. Get Kamla Dadi's OTP. Nobody said it would be easy.**

A voice game in Hindi and Hinglish. You call a 78-year-old grandmother and try
real scam tactics on her, out loud. Your "Boss" whispers what real scammers do
next. Dadi fights back with what people should really do: she calls back, asks
for your badge, gets her grandson, and catches your lies. Every call is a lesson
in disguise, and it ends by showing you how to protect the people you love.

Every call ends the same way, whether you win or lose: your own phone rings, and a
stranger's voice reads your best line back to you. All you have to do is hang up,
because practising that is the point. The idea builds on inoculation research, which
found that playing the manipulator helps people spot manipulation
([Basol et al., 2020](https://doi.org/10.5334/joc.91)). That study was about
misinformation, and this game hasn't been tested as a scam intervention.

## How it uses Gnani AI

- **Prisma v3.0** hears you live. Its partial transcripts drive the captions, and
  Dadi cuts you off the moment you say "OTP" before you've built a story.
- **Timbre v2.5** is Dadi's voice: streamed for live replies, pre-recorded for
  instant lines.

Dadi's replies and move scoring come from a separate LLM (Gemini in our build) over
any OpenAI-compatible API, so Gnani's open-weights Evon can be swapped in.

## Privacy

Your voice goes to Gnani for transcription and your words to the LLM for Dadi's
replies. The game doesn't save audio or transcripts, and it replaces long numbers,
such as a phone or Aadhaar number, before anything reaches the LLM.

## Run it

```bash
cp .env.example .env   # add your Gnani key and LLM settings
uv sync
uv run python -m scripts.make_voice   # voices any missing lines
uv run uvicorn backend.main:app --port 8000
```

Open `/?demo=1` for a repeatable call used to record the demo: fixed Dadi, no
counter-moves and fixed scoring, with speech and replies still live, and a label on
screen saying so. Demo calls don't count towards the public scoreboard. One script
that plays it through: introduce yourself as a CBI inspector, threaten an arrest
warrant, say there are only ten minutes, tell her to tell nobody, promise to help,
then ask for the OTP.

This is a game. Everything in it is fictional. Never say a real OTP, PIN or
account number. Getting a real scam call? Hang up and call **1930**, or report at
[cybercrime.gov.in](https://cybercrime.gov.in).
