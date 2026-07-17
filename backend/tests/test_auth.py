from datetime import timedelta

from fastapi.testclient import TestClient
import asyncio
import tempfile
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db, tenant_context
from app.main import app
from app.models.auth import EmailVerificationCode, User
from app.models.application_automation import AutomatedApplicationTask
from app.models.application_record import ApplicationRecord
from app.models.blacklist_company import BlacklistCompany
from app.models.greeting_message import GreetingMessage
from app.models.interview import InterviewSession, ResumeAsset
from app.models.job import Job
from app.models.job_search_exclusion import JobSearchExclusion
from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume
from app.models.resume_optimization import ResumeOptimization
from app.models.user_profile import UserProfile
from app.services.auth import code_digest, hash_password, utcnow


_async_engines = {}
_db_paths = {}


def build_client():
    db_path = Path(tempfile.mkstemp(suffix=".db")[1])
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    AsyncTestingSession = async_sessionmaker(bind=async_engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    async def override_get_db():
        async with AsyncTestingSession() as db:
            yield db

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    _async_engines[id(engine)] = async_engine
    _db_paths[id(engine)] = db_path
    return TestClient(app), TestingSession, engine


def close_client(client, engine):
    client.close()
    asyncio.run(_async_engines.pop(id(engine)).dispose())
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    try:
        _db_paths.pop(id(engine)).unlink(missing_ok=True)
    except PermissionError:
        pass


def test_password_login_logout_and_protected_route():
    client, SessionLocal, engine = build_client()
    try:
        with SessionLocal() as db:
            db.add(User(username="admin", email="admin@local.invalid", password_hash=hash_password("admin123"), is_admin=True, email_verified=True))
            db.commit()

        assert client.get("/api/resumes").status_code == 401
        login = client.post("/api/auth/login", json={"identifier": "admin", "password": "admin123", "remember_me": True})
        assert login.status_code == 200
        assert login.json()["user"]["username"] == "admin"
        assert client.get("/api/auth/me").status_code == 200
        assert client.get("/api/resumes").status_code == 200
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/resumes").status_code == 401
    finally:
        close_client(client, engine)


def test_register_with_qq_email_code_and_tenant_isolation():
    client, SessionLocal, engine = build_client()
    try:
        email = "12345678@qq.com"
        with SessionLocal() as db:
            db.add(EmailVerificationCode(email=email, purpose="register", code_hash=code_digest(email, "register", "123456"), expires_at=utcnow() + timedelta(minutes=5)))
            owner = User(username="owner", email="owner@local.invalid", password_hash=hash_password("owner123"), email_verified=True)
            db.add(owner)
            db.commit()
            token = tenant_context.set(owner.id)
            try:
                db.add(Resume(title="其他用户简历", content="private"))
                db.commit()
            finally:
                tenant_context.reset(token)

        response = client.post("/api/auth/register", json={"email": email, "password": "secure123", "verification_code": "123456"})
        assert response.status_code == 201
        assert response.json()["user"]["email"] == email
        assert client.get("/api/resumes").json() == []
        created = client.post("/api/resumes", json={"title": "我的简历", "target_role": "运营", "version": 1, "status": "draft", "content": "mine", "notes": "", "is_primary": True})
        assert created.status_code == 201
        assert [item["title"] for item in client.get("/api/resumes").json()] == ["我的简历"]
    finally:
        close_client(client, engine)


def test_invalid_password_is_rejected():
    client, SessionLocal, engine = build_client()
    try:
        with SessionLocal() as db:
            db.add(User(username="admin", email="admin@local.invalid", password_hash=hash_password("admin123"), is_active=True))
            db.commit()
        response = client.post("/api/auth/login", json={"identifier": "admin", "password": "wrong"})
        assert response.status_code == 401
        assert "set-cookie" not in response.headers
    finally:
        close_client(client, engine)


def test_job_favorites_are_isolated_per_user():
    client, SessionLocal, engine = build_client()
    try:
        with SessionLocal() as db:
            db.add_all([
                User(username="first", email="first@local.invalid", password_hash=hash_password("password123"), email_verified=True),
                User(username="second", email="second@local.invalid", password_hash=hash_password("password123"), email_verified=True),
            ])
            db.commit()

        assert client.post("/api/auth/login", json={"identifier": "first", "password": "password123"}).status_code == 200
        created = client.post("/api/jobs", json={"title": "我的收藏岗位", "is_favorite": False})
        assert created.status_code == 201
        job_id = created.json()["id"]
        favorite = client.post(f"/api/jobs/{job_id}/favorite?favorite=true")
        assert favorite.status_code == 200
        assert favorite.json()["is_favorite"] is True
        assert [job["id"] for job in client.get("/api/jobs?favorite_only=true").json()] == [job_id]

        assert client.post("/api/auth/logout").status_code == 200
        assert client.post("/api/auth/login", json={"identifier": "second", "password": "password123"}).status_code == 200
        assert client.get("/api/jobs").json() == []
        assert client.post(f"/api/jobs/{job_id}/favorite?favorite=false").status_code == 404
    finally:
        close_client(client, engine)


def test_bulk_job_delete_supports_selected_and_all_imported_with_tenant_isolation():
    client, SessionLocal, engine = build_client()
    try:
        with SessionLocal() as db:
            db.add_all([
                User(username="first", email="first@local.invalid", password_hash=hash_password("password123"), email_verified=True),
                User(username="second", email="second@local.invalid", password_hash=hash_password("password123"), email_verified=True),
            ])
            db.commit()

        assert client.post("/api/auth/login", json={"identifier": "second", "password": "password123"}).status_code == 200
        other_job = client.post("/api/jobs", json={"title": "其他用户岗位", "source_platform": "智联招聘"}).json()
        assert client.post("/api/auth/logout").status_code == 200

        assert client.post("/api/auth/login", json={"identifier": "first", "password": "password123"}).status_code == 200
        imported_ids = [
            client.post("/api/jobs", json={"title": f"导入岗位 {index}", "source_platform": "智联招聘"}).json()["id"]
            for index in range(8)
        ]
        manual_id = client.post("/api/jobs", json={"title": "手工岗位", "source_platform": "手动录入"}).json()["id"]

        preview = client.post(
            "/api/jobs/bulk-delete",
            json={"delete_all_imported": True, "preview": True},
        )
        assert preview.status_code == 200
        assert preview.json()["matched_count"] == 8
        assert preview.json()["cleared_count"] == 0
        assert preview.json()["preview"] is True

        selected = client.post(
            "/api/jobs/bulk-delete",
            json={"job_ids": imported_ids[:2], "preview": False},
        )
        assert selected.status_code == 200
        assert selected.json()["matched_count"] == 2
        assert selected.json()["cleared_count"] == 2
        assert selected.json()["cleared_job_ids"] == imported_ids[:2]

        with SessionLocal() as db:
            archived = [db.get(Job, job_id) for job_id in imported_ids[:2]]
            assert all(job is not None and job.is_archived for job in archived)

        restored = client.post(
            "/api/jobs/bulk-restore",
            json={"job_ids": imported_ids[:2]},
        )
        assert restored.status_code == 200
        assert restored.json()["restored_count"] == 2
        assert set(restored.json()["restored_job_ids"]) == set(imported_ids[:2])

        selected_again = client.post(
            "/api/jobs/bulk-delete",
            json={"job_ids": imported_ids[:2], "preview": False},
        )
        assert selected_again.json()["cleared_count"] == 2

        remaining_preview = client.post(
            "/api/jobs/bulk-delete",
            json={"delete_all_imported": True, "preview": True},
        )
        assert remaining_preview.json()["matched_count"] == 6

        all_imported = client.post(
            "/api/jobs/bulk-delete",
            json={"delete_all_imported": True, "preview": False},
        )
        assert all_imported.status_code == 200
        assert all_imported.json()["cleared_count"] == 6
        assert [job["id"] for job in client.get("/api/jobs").json()] == [manual_id]

        with SessionLocal() as db:
            assert all(db.get(Job, job_id) is not None for job_id in imported_ids)

        resume_id = client.post(
            "/api/resumes",
            json={"title": "归档保护简历", "content": "真实经历"},
        ).json()["id"]
        assert client.post(
            "/api/matches",
            json={"job_id": imported_ids[0], "resume_id": resume_id},
        ).status_code == 404
        assert client.post(
            "/api/applications",
            json={"job_id": imported_ids[0], "resume_id": resume_id},
        ).status_code == 404

        assert client.post("/api/auth/logout").status_code == 200
        assert client.post("/api/auth/login", json={"identifier": "second", "password": "password123"}).status_code == 200
        assert [job["id"] for job in client.get("/api/jobs").json()] == [other_job["id"]]
        cannot_restore_other_tenant = client.post(
            "/api/jobs/bulk-restore",
            json={"job_ids": imported_ids},
        )
        assert cannot_restore_other_tenant.json()["restored_count"] == 0
    finally:
        close_client(client, engine)


def test_all_business_root_models_are_tenant_scoped():
    client, SessionLocal, engine = build_client()
    try:
        with SessionLocal() as db:
            owner = User(username="owner", email="owner@local.invalid", password_hash=hash_password("password123"), email_verified=True)
            other = User(username="other", email="other@local.invalid", password_hash=hash_password("password123"), email_verified=True)
            db.add_all([owner, other])
            db.commit()
            db.refresh(owner)
            db.refresh(other)

            records = [
                UserProfile(full_name="Owner"),
                Resume(title="Owner resume"),
                Job(title="Owner job"),
                JobSearchExclusion(
                    search_signature="a" * 64,
                    source_url="https://www.zhaopin.com/job/owner-excluded",
                ),
                BlacklistCompany(company_name="Owner blocked company"),
                MatchAnalysis(job_id=1, resume_id=1, score=80),
                ResumeOptimization(match_id=1, job_id=1, resume_id=1),
                GreetingMessage(job_id=1, resume_id=1),
                ApplicationRecord(job_id=1, resume_id=1),
                AutomatedApplicationTask(
                    platform_key="zhaopin",
                    job_id=1,
                    resume_id=1,
                    job_title_snapshot="Owner job",
                    job_url_snapshot="https://www.zhaopin.com/job/owner",
                    resume_title_snapshot="Owner resume",
                ),
                ResumeAsset(original_filename="owner.pdf", size_bytes=1),
                InterviewSession(target_role="Owner role"),
            ]
            owner_token = tenant_context.set(owner.id)
            try:
                db.add_all(records)
                db.commit()
            finally:
                tenant_context.reset(owner_token)

            assert all(record.user_id == owner.id for record in records)
            models = [type(record) for record in records]

            other_token = tenant_context.set(other.id)
            try:
                for model in models:
                    assert list(db.scalars(select(model)).all()) == []
            finally:
                tenant_context.reset(other_token)

            owner_token = tenant_context.set(owner.id)
            try:
                for model in models:
                    assert len(db.scalars(select(model)).all()) == 1
            finally:
                tenant_context.reset(owner_token)
    finally:
        close_client(client, engine)
