"""Zavu notification client wrapper.

This module keeps outbound messaging isolated from risk and CRUD logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ZavuSendResult:
    ok: bool
    provider: str
    message_id: str | None = None
    status: str | None = None
    error: str | None = None
    raw: Any = None


def _load_zavu_client_class():
    try:
        from zavu import Zavu  # type: ignore

        return Zavu
    except ImportError:
        pass

    try:
        from zavudev import Zavudev  # type: ignore

        return Zavudev
    except ImportError as exc:
        raise RuntimeError(
            "Zavu SDK is not installed. Install the package that provides "
            "`from zavu import Zavu` or install `zavudev`."
        ) from exc


def _extract_message_payload(response: Any) -> tuple[str | None, str | None]:
    message = None
    if isinstance(response, dict):
        message = response.get("message") or response
    else:
        message = getattr(response, "message", response)

    if isinstance(message, dict):
        return message.get("id"), message.get("status")

    return getattr(message, "id", None), getattr(message, "status", None)


def _build_send_kwargs(
    *,
    to: str,
    text: str,
    channel: str,
    idempotency_key: str | None,
    sender_id: str | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "to": to,
        "channel": channel,
        "text": text,
    }
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key
    if sender_id:
        kwargs["zavu_sender"] = sender_id
    return kwargs


class ZavuNotificationClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_channel: str | None = None,
        sender_id: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("ZAVUDEV_API_KEY", "")
        self.default_channel = default_channel or os.getenv("ZAVU_DEFAULT_CHANNEL", "whatsapp")
        self.sender_id = sender_id or os.getenv("ZAVU_SENDER_ID", "") or None
        if not self.api_key:
            raise RuntimeError("ZAVUDEV_API_KEY is not configured")

        client_class = _load_zavu_client_class()
        self.client = client_class(api_key=self.api_key)

    def send_whatsapp_text(
        self,
        *,
        to: str,
        text: str,
        idempotency_key: str | None = None,
    ) -> ZavuSendResult:
        try:
            response = self.client.messages.send(
                **_build_send_kwargs(
                    to=to,
                    text=text,
                    channel="whatsapp",
                    idempotency_key=idempotency_key,
                    sender_id=self.sender_id,
                )
            )
            message_id, status = _extract_message_payload(response)
            return ZavuSendResult(
                ok=True,
                provider="zavu",
                message_id=message_id,
                status=status,
                raw=response,
            )
        except Exception as exc:
            return ZavuSendResult(
                ok=False,
                provider="zavu",
                error=str(exc),
            )


def send_whatsapp_text(
    *,
    to: str,
    text: str,
    idempotency_key: str | None = None,
) -> ZavuSendResult:
    return ZavuNotificationClient().send_whatsapp_text(
        to=to,
        text=text,
        idempotency_key=idempotency_key,
    )
