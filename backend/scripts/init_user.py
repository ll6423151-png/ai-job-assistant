import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal, init_db
from app.models.auth import User
from app.services.auth import hash_password


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a local CareerPilot AI user")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--email", default="admin@local.invalid")
    parser.add_argument("--password-env", default="INIT_USER_PASSWORD")
    parser.add_argument("--admin", action="store_true")
    parser.add_argument("--legacy-owner", action="store_true")
    parser.add_argument("--update-password", action="store_true")
    args = parser.parse_args()

    password = os.environ.get(args.password_env, "")
    if len(password) < 8 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise SystemExit(f"{args.password_env} must contain at least 8 characters, letters and numbers")

    await init_db()
    username = args.username.strip().lower()
    email = args.email.strip().lower()
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                is_active=True,
                is_admin=args.admin,
                email_verified=email.endswith("@qq.com") or email.endswith("@local.invalid"),
                is_legacy_owner=args.legacy_owner,
            )
            db.add(user)
            action = "created"
        else:
            user.email = email
            user.is_active = True
            user.is_admin = user.is_admin or args.admin
            user.is_legacy_owner = user.is_legacy_owner or args.legacy_owner
            if args.update_password:
                user.password_hash = hash_password(password)
            action = "updated"
        await db.commit()
        await db.refresh(user)
        print(f"user-{action}: id={user.id} username={user.username} email={user.email}")


if __name__ == "__main__":
    asyncio.run(main())
