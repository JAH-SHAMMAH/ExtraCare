"""
Compare the Organization ORM model against the live organizations table.

Usage:
    python scripts/compare_org_schema.py "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python scripts/compare_org_schema.py <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.organization import Organization


async def main():
    engine = create_async_engine(sys.argv[1])
    async with engine.connect() as conn:
        result = await conn.exec_driver_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'organizations'"
        )
        db_cols = {row[0] for row in result.fetchall()}

    model_cols = {c.name for c in Organization.__table__.columns}
    missing_in_db = model_cols - db_cols
    extra_in_db = db_cols - model_cols

    print("Columns in model but MISSING from DB table:")
    for c in sorted(missing_in_db):
        print(" -", c)
    print()
    print("Columns in DB table but not in model (informational):")
    for c in sorted(extra_in_db):
        print(" -", c)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
