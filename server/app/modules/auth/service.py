"""
认证领域服务

双模式运行：
  1. 数据库模式（async 方法）：通过 UserRepository 操作 PostgreSQL
  2. 内存 mock 模式（sync 方法）：数据库未就绪时的降级方案

router 层通过 get_db_session 依赖注入决定使用哪种模式。
当 session 可用时走数据库路径；不可用时 fallback 到内存 mock。
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.modules.auth.schemas import AuthToken, LoginRequest, RegisterRequest, UserProfile
from app.repositories.user_repo import UserRepository


class AuthService:
    """认证领域服务 —— 同时支持数据库和内存 mock 两种模式。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        # ── 内存 mock 数据（数据库未就绪时使用） ──
        self._users_by_phone: dict[str, dict[str, str | int]] = {}
        self._initialized = False

    # ──────────── 数据库模式（async） ────────────

    async def async_login(self, session: AsyncSession, payload: LoginRequest) -> AuthToken:
        """使用数据库验证登录"""
        repo = UserRepository(session)
        user = await repo.get_by_phone(payload.phone)
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")

        token = create_access_token(subject=user.id)
        return AuthToken(
            access_token=token,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=self._model_to_profile(user),
        )

    async def async_register(self, session: AsyncSession, payload: RegisterRequest) -> UserProfile:
        """使用数据库注册新用户"""
        repo = UserRepository(session)
        existing = await repo.get_by_phone(payload.phone)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")

        user = User(
            id=f"u_{uuid4().hex[:10]}",
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            nickname=payload.nickname,
            membership_level="普通用户",
            battery_balance=300,
        )
        await repo.create(user)
        await session.commit()
        return self._model_to_profile(user)

    async def async_get_profile(self, session: AsyncSession, user_id: str) -> UserProfile:
        """从数据库获取用户 Profile"""
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        return self._model_to_profile(user)

    @staticmethod
    def _model_to_profile(user: User) -> UserProfile:
        """将 ORM User 对象转为 UserProfile schema"""
        return UserProfile(
            user_id=user.id,
            phone=user.phone,
            nickname=user.nickname,
            membership_level=user.membership_level,
            battery_balance=user.battery_balance,
        )

    # ──────────── 内存 mock 模式（sync，降级用） ────────────

    def _ensure_demo_data(self) -> None:
        """延迟初始化演示用户（避免 import 时调用 bcrypt）"""
        if self._initialized:
            return
        self._initialized = True
        self._users_by_phone["17607176885"] = {
            "user_id": "u_demo_owner",
            "phone": "17607176885",
            "password_hash": hash_password("Fuck@123.com"),
            "nickname": "产品负责人",
            "membership_level": "VIP 3",
            "battery_balance": 12000,
        }

    def login(self, payload: LoginRequest) -> AuthToken:
        """内存 mock 登录（降级）"""
        self._ensure_demo_data()
        user = self._users_by_phone.get(payload.phone)
        if not user or not verify_password(payload.password, str(user["password_hash"])):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")

        token = create_access_token(subject=str(user["user_id"]))
        return AuthToken(
            access_token=token,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=self._dict_to_profile(user),
        )

    def register(self, payload: RegisterRequest) -> UserProfile:
        """内存 mock 注册（降级）"""
        self._ensure_demo_data()
        if payload.phone in self._users_by_phone:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已注册")

        user_id = f"u_{uuid4().hex[:10]}"
        self._users_by_phone[payload.phone] = {
            "user_id": user_id,
            "phone": payload.phone,
            "password_hash": hash_password(payload.password),
            "nickname": payload.nickname,
            "membership_level": "普通用户",
            "battery_balance": 300,
        }
        return self.get_profile(user_id=user_id)

    def get_profile(self, user_id: str) -> UserProfile:
        """内存 mock 获取 Profile（降级）"""
        self._ensure_demo_data()
        for user in self._users_by_phone.values():
            if user["user_id"] == user_id:
                return self._dict_to_profile(user)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    @staticmethod
    def _dict_to_profile(user: dict[str, str | int]) -> UserProfile:
        """将内存 dict 转为 UserProfile schema"""
        return UserProfile(
            user_id=str(user["user_id"]),
            phone=str(user["phone"]),
            nickname=str(user["nickname"]),
            membership_level=str(user["membership_level"]),
            battery_balance=int(user["battery_balance"]),
        )
