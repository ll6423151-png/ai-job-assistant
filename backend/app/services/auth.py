import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db, tenant_context
from app.models.auth import AuthSession, EmailVerificationCode, LoginAttempt, User
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=15)
LOGIN_IDENTIFIER_LIMIT = 5
LOGIN_IP_LIMIT = 20

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def code_digest(email: str, purpose: str, code: str) -> str:
    value = f'{email}:{purpose}:{code}'.encode('utf-8')
    return hmac.new(settings.auth_secret_key.encode('utf-8'), value, hashlib.sha256).hexdigest()

async def issue_email_code(db: AsyncSession, email: str, purpose: str, requested_ip: str) -> str:
    now = utcnow()
    latest = await db.scalar(select(EmailVerificationCode).where(EmailVerificationCode.email == email, EmailVerificationCode.purpose == purpose).order_by(desc(EmailVerificationCode.created_at), desc(EmailVerificationCode.id)))
    if latest and (now - as_utc(latest.created_at)).total_seconds() < 60:
        raise HTTPException(status_code=429, detail='验证码发送过于频繁，请稍后再试')
    recent_count = await db.scalar(select(func.count(EmailVerificationCode.id)).where(EmailVerificationCode.email == email, EmailVerificationCode.created_at >= now - timedelta(hours=1))) or 0
    if recent_count >= 10:
        raise HTTPException(status_code=429, detail='验证码请求次数过多，请一小时后再试')
    code = f'{secrets.randbelow(1000000):06d}'
    db.add(EmailVerificationCode(email=email, purpose=purpose, code_hash=code_digest(email, purpose, code), expires_at=now + timedelta(minutes=5), requested_ip=requested_ip))
    await db.commit()
    return code

async def consume_email_code(db: AsyncSession, email: str, purpose: str, code: str) -> None:
    record = await db.scalar(select(EmailVerificationCode).where(EmailVerificationCode.email == email, EmailVerificationCode.purpose == purpose, EmailVerificationCode.consumed_at.is_(None)).order_by(desc(EmailVerificationCode.created_at), desc(EmailVerificationCode.id)))
    if record is None or as_utc(record.expires_at) <= utcnow() or record.failed_attempts >= 5:
        raise HTTPException(status_code=400, detail='验证码无效或已过期')
    if not hmac.compare_digest(record.code_hash, code_digest(email, purpose, code)):
        record.failed_attempts += 1
        await db.commit()
        raise HTTPException(status_code=400, detail='验证码错误')
    record.consumed_at = utcnow()
    await db.commit()

async def find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    normalized = identifier.strip().lower()
    return await db.scalar(select(User).where(or_(func.lower(User.email) == normalized, func.lower(User.username) == normalized)))


def login_identifier_digest(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


def request_ip_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if settings.environment == "production" and forwarded:
        # Render preserves the originating client as the first forwarded address.
        return forwarded.split(",")[0].strip()[:80]
    return (request.client.host if request.client else "")[:80]


async def enforce_password_login_limit(db: AsyncSession, identifier: str, ip_address: str) -> tuple[int, int]:
    now = utcnow()
    cutoff = now - LOGIN_ATTEMPT_WINDOW
    identifier_hash = login_identifier_digest(identifier)
    await db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    identifier_count = await db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.identifier_hash == identifier_hash,
            LoginAttempt.created_at >= cutoff,
        )
    ) or 0
    ip_count = await db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.created_at >= cutoff,
        )
    ) or 0
    await db.commit()
    if identifier_count >= LOGIN_IDENTIFIER_LIMIT or ip_count >= LOGIN_IP_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请 15 分钟后再试",
            headers={"Retry-After": str(int(LOGIN_ATTEMPT_WINDOW.total_seconds()))},
        )
    return identifier_count, ip_count


async def record_password_login_failure(
    db: AsyncSession,
    identifier: str,
    ip_address: str,
    identifier_count: int,
    ip_count: int,
) -> None:
    db.add(
        LoginAttempt(
            identifier_hash=login_identifier_digest(identifier),
            ip_address=ip_address,
            created_at=utcnow(),
        )
    )
    await db.commit()
    if identifier_count + 1 >= LOGIN_IDENTIFIER_LIMIT or ip_count + 1 >= LOGIN_IP_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请 15 分钟后再试",
            headers={"Retry-After": str(int(LOGIN_ATTEMPT_WINDOW.total_seconds()))},
        )


async def clear_password_login_failures(db: AsyncSession, identifier: str) -> None:
    await db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.identifier_hash == login_identifier_digest(identifier)
        )
    )
    await db.commit()

async def create_session(db: AsyncSession, user: User, request: Request, remember_me: bool) -> tuple[str, AuthSession]:
    now = utcnow()
    token = secrets.token_urlsafe(48)
    days = settings.auth_session_days if remember_me else 1
    session = AuthSession(user_id=user.id, token_hash=token_digest(token), user_agent=(request.headers.get('user-agent') or '')[:300], ip_address=(request.client.host if request.client else '')[:80], expires_at=now + timedelta(days=days), last_seen_at=now)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return (token, session)

async def get_session_from_token(db: AsyncSession, token: str) -> tuple[AuthSession, User] | None:
    now = utcnow()
    session = await db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token), AuthSession.revoked_at.is_(None)))
    if session is None or as_utc(session.expires_at) <= now:
        return None
    if as_utc(session.last_seen_at) + timedelta(minutes=settings.auth_idle_minutes) <= now:
        session.revoked_at = now
        await db.commit()
        return None
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    if (now - as_utc(session.last_seen_at)).total_seconds() >= 300:
        session.last_seen_at = now
        await db.commit()
    return (session, user)

async def get_current_user(db: AsyncSession=Depends(get_db), session_token: str | None=Cookie(default=None, alias=settings.auth_cookie_name)):
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='请先登录')
    result = await get_session_from_token(db, session_token)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='登录已过期，请重新登录')
    _, user = result
    token = tenant_context.set(user.id)
    try:
        yield user
    finally:
        tenant_context.reset(token)
