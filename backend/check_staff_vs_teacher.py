import os
import asyncio
import asyncpg
import json

async def main():
    conn = await asyncpg.connect(
        os.environ["PROD_DATABASE_URL"],
        ssl="require"
    )
    staff = await conn.fetchrow("SELECT permissions FROM roles WHERE slug = 'staff'")
    teacher = await conn.fetchrow("SELECT permissions FROM roles WHERE slug = 'teacher'")

    staff_perms = set(json.loads(staff["permissions"]))
    teacher_perms = set(json.loads(teacher["permissions"]))

    print("STAFF permissions:", len(staff_perms))
    for p in sorted(staff_perms):
        print("  -", p)
    print()
    print("TEACHER permissions:", len(teacher_perms))
    for p in sorted(teacher_perms):
        print("  -", p)
    print()
    print("Only in STAFF:", sorted(staff_perms - teacher_perms))
    print("Only in TEACHER:", sorted(teacher_perms - staff_perms))

    await conn.close()

asyncio.run(main())
