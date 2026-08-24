"""Promote an already-registered user to role=admin.

There is no code path in the app itself that ever writes role: "admin" —
registration hardcodes settings.USER_ROLE_NAME (app/routers/auth.py), and
nothing else touches the field. This script is the reproducible way to do
what would otherwise be an undocumented, one-off edit in a Mongo shell.

It only ever changes an existing user's role. It never creates a user or
sets a password — the account must already be registered normally, so a
real bcrypt password_hash exists for it to log in with.

Usage:
    python scripts/make_admin.py someone@example.com
"""

from __future__ import annotations

import asyncio
import sys

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, ".")

from app.config import settings  # noqa: E402


async def make_admin(email: str) -> None:
    client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        db = client[settings.mongodb_db_name]
        user = await db.users.find_one({"email": email})
        if not user:
            print(
                f"No user found with email {email!r}. Register the account "
                "in the app first — this script only promotes an existing "
                "user, it never creates one."
            )
            raise SystemExit(1)

        if user.get("role") == settings.ADMIN_ROLE_NAME:
            print(f"{email} is already role={settings.ADMIN_ROLE_NAME!r} — nothing to do.")
            return

        result = await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"role": settings.ADMIN_ROLE_NAME}},
        )
        if result.modified_count != 1:
            print(f"Update did not apply as expected (matched={result.matched_count}).")
            raise SystemExit(1)

        # Re-read rather than trust the write — the whole point of printing
        # this is to verify the outcome, not assume it.
        confirmed = await db.users.find_one({"_id": user["_id"]}, {"role": 1, "email": 1})
        print(f"OK: {confirmed['email']} is now role={confirmed['role']!r}")
    finally:
        client.close()


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} someone@example.com")
        raise SystemExit(1)
    asyncio.run(make_admin(sys.argv[1]))


if __name__ == "__main__":
    main()
