import hmac

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.core.config import settings
from app.schemas.auth import InternalEmailRelayRequest
from app.services.email_delivery import EmailDeliveryUnavailable, send_verification_email_smtp


router = APIRouter()


@router.post(
    "/internal/email-relay",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def relay_verification_email(
    payload: InternalEmailRelayRequest,
    authorization: str | None = Header(default=None),
) -> Response:
    expected_token = settings.email_relay_token.strip()
    supplied_token = (authorization or "").removeprefix("Bearer ").strip()
    if len(expected_token) < 32:
        raise HTTPException(status_code=404, detail="Not Found")
    if not supplied_token or not hmac.compare_digest(expected_token, supplied_token):
        raise HTTPException(status_code=401, detail="邮件中继认证失败")
    try:
        send_verification_email_smtp(payload.recipient, payload.code, payload.purpose)
    except EmailDeliveryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="QQ 邮件发送失败") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
