"""
Check whether director@fairviewschoolng.com already exists (partial write check).

Usage:
    python scripts/check_partial_write.py "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python scripts/check_partial_write.py <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User


async def main():
    clean_url = sys.argv[1].split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        existing = (await db.execute(
            select(User).where(User.email == "director@fairviewschoolng.com")
        )).scalar_one_or_none()

        if existing:
            print("FOUND existing user record:")
            print(f"  ID: {existing.id}")
            print(f"  Email: {existing.email}")
            print(f"  Status: {getattr(existing, 'status', 'N/A')}")
            print(f"  Roles loaded: (checking separately, may lazy-load fail here too)")
        else:
            print("No user record found — no partial write occurred. Safe to retry cleanly.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
