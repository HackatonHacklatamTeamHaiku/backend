from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from mcp_server import server


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeClient:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return self.response

    def post(self, *args, **kwargs):
        return self.response


class McpServerTests(unittest.TestCase):
    def test_backend_get_returns_structured_error_for_backend_400(self):
        response = FakeResponse(
            status_code=400,
            payload={"data": {"error": "bad request"}, "meta": {"upstream_status": "invalid_request"}},
        )
        with patch.object(server.httpx, "Client", return_value=FakeClient(response)):
            result = server._backend_get("/api/weather/observed", {"lat": "bad"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(result["backend_response"]["meta"]["upstream_status"], "invalid_request")

    def test_backend_tool_call_returns_structured_error_for_malformed_json(self):
        response = FakeResponse(status_code=200, payload=ValueError("not json"), text="not-json")
        with patch.object(server.httpx, "Client", return_value=FakeClient(response)):
            result = server._backend_tool_call("getOfficialContext", {})

        self.assertFalse(result["ok"])
        self.assertIn("non-JSON", result["error"])
        self.assertEqual(result["raw_body_snippet"], "not-json")

    def test_tool_payload_standardizes_dispatcher_success(self):
        payload = server._tool_payload(
            {
                "tool_name": "getPhenologyContext",
                "arguments": {"crop": "maiz"},
                "result": {"phase_code": "VE"},
                "meta": {"upstream_status": "ok"},
            },
            backend_tool_name="getPhenologyContext",
            arguments={"crop": "maiz"},
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["backend_tool_name"], "getPhenologyContext")
        self.assertEqual(payload["result"]["phase_code"], "VE")
        self.assertEqual(payload["meta"]["upstream_status"], "ok")

    def test_tool_payload_lifts_backend_error_meta(self):
        payload = server._tool_payload(
            {
                "ok": False,
                "backend_response": {
                    "error": "bad",
                    "meta": {"upstream_status": "invalid_request"},
                },
                "error": "Backend returned an error response.",
            },
            backend_tool_name="getOfficialContext",
            arguments={"target_date": "bad"},
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["meta"]["upstream_status"], "invalid_request")

    def test_runtime_context_mcp_tool_uses_backend_dispatcher(self):
        with patch.object(
            server,
            "_backend_tool_call",
            return_value={
                "tool_name": "buildRuntimeContext",
                "arguments": {},
                "result": {"risk_assessment": {"risk_level": "NORMAL"}},
                "meta": {"upstream_status": "ok"},
            },
        ) as mocked:
            result = json.loads(server.get_runtime_context("maiz", "2026-05-01", 13.69, -89.21))

        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.args[0], "buildRuntimeContext")
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend_tool_name"], "buildRuntimeContext")


if __name__ == "__main__":
    unittest.main()
