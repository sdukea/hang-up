"""Minimal client for any OpenAI-compatible chat completions API.

Works with hosted providers and self-hosted servers (vLLM, Ollama, etc.),
including Gnani's open-weights Evon served behind an OpenAI-compatible
endpoint. Configure LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env.
"""

import asyncio
import json
import logging
import re

import httpx

from . import config

log = logging.getLogger("dadi.llm")


class LLMError(RuntimeError):
    pass


# Busy or rate-limited: worth retrying, then trying the fallback model.
RETRYABLE = {429, 500, 502, 503, 504}


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

    # Live game: try the main model, then the fallback, without waiting around.
    attempts = [(config.LLM_MODEL, 0), (config.LLM_FALLBACK_MODEL or config.LLM_MODEL, 0.5)]

    resp = None
    async with httpx.AsyncClient(timeout=7) as client:
        for model, pause in attempts:
            await asyncio.sleep(pause)
            try:
                resp = await _post(client, model, system, user, temperature)
            except httpx.HTTPError as e:
                log.warning("LLM %s unreachable: %s", model, e.__class__.__name__)
                continue
            if resp.status_code == 200:
                break
            if resp.status_code not in RETRYABLE:
                raise LLMError(f"LLM request failed ({resp.status_code}): {resp.text[:300]}")
            log.warning("LLM %s busy (%s), retrying", model, resp.status_code)

    if resp is None:
        raise LLMError("Could not reach the LLM.")
    if resp.status_code != 200:
        raise LLMError(f"LLM is busy right now ({resp.status_code}). Please try again in a minute.")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"Unexpected LLM response: {resp.text[:300]}") from e
    return _parse_json(content)


def _parse_json(text: str) -> dict:
    """Parse a JSON object, tolerating code fences or text around it."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError(f"LLM did not return JSON: {text[:300]}")
