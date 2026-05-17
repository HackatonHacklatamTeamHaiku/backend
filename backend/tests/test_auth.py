from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

bs4_stub = types.ModuleType("bs4")
bs4_stub.BeautifulSoup = object
sys.modules.setdefault("bs4", bs4_stub)

from app import create_app


class AuthTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True, AUTH_BYPASS_FOR_TESTING=False)
        self.app = app.test_client()

    def test_protected_endpoint_requires_bearer_token(self):
        response = self.app.get("/api/weather/observed?lat=13.69&lon=-89.21")
        self.assertEqual(response.status_code, 401)
        body = response.get_json()
        self.assertEqual(body["code"], "missing_authorization")

    @patch("services.auth.resolve_request_user")
    def test_auth_me_returns_authenticated_user(self, mocked_resolve):
        mocked_resolve.return_value = {
            "user_id": "123",
            "email": "test@example.com",
            "role": "authenticated",
            "claims": {"sub": "123", "email": "test@example.com", "role": "authenticated"},
            "profile": {"id": "123", "display_name": "Productor Prueba", "role": "producer"},
        }
        response = self.app.get("/api/auth/me", headers={"Authorization": "Bearer fake-token"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()["data"]
        self.assertEqual(body["email"], "test@example.com")
        self.assertEqual(body["profile"]["display_name"], "Productor Prueba")


if __name__ == "__main__":
    unittest.main()
