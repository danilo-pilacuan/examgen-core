"""Best-effort audit of LLM calls (raw prompt/answer/thinking).

Every LLM invocation can be recorded in the `llm_responses` table:
  - `prompt`: the serialized messages sent to the model.
  - `raw_answer`: the model's full answer (`AIMessage.content`).
  - `raw_thinking`: the chain of thought, ONLY when
    `settings.llm_capture_thinking` is true and the server returns it
    (vLLM + reasoning models put it in `additional_kwargs`).

Design rules:
  - BEST-EFFORT: a logging failure must never break the chat or the
    pipeline (all exceptions are swallowed after a console warning).
  - Own session per record (independent transaction from the caller's).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from core.config import settings
from core.domain.models import LLMResponse
from core.infrastructure.db.connection import SessionLocal

# Keys where reasoning models may expose the chain of thought.
_THINKING_KEYS = ("reasoning_content", "reasoning", "thinking")

def _serialize_message(msg: Any) -> dict[str, Any]:
    """Serializes one LangChain message (or dict) to a JSON-friendly dict."""
    if isinstance(msg, dict):
        return {"type": msg.get("role", "dict"), "content": msg.get("content")}
    out: dict[str, Any] = {"type": msg.__class__.__name__}
    out["content"] = getattr(msg, "content", None)
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        out["tool_calls"] = [
            {"name": tc.get("name"), "args": tc.get("args")} for tc in tool_calls
        ]
    return out


def serialize_messages(messages: Iterable[Any]) -> str:
    """Serializes the prompt messages to a readable JSON string."""
    try:
        return json.dumps(
            [_serialize_message(m) for m in messages],
            ensure_ascii=False,
            default=str,
        )
    except Exception:  # noqa: BLE001
        return str(messages)


def extract_thinking(response: Any) -> str | None:
    """Extracts the chain of thought from an AIMessage, if the server sent it.

    vLLM + reasoning models (GLM/DeepSeek) expose it in
    `additional_kwargs["reasoning_content"]` (or `reasoning`/`thinking`
    depending on the server version).
    """
    kwargs = getattr(response, "additional_kwargs", None) or {}
    for key in _THINKING_KEYS:
        value = kwargs.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def record_llm_response(
    *,
    context: str,
    model: str,
    prompt_messages: Iterable[Any],
    raw_answer: str,
    raw_thinking: str | None = None,
    thread_id: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Records one LLM call in `llm_responses`. Never raises.

    Honors the capture switches:
      - `llm_capture_raw=False` → does nothing.
      - `llm_capture_thinking=False` → `raw_thinking` is dropped.
    """
    if not settings.llm_capture_raw:
        return
    try:
        thinking = raw_thinking if settings.llm_capture_thinking else None
        db = SessionLocal()
        try:
            db.add(LLMResponse(
                thread_id=thread_id,
                context=context,
                model=model,
                prompt=serialize_messages(prompt_messages),
                raw_answer=raw_answer or "",
                raw_thinking=thinking,
                latency_ms=latency_ms,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ llm_log: could not record LLM response ({e})")
