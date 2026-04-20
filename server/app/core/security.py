from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

_ALGORITHM = "HS256"
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: str, expires_delta: timedelta | None = None, **extra: Any) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {"sub": subject, "exp": expire, **extra}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token, returning its claims."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的访问令牌") from exc


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — extracts `user_id` from the Bearer token.

    When no token is provided (e.g. during early dev / Swagger testing),
    falls back to the demo user so that the API remains functional without
    a login flow.  This fallback will be removed once the login flow is
    wired end-to-end.
    """
    if credentials is None:
        # 开发阶段：无 token 时 fallback 到种子演示用户，确保能看到 DB 真实数据
        return "u_demo"
    try:
        claims = decode_access_token(credentials.credentials)
        sub = claims.get("sub")
        if not sub:
            # token 合法但缺少 sub 字段，开发阶段 fallback
            return "u_demo"
        return str(sub)
    except HTTPException:
        # token 无效或过期，开发阶段 fallback 到演示用户
        return "u_demo"
