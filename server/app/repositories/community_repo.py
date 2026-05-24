"""
社区 Repository —— Post / Comment 表的数据访问层

提供：
  - 帖子列表（支持分类筛选、热门/最新排序）
  - 帖子详情
  - 评论列表
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.community import Comment, Post
from app.repositories.base import BaseRepository


class PostRepository(BaseRepository[Post]):
    """帖子数据访问"""

    model_class = Post

    async def list_posts(
        self,
        *,
        author_id: str | None = None,
        category: str | None = None,
        featured: bool | None = None,
        sort: str = "latest",
        offset: int = 0,
        limit: int = 20,
    ) -> list[Post]:
        """查询帖子列表，支持分类筛选和排序"""
        filters = []
        if author_id:
            filters.append(Post.author_id == author_id)
        if category:
            filters.append(Post.category == category)
        if featured is not None:
            filters.append(Post.is_pinned == featured)

        # 排序方式：latest / hot / comments
        order = Post.created_at.desc()
        if sort == "hot":
            order = (Post.like_count + Post.comment_count + Post.view_count).desc()
        elif sort == "comments":
            order = Post.comment_count.desc()

        stmt = (
            select(Post)
            .options(selectinload(Post.author))
            .order_by(order)
            .offset(offset)
            .limit(limit)
        )
        for condition in filters:
            stmt = stmt.where(condition)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, record_id: str) -> Post | None:
        """按主键查询帖子，并预加载作者。"""
        stmt = select(Post).options(selectinload(Post.author)).where(Post.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class CommentRepository(BaseRepository[Comment]):
    """评论数据访问"""

    model_class = Comment

    async def list_by_post(self, post_id: str, *, offset: int = 0, limit: int = 50) -> list[Comment]:
        """查询某帖子下的评论列表"""
        stmt = (
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
