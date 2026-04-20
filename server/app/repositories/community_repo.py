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

from app.models.community import Comment, Post
from app.repositories.base import BaseRepository


class PostRepository(BaseRepository[Post]):
    """帖子数据访问"""

    model_class = Post

    async def list_posts(
        self,
        *,
        category: str | None = None,
        sort: str = "latest",
        offset: int = 0,
        limit: int = 20,
    ) -> list[Post]:
        """查询帖子列表，支持分类筛选和排序"""
        filters = []
        if category:
            filters.append(Post.category == category)

        # 排序方式：latest / hot
        order = Post.created_at.desc()
        if sort == "hot":
            order = Post.view_count.desc()

        return await self.list_all(
            filters=filters,
            order_by=order,
            offset=offset,
            limit=limit,
        )


class CommentRepository(BaseRepository[Comment]):
    """评论数据访问"""

    model_class = Comment

    async def list_by_post(self, post_id: str, *, offset: int = 0, limit: int = 50) -> list[Comment]:
        """查询某帖子下的评论列表"""
        return await self.list_all(
            filters=[Comment.post_id == post_id],
            order_by=Comment.created_at.asc(),
            offset=offset,
            limit=limit,
        )
