# Scam Dadi

**You are a fake officer. Get Kamla Dadi's OTP. Nobody said it would be easy.**

A voice game in Hindi and Hinglish. You call a 78-year-old grandmother and try
real scam tactics on her, out loud. Your "Boss" whispers what real scammers do
next. Dadi fights back with what people should really do: she calls back, asks
for your badge, gets her grandson, and catches your lies. Every call is a lesson
in disguise, and it ends by showing you how to protect the people you love.

Built on [Gnani AI](https://www.gnani.ai): **Prisma** hears you and **Timbre** is
Dadi's voice.

## Run it

```bash
cp .env.example .env   # add your Gnani key and LLM settings
uv sync
uv run python -m scripts.make_voice   # voices any missing lines
uv run uvicorn backend.main:app --port 8000
```

This is a game. Everything in it is fictional. Never say a real OTP, PIN or
account number. Getting a real scam call? Hang up and call **1930**, or report at
[cybercrime.gov.in](https://cybercrime.gov.in).
