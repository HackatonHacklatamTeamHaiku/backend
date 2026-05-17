from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.database import close_pool, get_dict_cursor, init_pool


DEFAULT_EMAIL = "test@example.com"
DEFAULT_PASSWORD = "TestPassword123!"
DEFAULT_FULL_NAME = "Productor de Prueba"
DEFAULT_DISPLAY_NAME = "Productor Prueba"


def main() -> int:
    env_path = ROOT / ".env"
    load_dotenv(env_path)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is missing in backend/.env")
        return 1

    email = os.getenv("TEST_USER_EMAIL", DEFAULT_EMAIL).strip().lower()
    password = os.getenv("TEST_USER_PASSWORD", DEFAULT_PASSWORD)
    full_name = os.getenv("TEST_USER_FULL_NAME", DEFAULT_FULL_NAME).strip()
    display_name = os.getenv("TEST_USER_DISPLAY_NAME", DEFAULT_DISPLAY_NAME).strip()

    init_pool(database_url)
    try:
        user_id = seed_test_user(
            email=email,
            password=password,
            full_name=full_name,
            display_name=display_name,
        )
    finally:
        close_pool()

    print("Test user ready")
    print(f"user_id={user_id}")
    print(f"email={email}")
    print(f"password={password}")
    return 0


def seed_test_user(*, email: str, password: str, full_name: str, display_name: str) -> str:
    with get_dict_cursor() as cur:
        cur.execute("SELECT id FROM auth.users WHERE email = %s AND deleted_at IS NULL", (email,))
        row = cur.fetchone()
        user_id = str(row["id"]) if row else str(uuid.uuid4())

        cur.execute("SELECT crypt(%s, gen_salt('bf')) AS password_hash", (password,))
        password_hash = cur.fetchone()["password_hash"]

        app_meta = {"provider": "email", "providers": ["email"]}
        user_meta = {"full_name": full_name, "display_name": display_name}
        identity_data = {
            "sub": user_id,
            "email": email,
            "email_verified": True,
            "phone_verified": False,
        }

        cur.execute(
            """
            INSERT INTO auth.users (
                instance_id,
                id,
                aud,
                role,
                email,
                encrypted_password,
                email_confirmed_at,
                last_sign_in_at,
                raw_app_meta_data,
                raw_user_meta_data,
                created_at,
                updated_at,
                is_sso_user,
                is_anonymous
            )
            VALUES (
                '00000000-0000-0000-0000-000000000000',
                %s,
                'authenticated',
                'authenticated',
                %s,
                %s,
                now(),
                now(),
                %s,
                %s,
                now(),
                now(),
                false,
                false
            )
            ON CONFLICT (id) DO UPDATE
            SET
                instance_id = EXCLUDED.instance_id,
                email = EXCLUDED.email,
                encrypted_password = EXCLUDED.encrypted_password,
                email_confirmed_at = EXCLUDED.email_confirmed_at,
                last_sign_in_at = EXCLUDED.last_sign_in_at,
                raw_app_meta_data = EXCLUDED.raw_app_meta_data,
                raw_user_meta_data = EXCLUDED.raw_user_meta_data,
                updated_at = now()
            """,
            (
                user_id,
                email,
                password_hash,
                Json(app_meta),
                Json(user_meta),
            ),
        )

        cur.execute(
            """
            INSERT INTO auth.identities (
                provider_id,
                user_id,
                identity_data,
                provider,
                last_sign_in_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'email', now(), now(), now())
            ON CONFLICT (provider_id, provider) DO UPDATE
            SET
                user_id = EXCLUDED.user_id,
                identity_data = EXCLUDED.identity_data,
                last_sign_in_at = EXCLUDED.last_sign_in_at,
                updated_at = now()
            """,
            (
                email,
                user_id,
                Json(identity_data),
            ),
        )

        cur.execute(
            """
            INSERT INTO public.profiles (
                id,
                full_name,
                display_name,
                role,
                preferred_language,
                country,
                onboarding_completed,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'producer', 'es', 'El Salvador', false, now(), now())
            ON CONFLICT (id) DO UPDATE
            SET
                full_name = EXCLUDED.full_name,
                display_name = EXCLUDED.display_name,
                updated_at = now()
            """,
            (user_id, full_name, display_name),
        )

        cur.execute(
            """
            INSERT INTO public.user_preferences (profile_id)
            VALUES (%s)
            ON CONFLICT (profile_id) DO NOTHING
            """,
            (user_id,),
        )
        return user_id


if __name__ == "__main__":
    raise SystemExit(main())
