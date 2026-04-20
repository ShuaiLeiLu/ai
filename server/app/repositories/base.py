"""
通用 Repository 基类

提供泛型 CRUD 操作，业务 Repository 继承后只需指定 model_class 即可获得：
  - get_by_id: 按主键查询
  - list_all: 分页列表（支持筛选条件）
  - create: 新增记录
  - update: 更新记录字段
  - delete: 删除记录
  - count: 统计数量
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """泛型 Repository，子类设置 model_class 即可使用全部 CRUD。"""

    model_class: type[ModelT]  # 子类必须赋值

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── 查询 ──

    async def get_by_id(self, record_id: str) -> ModelT | None:
        """按主键查询单条记录"""
        return await self.session.get(self.model_class, record_id)

    async def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        order_by: Any | None = None,
        filters: Sequence[Any] | None = None,
    ) -> list[ModelT]:
        """分页列表查询，支持任意 where 条件和排序"""
        stmt = select(self.model_class)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, *, filters: Sequence[Any] | None = None) -> int:
        """统计满足条件的记录数"""
        stmt = select(func.count()).select_from(self.model_class)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # ── 写入 ──

    async def create(self, instance: ModelT) -> ModelT:
        """新增一条记录并刷新以获取数据库默认值"""
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """更新已有记录的指定字段"""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """删除一条记录"""
        await self.session.delete(instance)
        await self.session.flush()
