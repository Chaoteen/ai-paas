from dataclasses import dataclass
from fastapi import Header, HTTPException
import jwt
from .config import settings


@dataclass
class UserContext:
    user_id: str
    tenant_id: str
    is_admin: bool = False
    display_name: str = "user"


def get_current_user(authorization: str = Header(default="")) -> UserContext:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = str(payload.get("user_id") or "")
    tenant_id = str(payload.get("tenant_id") or "")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing user_id/tenant_id")

    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        is_admin=bool(payload.get("is_admin", False)),
        display_name=str(payload.get("display_name") or "user"),
    )
