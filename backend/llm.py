"""Minimal client for any OpenAI-compatible chat completions API.

Works with hosted providers and self-hosted servers (vLLM, Ollama, etc.),
including Gnani's open-weights Evon served behind an OpenAI-compatible
endpoint. Configure LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env.
"""

import asyncio
import json
import logging
import re
import time

import httpx

from . import config

log = logging.getLogger("dadi.llm")


class LLMError(RuntimeError):
    pass


class LLMBadOutput(LLMError):
    """The provider answered, but not with something usable. It isn't an outage."""


HEDGE_SECONDS = 3.0
FAILS_BEFORE_PAUSE = 3
PAUSE_SECONDS = 30.0
_fails_in_a_row = 0
_paused_until = 0.0


async def _post(client: httpx.AsyncClient, model: str, system: str, user: str, temperature: float) -> httpx.Response:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    if config.LLM_REASONING_EFFORT:
        payload["reasoning_effort"] = config.LLM_REASONING_EFFORT
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    return await client.post(url, json=payload, headers=headers)


async def complete_json(system: str, user: str, temperature: float = 0.2) -> dict:
    if not config.LLM_BASE_URL or not config.LLM_MODEL:
        raise LLMError("LLM is not configured. Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env.")

    async with httpx.AsyncClient(timeout=7) as client:
        main = asyncio.create_task(_attempt(client, config.LLM_MODEL, system, user, temperature))
        tasks = [main]
        if config.LLM_FALLBACK_MODEL and config.LLM_FALLBACK_MODEL != config.LLM_MODEL:
            tasks.append(asyncio.create_task(_backup(main, client, system, user, temperature)))
        try:
            error = None
            for finished in asyncio.as_completed(tasks):
                try:
                    return await finished
                except LLMError as e:
                    error = e
            raise error
        finally:
            for task in tasks:
                task.cancel()


async def complete_live(system: str, user: str, temperature: float, deadline: float) -> dict:
    """For a player waiting on a call: once the provider is clearly down, stop making them wait for it."""
    global _fails_in_a_row, _paused_until
    if time.monotonic() < _paused_until:
        raise LLMError("skipped while the LLM is down")
    try:
        data = await asyncio.wait_for(complete_json(system, user, temperature), timeout=deadline)
    except LLMBadOutput:
        _fails_in_a_row = 0
        raise
    except (LLMError, asyncio.TimeoutError) as e:
        _fails_in_a_row += 1
        if _fails_in_a_row >= FAILS_BEFORE_PAUSE:
            _paused_until = time.monotonic() + PAUSE_SECONDS
        raise LLMError(str(e) or "LLM timed out") from e
    _fails_in_a_row = 0
    return data


async def _backup(main: asyncio.Task, client: httpx.AsyncClient, system: str, user: str, temperature: float) -> dict:
    """Live game: start the fallback if the main model fails or is slow. The first answer wins."""
    await asyncio.wait({main}, timeout=HEDGE_SECONDS)
    return await _attempt(client, config.LLM_FALLBACK_MODEL, system, user, temperature)


async def _attempt(client: httpx.AsyncClient, model: str, system: str, user: str, temperature: float) -> dict:
    try:
        resp = await _post(client, model, system, user, temperature)
    except httpx.HTTPError as e:
        raise LLMError(f"LLM {model} unreachable: {e.__class__.__name__}") from e
    if resp.status_code != 200:
        raise LLMError(f"LLM {model} failed ({resp.status_code})")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMBadOutput(f"LLM {model} sent an unexpected response") from e
    return _parse_json(content)


def _parse_json(text) -> dict:
    """Parse a JSON object, tolerating code fences, text around it, or a list holding it.

    Errors never quote the model's text, because it can echo what a player said.
    """
    if not isinstance(text, str):
        raise LLMBadOutput("LLM sent no text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise LLMBadOutput("LLM did not return JSON") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise LLMBadOutput("LLM did not return JSON") from None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict):
        raise LLMBadOutput("LLM did not return a JSON object")
    return data
