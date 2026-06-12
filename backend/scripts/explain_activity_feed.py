"""
One-shot: confirms the composite index on audit_logs(org_id, created_at)
is actually used by the /activity-feed query. Runs an isolated in-memory
SQLite build of the schema, then prints EXPLAIN QUERY PLAN + PRAGMA
index_list so we can see the planner's choice.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Import app models so Base.metadata sees every table / index
from app.database import Base
from app.models import user, organization, role, audit, import_job  # noqa: F401
from app.models.modules import school, hospital, business  # noqa: F401


async def main() -> None:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        plan_sql = """
            EXPLAIN QUERY PLAN
            SELECT id, action, resource_type, resource_label,
                   actor_email, severity, created_at
            FROM audit_logs
            WHERE org_id = :org
            ORDER BY created_at DESC
            LIMIT 20 OFFSET 0
        """
        rows = (await conn.execute(text(plan_sql), {"org": "demo"})).fetchall()
        print("=== EXPLAIN QUERY PLAN: /activity-feed ===")
        for r in rows:
            print(" ", tuple(r))

        idx = (await conn.execute(text("PRAGMA index_list('audit_logs')"))).fetchall()
        print("\n=== Indexes on audit_logs ===")
        for r in idx:
            print(" ", tuple(r))

        info = (await conn.execute(text("PRAGMA index_info('ix_audit_logs_org_created')"))).fetchall()
        print("\n=== ix_audit_logs_org_created columns ===")
        for r in info:
            print(" ", tuple(r))


if __name__ == "__main__":
    asyncio.run(main())
