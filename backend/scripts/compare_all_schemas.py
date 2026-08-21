"""
Compare ALL ORM models against their live database tables, reporting any
column that exists on a model but not in the corresponding table.

Usage:
    python -m scripts.compare_all_schemas "postgresql+asyncpg://user:pass@host/db?ssl=require"
"""
import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.compare_all_schemas <DATABASE_URL>")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy.ext.asyncio import create_async_engine
from app.models.base import Base

# Import every model module so all tables register on Base.metadata
import importlib
import pkgutil
import app.models as models_pkg
import app.models.modules as modules_pkg

for _, name, _ in pkgutil.iter_modules(models_pkg.__path__, models_pkg.__name__ + "."):
    try:
        importlib.import_module(name)
    except Exception as e:
        print(f"  (skipped {name}: {e})")

for _, name, _ in pkgutil.iter_modules(modules_pkg.__path__, modules_pkg.__name__ + "."):
    try:
        importlib.import_module(name)
    except Exception as e:
        print(f"  (skipped {name}: {e})")


async def main():
    clean_url = sys.argv[1].split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})

    async with engine.connect() as conn:
        result = await conn.exec_driver_sql(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
        )
        db_schema = {}
        for table_name, column_name in result.fetchall():
            db_schema.setdefault(table_name, set()).add(column_name)

    total_gaps = 0
    for table in sorted(Base.metadata.tables.keys()):
        model_cols = {c.name for c in Base.metadata.tables[table].columns}
        db_cols = db_schema.get(table)
        if db_cols is None:
            print(f"[MISSING TABLE] {table}")
            total_gaps += 1
            continue
        missing = model_cols - db_cols
        if missing:
            print(f"[{table}] missing columns: {sorted(missing)}")
            total_gaps += len(missing)

    print()
    print(f"Total gaps found: {total_gaps}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
