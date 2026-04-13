from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header


@dataclass(frozen=True)
class PlatformRequestContext:
    user_id: str
    tenant_id: str
    display_name: Optional[str]
    is_admin: bool


async def get_platform_request_context(
    x_user_id: Optional[str] = Header(default=None),
    x_tenant_id: Optional[str] = Header(default=None),
    x_display_name: Optional[str] = Header(default=None),
    x_is_admin: Optional[str] = Header(default=None),
) -> PlatformRequestContext:
    user_id = x_user_id or "dev"
    tenant_id = x_tenant_id or "dev"
    display_name = x_display_name or user_id
    is_admin = (x_is_admin or "true").lower() == "true"
    return PlatformRequestContext(
        user_id=user_id,
        tenant_id=tenant_id,
        display_name=display_name,
        is_admin=is_admin,
    )