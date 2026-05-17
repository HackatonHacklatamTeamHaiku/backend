from __future__ import annotations

import os
import re
from typing import Any

import langsmith as ls
from langsmith import Client, traceable


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TOKEN_RE = re.compile(r"(sk-or-[A-Za-z0-9_\-]+|lsv2_[A-Za-z0-9_\-]+)")

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "lat",
    "latitude",
    "lon",
    "lng",
    "longitude",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def is_langsmith_enabled() -> bool:
    value = os.getenv("LANGSMITH_TRACING") or os.getenv("LANGCHAIN_TRACING_V2") or ""
    return value.strip().lower() in {"1", "true", "yes", "on"}


def should_redact_traces() -> bool:
    value = os.getenv("LANGSMITH_REDACT_TRACES", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def redact_payload(value: Any, depth: int = 8) -> Any:
    if depth <= 0:
        return "[REDACTED_MAX_DEPTH]"

    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_payload(item, depth - 1)
        return redacted

    if isinstance(value, list):
        return [redact_payload(item, depth - 1) for item in value]

    if isinstance(value, str):
        value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
        return TOKEN_RE.sub("[REDACTED_TOKEN]", value)

    return value


def serialize_response(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return dict_method()

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    return repr(value)


def extract_usage_metadata(response: Any) -> dict:
    payload = serialize_response(response)
    if not isinstance(payload, dict):
        return {}

    usage = payload.get("usage") or {}
    if not isinstance(usage, dict):
        return {}

    result = {}
    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")

    if isinstance(input_tokens, int):
        result["input_tokens"] = input_tokens
    if isinstance(output_tokens, int):
        result["output_tokens"] = output_tokens
    if isinstance(total_tokens, int):
        result["total_tokens"] = total_tokens

    return result


def _make_client() -> Client | None:
    if not is_langsmith_enabled():
        return None

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        return None

    kwargs = {}
    if should_redact_traces():
        kwargs["hide_inputs"] = redact_payload
        kwargs["hide_outputs"] = redact_payload
    endpoint = os.getenv("LANGSMITH_ENDPOINT", "").strip().rstrip(".")
    if endpoint:
        kwargs["api_url"] = endpoint
    return Client(**kwargs)


langsmith_client = _make_client()


__all__ = [
    "extract_usage_metadata",
    "is_langsmith_enabled",
    "langsmith_client",
    "ls",
    "redact_payload",
    "should_redact_traces",
    "serialize_response",
    "traceable",
]
