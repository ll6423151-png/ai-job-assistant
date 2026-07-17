from collections.abc import AsyncGenerator
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, with_loader_criteria

from app.core.config import settings


class Base(DeclarativeBase):
    pass


tenant_context: ContextVar[int | None] = ContextVar("tenant_context", default=None)

engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "do_orm_execute")
def scope_tenant_queries(execute_state) -> None:
    tenant_id = tenant_context.get()
    if tenant_id is None or not execute_state.is_select:
        return
    from app.models.tenant import TenantOwned

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantOwned,
            lambda model: model.user_id == tenant_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def assign_tenant_to_new_records(session: Session, _flush_context, _instances) -> None:
    tenant_id = tenant_context.get()
    if tenant_id is None:
        return
    from app.models.tenant import TenantOwned

    for instance in session.new:
        if isinstance(instance, TenantOwned):
            instance.user_id = tenant_id


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        yield db


async def init_db() -> None:
    """Create the optional bootstrap user after Alembic has created the schema."""
    if not settings.bootstrap_admin_enabled:
        return

    from sqlalchemy import select

    from app.models.auth import User
    from app.services.auth import hash_password

    async with SessionLocal() as db:
        username = settings.bootstrap_admin_username.strip().lower() or "admin"
        admin = await db.scalar(select(User).where(User.username == username))
        if admin is None:
            admin = User(
                username=username,
                email="admin@local.invalid",
                password_hash=hash_password(settings.bootstrap_admin_password),
                is_active=True,
                is_admin=True,
                email_verified=True,
                is_legacy_owner=True,
            )
            db.add(admin)
            await db.commit()
