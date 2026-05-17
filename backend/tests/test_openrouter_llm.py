from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.openrouter_llm import _build_messages, generate_chat_reply


class _DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def model_dump(self):
        return self._payload


class _DummyChat:
    def __init__(self, responses: list[dict]):
        self._responses = responses
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        return _DummyResponse(self._responses.pop(0))


class _DummyClient:
    def __init__(self, responses: list[dict]):
        self.chat = _DummyChat(responses)


class OpenRouterLLMTests(unittest.TestCase):
    def test_runtime_context_prompt_formats_calendar_as_markdown_csv(self):
        runtime_context = {
            "current_date": "2026-05-17",
            "crop_calendar": {
                "crop": "maiz",
                "format": "csv",
                "csv": "Día,Días desde Siembra,Días desde presente,Evento\nV 01/05/26,0,-16,Siembra\nD 17/05/26,16,0,Presente",
            },
        }

        messages = _build_messages("system prompt", runtime_context, [], "hola")
        content = messages[1]["content"]

        self.assertIn("## Datos estructurados", content)
        self.assertIn("## crop_calendar.csv", content)
        self.assertIn("```csv\nDía,Días desde Siembra,Días desde presente,Evento", content)
        self.assertIn("D 17/05/26,16,0,Presente", content)
        self.assertNotIn('"csv":', content)
        self.assertNotIn("\\nD 17/05/26", content)

    def test_generate_chat_reply_runs_tool_loop_and_returns_final_text(self):
        runtime_context = {
            "current_datetime": "2026-05-16T10:30:00-06:00",
            "timezone": "America/El_Salvador",
            "user_inputs": {"crop": "maiz", "sowing_date": "2026-05-10", "lat": 13.8, "lon": -89.18},
            "ui_state": {"selected_target_date": "2026-05-16", "selected_horizon": "present", "visible_panel": "risk_summary"},
            "missing_required_user_data": [],
            "plant_state": {"phase": "VE"},
            "risk_assessment": {"risk_level": "alto"},
            "sources_used": [],
            "source_policy": {"observed": "SNET/MARN observado local"},
        }
        tool_result = {
            "risk_level": "alto",
            "confidence": "media-alta",
            "plant_state": {"phase": "VE"},
            "risk_factors": [{"label": "Calor fuerte", "state": "alto"}],
            "official_context": {"canicula_2026_watch": True},
            "recommendations": ["No fertilizar en seco."],
        }
        client = _DummyClient(
            [
                {
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "getRiskAssessment",
                                            "arguments": "{\"crop\":\"maiz\",\"sowing_date\":\"2026-05-10\",\"lat\":13.8,\"lon\":-89.1833,\"target_date\":\"2026-05-16\"}",
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "Tu maiz va con riesgo preventivo alto. Hoy revisa la humedad del suelo y no fertilices en seco.",
                            },
                        }
                    ]
                },
            ]
        )

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
                "OPENROUTER_FALLBACK_MODELS": "openai/gpt-5.4-nano",
            },
            clear=False,
        ):
            with patch("services.openrouter_llm.build_runtime_llm_context", return_value=(runtime_context, {"cached": True}, 200)):
                with patch("services.openrouter_llm._build_openrouter_client", return_value=client):
                    with patch("services.openrouter_llm.execute_semantic_tool", return_value=(tool_result, {"cached": True}, 200)):
                        data, meta, status = generate_chat_reply(
                            {
                                "message": "como va mi milpa",
                                "model": "openai/gpt-5.4-pro",
                                "crop": "maiz",
                                "sowing_date": "2026-05-10",
                                "lat": 13.8,
                                "lon": -89.1833,
                                "target_date": "2026-05-16",
                            }
                        )

        self.assertEqual(status, 200)
        self.assertEqual(meta["upstream_status"], "ok")
        self.assertIn("riesgo preventivo alto", data["reply"])
        self.assertEqual(len(data["tool_calls"]), 1)
        self.assertEqual(data["tool_calls"][0]["tool_name"], "getRiskAssessment")
        self.assertEqual(data["requested_model"], "openai/gpt-5.4-pro")
        self.assertEqual(data["routing_models"], ["openai/gpt-5.4-pro", "openai/gpt-5.4-nano"])
        self.assertEqual(
            client.chat.calls[0]["models"],
            ["openai/gpt-5.4-pro", "openai/gpt-5.4-nano"],
        )

    def test_generate_chat_reply_requires_message(self):
        data, meta, status = generate_chat_reply({"crop": "maiz"})
        self.assertEqual(status, 400)
        self.assertEqual(meta["upstream_status"], "invalid_request")
        self.assertIn("message", data["error"])


if __name__ == "__main__":
    unittest.main()
