from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.config import get_settings

settings = get_settings()

# Naming convention for consistent migration generation
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


# Pool tuning is only meaningful for real databases; SQLite runs single-writer
# with a NullPool-equivalent under the hood, so we skip the kwargs there.
_is_sqlite = "sqlite" in settings.DATABASE_URL
_engine_kwargs = {"echo": settings.DATABASE_ECHO}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        pool_pre_ping=True,  # drops stale connections after idle-kill on cloud DBs.
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create tables + sync system-role permission presets.

    In production, AUTO_CREATE_SCHEMA is False and schema is managed by
    Alembic — this function then only syncs the role presets. Dev/test
    environments can keep it on for zero-config bootstrapping.
    """
    # Import all models so Base knows about them
    from app.models import user, organization, role, audit, import_job, hrm, leave, messenger, feed, live  # noqa
    from app.models.modules import school, hospital, business  # noqa

    if settings.AUTO_CREATE_SCHEMA:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Keep system-role permission presets in sync with code. Presets are
    # workspace-aware, so legacy system roles lose cross-industry grants on
    # the next boot without a destructive migration.
    from sqlalchemy import select
    from app.models.organization import Organization
    from app.models.role import Role, permission_presets_for_industry

    async with AsyncSessionLocal() as session:
        orgs = (await session.execute(
            select(Organization).where(Organization.is_deleted == False)
        )).scalars().all()
        changed = False
        for org in orgs:
            industry = org.industry.value if org.industry else None
            presets = permission_presets_for_industry(industry)
            roles = (await session.execute(
                select(Role).where(Role.org_id == org.id, Role.is_system == True)
            )).scalars().all()
            by_slug = {role.slug: role for role in roles}

            for slug, preset in presets.items():
                if slug == "super_admin":
                    continue
                role = by_slug.get(slug)
                if role is None:
                    session.add(Role(
                        name=slug.replace("_", " ").title(),
                        slug=slug,
                        permissions=list(preset),
                        org_id=org.id,
                        is_system=True,
                    ))
                    changed = True
                    continue
                if list(role.permissions or []) != list(preset):
                    role.permissions = list(preset)
                    changed = True
        if changed:
            await session.commit()
