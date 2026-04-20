"""
社区领域服务

双模式运行：
  1. 数据库模式（async）：通过 PostRepository 操作 PostgreSQL
  2. 内存 mock 模式（sync）：数据库未就绪时的降级方案
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Post as PostModel
from app.modules.community.schemas import (
    CommunityComment,
    CommunityCreatePostRequest,
    CommunityPost,
    CommunityPostDetail,
)
from app.repositories.community_repo import PostRepository


class CommunityService:
    """社区领域服务 —— 同时支持数据库和内存 mock 两种模式。"""

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        # 预置一条帖子与评论，便于前端快速验证交互。
        self._posts: dict[str, CommunityPostDetail] = {
            "p_1": CommunityPostDetail(
                post_id="p_1",
                title="盘后复盘：AI主线延续，低位基建值得关注",
                author="情绪派张三",
                excerpt="今日盘面资金继续围绕 AI 与高股息轮动，低位基建有承接信号。",
                likes=34,
                comments=2,
                created_at=now - timedelta(hours=4),
                content="资金切换仍快，建议聚焦核心龙头与低位补涨。",
                tags=["复盘", "AI", "基建"],
                comment_list=[
                    CommunityComment(
                        comment_id="c_1",
                        author="基本面分析师",
                        content="补涨逻辑成立，但仓位仍要控制。",
                        created_at=now - timedelta(hours=3, minutes=20),
                    ),
                    CommunityComment(
                        comment_id="c_2",
                        author="量化小助手",
                        content="成交量未显著放大，追高需谨慎。",
                        created_at=now - timedelta(hours=2, minutes=40),
                    ),
                ],
            )
        }

    def list_posts(self, q: str | None = None) -> list[CommunityPost]:
        keyword = (q or "").strip().lower()
        posts = sorted(self._posts.values(), key=lambda item: item.created_at, reverse=True)
        if keyword:
            posts = [
                item
                for item in posts
                if keyword in item.title.lower() or keyword in item.excerpt.lower()
            ]
        return [CommunityPost(**item.model_dump(include=set(CommunityPost.model_fields.keys()))) for item in posts]

    def get_post(self, post_id: str) -> CommunityPostDetail:
        post = self._posts.get(post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
        return post

    def create_post(self, payload: CommunityCreatePostRequest, author: str = "当前用户") -> CommunityPostDetail:
        """内存 mock 创建帖子"""
        now = datetime.now(tz=UTC)
        post_id = f"p_{uuid4().hex[:10]}"
        detail = CommunityPostDetail(
            post_id=post_id,
            title=payload.title,
            author=author,
            excerpt=payload.content[:80],
            likes=0,
            comments=0,
            created_at=now,
            content=payload.content,
            tags=payload.tags,
            comment_list=[],
        )
        self._posts[post_id] = detail
        return detail

    # ──────────── 数据库模式（async） ────────────

    async def async_list_posts(self, session: AsyncSession, *, q: str | None = None) -> list[CommunityPost]:
        """从数据库查询帖子列表"""
        repo = PostRepository(session)
        posts = await repo.list_posts(sort="latest")
        keyword = (q or "").strip().lower()
        result = []
        for p in posts:
            if keyword and keyword not in p.title.lower() and keyword not in p.content.lower():
                continue
            result.append(CommunityPost(
                post_id=p.id,
                title=p.title,
                author="",  # 需要 join User 表，后续完善
                excerpt=p.content[:80],
                likes=p.like_count,
                comments=p.comment_count,
                created_at=p.created_at,
            ))
        return result

    async def async_get_post(self, session: AsyncSession, post_id: str) -> CommunityPostDetail:
        """从数据库查询帖子详情"""
        repo = PostRepository(session)
        p = await repo.get_by_id(post_id)
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
        return CommunityPostDetail(
            post_id=p.id,
            title=p.title,
            author="",
            excerpt=p.content[:80],
            likes=p.like_count,
            comments=p.comment_count,
            created_at=p.created_at,
            content=p.content,
            tags=[],  # 后续扩展
            comment_list=[],  # 后续加载评论
        )

    async def async_create_post(
        self, session: AsyncSession, user_id: str, payload: CommunityCreatePostRequest
    ) -> CommunityPostDetail:
        """在数据库创建帖子"""
        repo = PostRepository(session)
        post = PostModel(
            id=f"p_{uuid4().hex[:10]}",
            author_id=user_id,
            title=payload.title,
            content=payload.content,
            category="discussion",
        )
        await repo.create(post)
        await session.commit()
        return CommunityPostDetail(
            post_id=post.id,
            title=post.title,
            author="",
            excerpt=post.content[:80],
            likes=0,
            comments=0,
            created_at=post.created_at,
            content=post.content,
            tags=payload.tags,
            comment_list=[],
        )
