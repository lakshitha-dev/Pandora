"""Azure OpenAI access — chat completions and embeddings.

Every reasoning-model quirk is contained in this module so no caller has to
know about them. Verified against the live deployment on 2026-08-05:

    deployment gpt-5-mini
      · max_completion_tokens   — `max_tokens` is rejected
      · temperature must be 1   — 0.1 returns HTTP 400
      · reasoning tokens consume the completion budget (64 tokens were spent
        reasoning just to answer "OK"), so budgets must be generous
      · response_format={"type": "json_object"} works

    deployment text-embedding-3-small
      · 1536 dimensions

Switching to a non-reasoning model (e.g. gpt-4o-mini, if it is ever deployed)
is one env var: set IS_REASONING_MODEL=false and the request shape adapts.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Sequence

from openai import AzureOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 64


class LLMError(RuntimeError):
    """Raised when Azure OpenAI cannot serve a request."""


def _client() -> AzureOpenAI:
    s = get_settings()
    return AzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
        timeout=60.0,
        max_retries=2,
    )


# ─────────────────────────────────────────────────────────────────────────
# Chat completions
# ─────────────────────────────────────────────────────────────────────────


def chat(
    messages: Sequence[dict[str, str]],
    *,
    max_tokens: int | None = None,
    json_mode: bool = False,
    temperature: float | None = None,
) -> str:
    """Run a chat completion and return the message text.

    Args:
        messages: OpenAI-format message dicts.
        max_tokens: Output budget. On a reasoning model this covers reasoning
            tokens too, so it is set generously by default.
        json_mode: Constrain the response to a single JSON object.
        temperature: Ignored on reasoning models, which only accept the
            default. Passing a value there would return HTTP 400.

    Raises:
        LLMError: on an API failure or an empty completion.
    """
    s = get_settings()
    budget = max_tokens or s.chat_max_completion_tokens

    kwargs: dict[str, Any] = {
        "model": s.azure_openai_chat_deployment,
        "messages": list(messages),
    }

    if s.is_reasoning_model:
        # Reasoning models: max_completion_tokens, and no temperature at all.
        kwargs["max_completion_tokens"] = budget
    else:
        kwargs["max_tokens"] = budget
        if temperature is not None:
            kwargs["temperature"] = temperature

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = _client().chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface any client failure uniformly
        raise LLMError(f"chat completion failed: {exc}") from exc

    choice = resp.choices[0]
    content = (choice.message.content or "").strip()

    usage = getattr(resp, "usage", None)
    if usage is not None:
        details = getattr(usage, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None) if details else None
        logger.debug(
            "chat usage prompt=%s completion=%s reasoning=%s finish=%s",
            usage.prompt_tokens,
            usage.completion_tokens,
            reasoning,
            choice.finish_reason,
        )

    if not content:
        # On a reasoning model this almost always means the budget was spent
        # entirely on reasoning tokens before any output was produced.
        raise LLMError(
            "empty completion "
            f"(finish_reason={choice.finish_reason!r}) — the token budget of "
            f"{budget} was likely consumed by reasoning. Raise "
            "CHAT_MAX_COMPLETION_TOKENS."
        )

    return content


def chat_json(
    messages: Sequence[dict[str, str]],
    *,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Chat completion constrained to JSON, parsed into a dict.

    Raises:
        LLMError: if the response is not a JSON object.
    """
    raw = chat(messages, max_tokens=max_tokens, json_mode=True)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"expected JSON, got: {raw[:200]!r}") from exc
    if not isinstance(parsed, dict):
        raise LLMError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


# ─────────────────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _embed_batch(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    resp = _client().embeddings.create(
        model=s.azure_openai_embedding_deployment,
        input=texts,
    )
    # The API may return items out of order; sort by index to be safe.
    return [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    """Embed many texts, batched with retry/backoff on rate limits."""
    items = list(texts)
    if not items:
        return []

    vectors: list[list[float]] = []
    for start in range(0, len(items), _EMBED_BATCH_SIZE):
        batch = items[start : start + _EMBED_BATCH_SIZE]
        try:
            vectors.extend(_embed_batch(batch))
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"embedding failed for batch at offset {start}: {exc}"
            ) from exc
        logger.info("embedded %d/%d chunks", min(start + len(batch), len(items)), len(items))

    expected = get_settings().embedding_dimensions
    if vectors and len(vectors[0]) != expected:
        raise LLMError(
            f"embedding dimension mismatch: got {len(vectors[0])}, index expects "
            f"{expected}. The index and the embedding model must agree."
        )
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]


# ─────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────


def llm_reachable() -> bool:
    """Cheap liveness probe used by GET /health."""
    try:
        embed_query("ping")
        return True
    except Exception:  # noqa: BLE001
        logger.warning("LLM health probe failed", exc_info=True)
        return False
