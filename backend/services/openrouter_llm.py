from __future__ import annotations

import json
import os
from pathlib import Path

from services.manifest_context import build_runtime_llm_context
from services.semantic_tools import execute_semantic_tool, openrouter_tool_definitions
from utils.time import now_utc_iso


def generate_chat_reply(arguments: dict) -> tuple[dict, dict, int]:
    user_message = arguments.get("message")
    if not isinstance(user_message, str) or not user_message.strip():
        return _error("message must be a non-empty string")
    selected_model = arguments.get("model")
    if selected_model is not None and (not isinstance(selected_model, str) or not selected_model.strip()):
        return _error("model must be a non-empty string")
    selected_model = selected_model.strip() if isinstance(selected_model, str) else None

    conversation = arguments.get("conversation")
    if conversation is not None and not isinstance(conversation, list):
        return _error("conversation must be a list")

    runtime_args = {
        "crop": arguments.get("crop"),
        "sowing_date": arguments.get("sowing_date"),
        "lat": arguments.get("lat"),
        "lon": arguments.get("lon"),
        "target_date": arguments.get("target_date"),
    }
    runtime_context, runtime_meta, runtime_status = build_runtime_llm_context(runtime_args)
    if runtime_status >= 400:
        return runtime_context, runtime_meta, runtime_status

    client = _build_openrouter_client()
    if client is None:
        return _error("OpenRouter client is not configured on the backend", status=503)
    routing_models = _routing_models(selected_model)
    if not routing_models:
        return _error("Either payload.model or OPENROUTER_MODEL / OPENROUTER_FALLBACK_MODELS must be configured on the backend", status=503)

    system_prompt = _load_system_prompt()
    tool_defs = openrouter_tool_definitions()
    messages = _build_messages(system_prompt, runtime_context, conversation or [], user_message.strip())

    tool_rounds: list[dict] = []
    max_rounds = int(os.getenv("OPENROUTER_MAX_TOOL_ROUNDS", "4"))

    for _ in range(max_rounds):
        response = client.chat.send(
            models=routing_models,
            messages=messages,
            tools=tool_defs,
            tool_choice="auto",
            parallel_tool_calls=False,
            temperature=0.2,
        )

        choice = _first_choice(response)
        assistant_message = _message_dict(choice.get("message"))
        tool_calls = assistant_message.get("tool_calls") or []

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.get("content"),
                    "tool_calls": tool_calls,
                }
            )
            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                tool_name = function.get("name")
                raw_arguments = function.get("arguments") or "{}"
                try:
                    parsed_arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                except json.JSONDecodeError:
                    parsed_arguments = {}

                tool_result, tool_meta, tool_status = execute_semantic_tool(tool_name, parsed_arguments)
                tool_rounds.append(
                    {
                        "tool_name": tool_name,
                        "arguments": parsed_arguments,
                        "status": tool_status,
                        "meta": tool_meta,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "name": tool_name,
                        "content": json.dumps(
                            {
                                "result": tool_result,
                                "meta": tool_meta,
                                "status": tool_status,
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
            continue

        reply_text = _assistant_text(assistant_message)
        return (
            {
                "reply": reply_text,
                "runtime_context": runtime_context,
                "tool_calls": tool_rounds,
                "model": choice.get("model") or getattr(response, "model", None) or routing_models[0],
                "requested_model": selected_model or None,
                "routing_models": routing_models,
                "finish_reason": choice.get("finish_reason"),
                "openrouter_metadata": getattr(response, "openrouter_metadata", None),
            },
            _meta("ok"),
            200,
        )

    return _error("OpenRouter tool loop exceeded max rounds", status=502)


def _build_openrouter_client():
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openrouter import OpenRouter
    except ImportError:
        return None
    return OpenRouter(
        api_key=api_key,
        http_referer=os.getenv("OPENROUTER_HTTP_REFERER"),
        x_open_router_title=os.getenv("OPENROUTER_TITLE", "SATO-Agro Backend"),
        x_open_router_categories=os.getenv("OPENROUTER_CATEGORIES", "backend,agriculture"),
    )


def _fallback_models() -> list[str] | None:
    raw = os.getenv("OPENROUTER_FALLBACK_MODELS", "").strip()
    if not raw:
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def _routing_models(selected_model: str | None) -> list[str]:
    primary = selected_model or os.getenv("OPENROUTER_MODEL", "").strip()
    fallbacks = _fallback_models() or []
    if not primary and fallbacks:
        primary = fallbacks[0]
        fallbacks = fallbacks[1:]
    ordered = []
    for model_name in [primary, *fallbacks]:
        if model_name and model_name not in ordered:
            ordered.append(model_name)
    return ordered


def _load_system_prompt() -> str:
    configured = os.getenv("LLM_SYSTEM_PROMPT_PATH", "").strip()
    candidate_paths = []
    if configured:
        candidate_paths.append(Path(configured))
    candidate_paths.append(Path(__file__).resolve().parents[1] / "prompts" / "sato_agro_system_prompt.md")
    candidate_paths.append(
        Path(__file__).resolve().parents[3] / "infra---data-I-plus-D" / "model" / "SYSTEM_PROMPT.md"
    )
    for path in candidate_paths:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return "Eres el asistente agroclimatico de SATO-Agro. Responde en espanol claro, breve y prudente."


def _build_messages(system_prompt: str, runtime_context: dict, conversation: list, user_message: str) -> list[dict]:
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": "Este es el runtime_context actual del usuario. Usalo como fuente principal.\n"
            + json.dumps(runtime_context, ensure_ascii=False),
        },
    ]
    for item in conversation:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    messages.append({"role": "user", "content": user_message})
    return messages


def _first_choice(response) -> dict:
    response_dict = _obj_to_dict(response)
    choices = response_dict.get("choices") or []
    if not choices:
        return {}
    choice = choices[0]
    return choice if isinstance(choice, dict) else _obj_to_dict(choice)


def _message_dict(message) -> dict:
    if not message:
        return {}
    return message if isinstance(message, dict) else _obj_to_dict(message)


def _assistant_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        bits = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    bits.append(str(text))
        return "\n".join(bits).strip()
    return ""


def _obj_to_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _meta(upstream_status: str) -> dict:
    return {
        "cached": False,
        "stale": False,
        "upstream_status": upstream_status,
        "fetched_at": now_utc_iso(),
    }


def _error(message: str, status: int = 400) -> tuple[dict, dict, int]:
    return {"error": message}, _meta("invalid_request" if status == 400 else "failed"), status
