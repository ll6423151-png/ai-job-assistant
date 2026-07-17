import asyncio
import tempfile
from pathlib import Path
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db, tenant_context
from app.main import app
from app.services.auth import get_current_user


@pytest.fixture()
def client():
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    AsyncTestingSession = async_sessionmaker(bind=async_engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    async def override_get_db():
        async with AsyncTestingSession() as db:
            yield db

    async def override_current_user():
        token = tenant_context.set(1)
        try:
            yield SimpleNamespace(id=1, username="test-user", email="test@qq.com")
        finally:
            tenant_context.reset(token)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    asyncio.run(async_engine.dispose())
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    try:
        db_path.unlink(missing_ok=True)
    except PermissionError:
        pass
