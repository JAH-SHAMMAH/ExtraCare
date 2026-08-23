import asyncio
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import CBTAttempt, Student

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"

async def main():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        # Find FSN-0031
        student = (await db.execute(
            select(Student).where(Student.student_id == "FSN-0031")
        )).scalar_one_or_none()

        if not student:
            print("[ERROR] FSN-0031 not found")
            await engine.dispose()
            return

        print(f"[OK] Student: {student.student_id}")

        # Delete their Biology exam attempt
        result = await db.execute(
            delete(CBTAttempt).where(
                CBTAttempt.student_id == student.id,
                CBTAttempt.exam_id == "25ef7e84-726c-4308-adbd-40de2e0875c1"
            )
        )

        await db.commit()
        print(f"[OK] Deleted {result.rowcount} attempt(s) for Biology exam")

    await engine.dispose()

asyncio.run(main())
