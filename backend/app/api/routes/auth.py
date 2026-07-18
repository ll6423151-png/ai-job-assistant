import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db
from app.models.auth import AuthSession, EmailVerificationCode, User
from app.schemas.auth import AuthStatus, CodeLoginRequest, EmailCodeRequest, EmailCodeSent, MessageResponse, PasswordLoginRequest, RegisterRequest, ResetPasswordRequest, UserRead
from app.services.auth import clear_password_login_failures, consume_email_code, code_digest, create_session, enforce_password_login_limit, find_user_by_identifier, get_current_user, hash_password, issue_email_code, record_password_login_failure, request_ip_address, token_digest, utcnow, verify_password
from app.services.email_delivery import EmailDeliveryUnavailable, send_verification_email
router = APIRouter()

async def discard_unsent_code(db: AsyncSession, email: str, purpose: str, code: str) -> None:
    record = await db.scalar(select(EmailVerificationCode).where(EmailVerificationCode.email == email, EmailVerificationCode.purpose == purpose, EmailVerificationCode.code_hash == code_digest(email, purpose, code), EmailVerificationCode.consumed_at.is_(None)))
    if record is not None:
        await db.delete(record)
        await db.commit()

def set_session_cookie(response: Response, token: str, remember_me: bool) -> None:
    response.set_cookie(settings.auth_cookie_name, token, max_age=settings.auth_session_days * 86400 if remember_me else None, httponly=True, secure=settings.auth_cookie_secure, samesite='lax', path='/')

def auth_status(user: User, expires_at) -> AuthStatus:
    return AuthStatus(user=UserRead.model_validate(user), expires_at=expires_at.isoformat())

@router.post('/auth/email-codes', response_model=EmailCodeSent)
async def send_email_code(payload: EmailCodeRequest, request: Request, db: AsyncSession=Depends(get_db)) -> EmailCodeSent:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if payload.purpose == 'register' and existing:
        raise HTTPException(status_code=409, detail='该 QQ 邮箱已注册')
    if payload.purpose in {'login', 'reset_password'} and existing is None:
        raise HTTPException(status_code=404, detail='该 QQ 邮箱尚未注册')
    code = await issue_email_code(db, payload.email, payload.purpose, request.client.host if request.client else '')
    try:
        await asyncio.to_thread(send_verification_email, payload.email, code, payload.purpose)
    except EmailDeliveryUnavailable as exc:
        await discard_unsent_code(db, payload.email, payload.purpose, code)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        await discard_unsent_code(db, payload.email, payload.purpose, code)
        raise HTTPException(status_code=502, detail='验证码邮件发送失败，请检查 QQ SMTP 配置') from exc
    return EmailCodeSent(message='验证码已发送到你的 QQ 邮箱')

@router.post('/auth/register', response_model=AuthStatus, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession=Depends(get_db)) -> AuthStatus:
    if await db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=409, detail='该 QQ 邮箱已注册')
    await consume_email_code(db, payload.email, 'register', payload.verification_code)
    username = payload.email.split('@', 1)[0]
    user = User(username=username, email=payload.email, password_hash=hash_password(payload.password), email_verified=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token, session = await create_session(db, user, request, True)
    set_session_cookie(response, token, True)
    return auth_status(user, session.expires_at)

@router.post('/auth/login', response_model=AuthStatus)
async def login(payload: PasswordLoginRequest, request: Request, response: Response, db: AsyncSession=Depends(get_db)) -> AuthStatus:
    ip_address = request_ip_address(request)
    identifier_count, ip_count = await enforce_password_login_limit(db, payload.identifier, ip_address)
    user = await find_user_by_identifier(db, payload.identifier)
    if user is None or not verify_password(user.password_hash, payload.password) or (not user.is_active):
        await record_password_login_failure(
            db,
            payload.identifier,
            ip_address,
            identifier_count,
            ip_count,
        )
        raise HTTPException(status_code=401, detail='账号或密码错误')
    await clear_password_login_failures(db, payload.identifier)
    token, session = await create_session(db, user, request, payload.remember_me)
    set_session_cookie(response, token, payload.remember_me)
    return auth_status(user, session.expires_at)

@router.post('/auth/code-login', response_model=AuthStatus)
async def code_login(payload: CodeLoginRequest, request: Request, response: Response, db: AsyncSession=Depends(get_db)) -> AuthStatus:
    user = await db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=404, detail='该 QQ 邮箱尚未注册')
    await consume_email_code(db, payload.email, 'login', payload.verification_code)
    token, session = await create_session(db, user, request, payload.remember_me)
    set_session_cookie(response, token, payload.remember_me)
    return auth_status(user, session.expires_at)

@router.post('/auth/reset-password', response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession=Depends(get_db)) -> MessageResponse:
    user = await db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=404, detail='该 QQ 邮箱尚未注册')
    await consume_email_code(db, payload.email, 'reset_password', payload.verification_code)
    user.password_hash = hash_password(payload.new_password)
    for session in (await db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)))).all():
        session.revoked_at = utcnow()
    await db.commit()
    return MessageResponse(message='密码已重置，请重新登录')

@router.get('/auth/me', response_model=UserRead)
def me(user: User=Depends(get_current_user)) -> User:
    return user

@router.post('/auth/logout', response_model=MessageResponse)
async def logout(request: Request, response: Response, db: AsyncSession=Depends(get_db)) -> MessageResponse:
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        session = await db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            await db.commit()
    response.delete_cookie(settings.auth_cookie_name, path='/')
    return MessageResponse(message='已退出登录')
