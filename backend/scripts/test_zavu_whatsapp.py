from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
sys.path.insert(0, str(ROOT))

from services.zavu_notifications import ZavuNotificationClient  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Zavu WhatsApp access")
    parser.add_argument("--to", help="Destination phone in E.164 format, e.g. +503XXXXXXXX")
    parser.add_argument("--text", default="Prueba SATO-Agro: conexion con Zavu WhatsApp OK.")
    parser.add_argument("--send", action="store_true", help="Actually send the test message")
    parser.add_argument("--idempotency-key", help="Optional explicit Zavu idempotency key")
    return parser.parse_args()


def main() -> None:
    load_dotenv(ENV_PATH)
    args = parse_args()
    api_key = os.getenv("ZAVUDEV_API_KEY")
    if not api_key:
        raise RuntimeError("ZAVUDEV_API_KEY is not set in backend/.env or the environment")

    client = ZavuNotificationClient(api_key=api_key)
    print("zavu_configured=true")
    print(f"default_channel={client.default_channel}")

    if not args.send:
        print("send=false")
        print("Use --send --to +503XXXXXXXX to send a WhatsApp test message.")
        return

    if not args.to:
        raise RuntimeError("--to is required when using --send")

    result = client.send_whatsapp_text(
        to=args.to,
        text=args.text,
        idempotency_key=args.idempotency_key
        or f"sato-agro:zavu-test:{args.to}:{hashlib.sha256(args.text.encode('utf-8')).hexdigest()[:12]}",
    )
    print(f"sent={str(result.ok).lower()}")
    if result.message_id:
        print(f"message_id={result.message_id}")
    if result.status:
        print(f"status={result.status}")
    if result.error:
        print(f"error={result.error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
