"""
Check which tables/columns currently use a given Postgres enum type,
and list all enum types already present in the database.

Usage:
    python -m scripts.check_enum_collision "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.check_enum_collision <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    clean_url = sys.argv[1].split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})

    async with engine.connect() as conn:
        # All enum types currently in the database
        result = await conn.exec_driver_sql("""
            SELECT t.typname, array_agg(e.enumlabel ORDER BY e.enumsortorder) as labels
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            GROUP BY t.typname
            ORDER BY t.typname
        """)
        print("=" * 70)
        print("All enum types currently in the database:")
        print("=" * 70)
        for typname, labels in result.fetchall():
            print(f"  {typname}: {labels}")

        print()
        print("=" * 70)
        print("Columns currently using type 'leavetype':")
        print("=" * 70)
        result = await conn.exec_driver_sql("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE udt_name = 'leavetype'
        """)
        rows = result.fetchall()
        if rows:
            for table_name, column_name in rows:
                print(f"  {table_name}.{column_name}")
        else:
            print("  (none — the type exists but nothing references it)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
