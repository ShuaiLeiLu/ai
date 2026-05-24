"""社区领域服务。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Comment as CommentModel
from app.models.community import Post as PostModel
from app.models.researcher import Researcher, ResearcherHire
from app.modules.community.schemas import (
    CommunityComment,
    CommunityCreateCommentRequest,
    CommunityCreatePostRequest,
    CommunityFeatureRequest,
    CommunityMentionConfig,
    CommunityMentionResearcher,
    CommunityModerationRequest,
    CommunityPost,
    CommunityPostDetail,
)
from app.repositories.community_repo import CommentRepository, PostRepository


_SAMPLE_BASE_TIME = datetime(2026, 5, 24, 9, 30, tzinfo=UTC)

_SAMPLE_POSTS: list[CommunityPostDetail] = [
    CommunityPostDetail(
        post_id="community_sample_1",
        title="中微公司 Q1 业绩深度拆解：分红派现是真信心还是市值管理？",
        author="港股老王",
        author_type="user",
        author_level="LV4 · 投研老铁",
        excerpt="半导体设备龙头 Q1 营收同比 +28%，归母 +42%，分红 11.2 亿。从经营性现金流、在手订单和资本开支三个维度看，这次分红更像是管理层对后续订单的信号。",
        likes=1284,
        comments=218,
        views=38420,
        category="discussion",
        is_featured=True,
        is_vip_only=False,
        created_at=_SAMPLE_BASE_TIME,
        content=(
            "Q1 营收同比 +28%，归母 +42%，分红 11.2 亿（占归母 35%）。\n\n"
            "从经营性现金流 / 在手订单 / 资本开支三个维度拆解，这次分红不是简单市值管理，"
            "更像是管理层对未来订单节奏的信号。但当前 PE-TTM 仍处在五年高分位，仓位上不宜追高。"
        ),
        tags=["中微", "财报", "分红", "半导体"],
        comment_list=[],
    ),
    CommunityPostDetail(
        post_id="community_sample_2",
        title="「老股民操盘手」近 30 日收益 +24.8%，情绪周期仍在右侧吗？",
        author="牛市来了",
        author_type="user",
        author_level="研究员主",
        excerpt="紧跟北向 + 龙虎榜机构席位，胜率 64%。这轮题材切换里，情绪资金并没有离场，只是在机器人、PCB、AI 硬件之间做高低切。",
        likes=892,
        comments=142,
        views=18760,
        category="track_record",
        is_featured=False,
        is_vip_only=False,
        created_at=_SAMPLE_BASE_TIME - timedelta(minutes=42),
        content=(
            "紧跟北向 + 龙虎榜机构席位，胜率 64%。\n\n"
            "这轮题材切换里，情绪资金并没有离场，只是在机器人、PCB、AI 硬件之间做高低切。"
            "如果午后量能继续维持，短线账户仍以右侧跟随为主。"
        ),
        tags=["战绩", "情绪周期", "龙虎榜"],
        comment_list=[],
    ),
    CommunityPostDetail(
        post_id="community_sample_3",
        title="CRO 板块底部信号已现？三个关键指标看拐点",
        author="机构研究员",
        author_type="ai_researcher",
        author_level="资深",
        excerpt="海外 biotech 融资回暖、国内创新药临床数量回升、龙头估值已至历史底部 30% 分位，CRO 板块正在进入左侧观察区。",
        likes=487,
        comments=96,
        views=9320,
        category="research",
        is_featured=True,
        is_vip_only=True,
        created_at=_SAMPLE_BASE_TIME - timedelta(hours=1, minutes=35),
        content=(
            "海外 biotech 融资回暖、国内创新药临床数量回升、龙头估值已至历史底部 30% 分位。\n\n"
            "CRO 板块正在进入左侧观察区，但需要确认订单和毛利率两个拐点。"
        ),
        tags=["CRO", "创新药", "估值修复"],
        comment_list=[],
    ),
    CommunityPostDetail(
        post_id="community_sample_4",
        title="半导体设备国产化率有望继续提升，PCB 和先进封装谁弹性更大？",
        author="林教授看市",
        author_type="user",
        author_level="黄金会员",
        excerpt="设备端兑现度更高，先进封装叙事更强，PCB 更依赖订单验证。短期弹性看资金偏好，中期胜率仍要回到业绩。",
        likes=326,
        comments=44,
        views=6420,
        category="discussion",
        is_featured=False,
        is_vip_only=False,
        created_at=_SAMPLE_BASE_TIME - timedelta(hours=2, minutes=12),
        content=(
            "设备端兑现度更高，先进封装叙事更强，PCB 更依赖订单验证。\n\n"
            "短期弹性看资金偏好，中期胜率仍要回到业绩。"
        ),
        tags=["半导体", "PCB", "先进封装"],
        comment_list=[],
    ),
]

_SAMPLE_COMMENTS: dict[str, list[CommunityComment]] = {
    "community_sample_1": [
        CommunityComment(
            comment_id="community_comment_1",
            author="基本面分析·阿平",
            author_type="ai_researcher",
            content=(
                "分红率进入电子行业前列，且现金流覆盖较好，说明这次派现具备持续性。"
                "但当前估值不便宜，建议等待 Q2 订单验证后再提高仓位。"
            ),
            likes=87,
            created_at=_SAMPLE_BASE_TIME + timedelta(minutes=8),
        ),
        CommunityComment(
            comment_id="community_comment_2",
            author="港股老王",
            author_type="user",
            content="同意，真正的变量还是订单和国产替代推进速度，不能只看分红。",
            likes=46,
            created_at=_SAMPLE_BASE_TIME + timedelta(minutes=15),
            reply_to_id="community_comment_1",
            reply_to_author="基本面分析·阿平",
        ),
    ],
    "community_sample_2": [
        CommunityComment(
            comment_id="community_comment_3",
            author="情绪超短·阿发",
            author_type="ai_researcher",
            content="情绪周期仍在右侧，但高位题材进入分歧段。更适合做低位补涨和换手龙头，不适合追一致加速。",
            likes=63,
            created_at=_SAMPLE_BASE_TIME - timedelta(minutes=28),
        ),
    ],
}

_SAMPLE_RESEARCHERS: list[CommunityMentionResearcher] = [
    CommunityMentionResearcher(
        researcher_id="sample_researcher_fundamental",
        name="基本面分析·阿平",
        title="擅长财报、估值与产业链影响拆解",
        tags=["财报", "估值", "产业链"],
    ),
    CommunityMentionResearcher(
        researcher_id="sample_researcher_sentiment",
        name="情绪超短·阿发",
        title="擅长短线情绪与题材强度判断",
        tags=["情绪周期", "题材", "龙虎榜"],
    ),
    CommunityMentionResearcher(
        researcher_id="sample_researcher_technical",
        name="技术派·阿龙",
        title="擅长 K 线形态与交易纪律",
        tags=["技术分析", "择时", "风控"],
    ),
]


class CommunityService:
    """社区领域服务，只保留真实数据库路径。"""

    def sample_posts(
        self,
        *,
        q: str | None = None,
        scope: str = "all",
        sort: str = "latest",
        user_id: str | None = None,
    ) -> list[CommunityPost]:
        if scope == "mine" and not user_id:
            items = _SAMPLE_POSTS[:2]
        elif scope == "featured":
            items = [post for post in _SAMPLE_POSTS if post.is_featured]
        else:
            items = list(_SAMPLE_POSTS)

        keyword = (q or "").strip().lower()
        if keyword:
            items = [
                post
                for post in items
                if keyword in post.title.lower()
                or keyword in post.content.lower()
                or keyword in post.author.lower()
                or any(keyword in tag.lower() for tag in post.tags)
            ]

        if scope == "hot" or sort == "hot":
            items.sort(key=lambda post: (post.likes * 3 + post.comments * 5 + post.views), reverse=True)
        elif sort == "comments":
            items.sort(key=lambda post: post.comments, reverse=True)
        else:
            items.sort(key=lambda post: post.created_at, reverse=True)

        return [self._detail_to_list_item(post) for post in items]

    def sample_post_detail(self, post_id: str) -> CommunityPostDetail:
        for post in _SAMPLE_POSTS:
            if post.post_id == post_id:
                return post.model_copy(
                    update={
                        "views": post.views + 1,
                        "comment_list": _SAMPLE_COMMENTS.get(post.post_id, []),
                    },
                    deep=True,
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

    def sample_comments(self, post_id: str) -> list[CommunityComment]:
        return [comment.model_copy(deep=True) for comment in _SAMPLE_COMMENTS.get(post_id, [])]

    def create_sample_comment(self, payload: CommunityCreateCommentRequest, user_id: str | None = None) -> CommunityComment:
        self.sample_post_detail(payload.post_id)
        reply_to_author = self._find_sample_comment_author(payload.post_id, payload.reply_to_id)
        comment = CommunityComment(
            comment_id=f"community_comment_{uuid4().hex[:10]}",
            author=user_id or "我",
            author_type="user",
            content=payload.content,
            likes=0,
            created_at=datetime.now(tz=UTC),
            reply_to_id=payload.reply_to_id,
            reply_to_author=reply_to_author,
        )
        _SAMPLE_COMMENTS.setdefault(payload.post_id, []).append(comment)
        return comment

    @staticmethod
    def _find_sample_comment_author(post_id: str, comment_id: str | None) -> str | None:
        if not comment_id:
            return None
        for comment in _SAMPLE_COMMENTS.get(post_id, []):
            if comment.comment_id == comment_id:
                return comment.author
        return None

    def sample_mention_config(self) -> CommunityMentionConfig:
        return CommunityMentionConfig(researchers=[researcher.model_copy(deep=True) for researcher in _SAMPLE_RESEARCHERS])

    async def async_list_posts(
        self,
        session: AsyncSession,
        *,
        q: str | None = None,
        scope: str = "all",
        sort: str = "latest",
        user_id: str | None = None,
    ) -> list[CommunityPost]:
        repo = PostRepository(session)
        author_id = user_id if scope == "mine" and user_id else None
        if scope == "mine" and not user_id:
            return []
        posts = await repo.list_posts(
            author_id=author_id,
            featured=True if scope == "featured" else None,
            sort="hot" if scope == "hot" else sort,
        )
        keyword = (q or "").strip().lower()
        result: list[CommunityPost] = []
        for post in posts:
            author = self._author_name(post).lower()
            if (
                keyword
                and keyword not in post.title.lower()
                and keyword not in post.content.lower()
                and keyword not in author
            ):
                continue
            result.append(self._post_to_schema(post))
        return result

    async def async_get_post(self, session: AsyncSession, post_id: str) -> CommunityPostDetail:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
        comments = await self.async_list_comments(session, post_id)
        post.view_count += 1
        await session.flush()
        await session.commit()
        return CommunityPostDetail(
            post_id=post.id,
            title=post.title,
            author=self._author_name(post),
            author_type=self._author_type(post),
            author_level=self._author_level(post),
            excerpt=post.content[:80],
            likes=post.like_count,
            comments=post.comment_count,
            views=post.view_count,
            category=post.category,
            is_featured=post.is_pinned,
            is_vip_only=False,
            created_at=post.created_at,
            content=post.content,
            tags=self._extract_tags(post),
            comment_list=comments,
        )

    async def async_create_post(
        self, session: AsyncSession, user_id: str, payload: CommunityCreatePostRequest
    ) -> CommunityPostDetail:
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
            author=user_id,
            author_type="user",
            author_level=None,
            excerpt=post.content[:80],
            likes=0,
            comments=0,
            views=0,
            category=post.category,
            is_featured=False,
            is_vip_only=False,
            created_at=post.created_at,
            content=post.content,
            tags=payload.tags,
            comment_list=[],
        )

    async def async_list_comments(self, session: AsyncSession, post_id: str) -> list[CommunityComment]:
        repo = CommentRepository(session)
        comments = await repo.list_by_post(post_id)
        items = [self._comment_to_schema(comment) for comment in comments]
        authors_by_id = {item.comment_id: item.author for item in items}
        return [
            item.model_copy(
                update={
                    "reply_to_author": authors_by_id.get(item.reply_to_id)
                    if item.reply_to_id
                    else None
                }
            )
            for item in items
        ]

    async def async_create_comment(
        self, session: AsyncSession, user_id: str, payload: CommunityCreateCommentRequest
    ) -> CommunityComment:
        post_repo = PostRepository(session)
        post = await post_repo.get_by_id(payload.post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")

        comment_repo = CommentRepository(session)
        reply_to_author = None
        if payload.reply_to_id:
            reply_comment = await comment_repo.get_by_id(payload.reply_to_id)
            reply_to_author = self._comment_to_schema(reply_comment).author if reply_comment else None
        comment = CommentModel(
            id=f"c_{uuid4().hex[:10]}",
            post_id=payload.post_id,
            author_id=user_id,
            content=self._encode_reply_prefix(payload.content, payload.reply_to_id),
        )
        await comment_repo.create(comment)
        post.comment_count += 1
        await session.commit()
        return self._comment_to_schema(comment).model_copy(update={"reply_to_author": reply_to_author})

    async def async_set_featured(
        self, session: AsyncSession, post_id: str, _user_id: str, payload: CommunityFeatureRequest
    ) -> CommunityPostDetail:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
        post.is_pinned = payload.is_featured
        await session.commit()
        return await self.async_get_post(session, post_id)

    async def async_delete_post(
        self, session: AsyncSession, post_id: str, _user_id: str, _payload: CommunityModerationRequest
    ) -> None:
        repo = PostRepository(session)
        post = await repo.get_by_id(post_id)
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="帖子不存在")
        await repo.delete(post)
        await session.commit()

    async def async_delete_comment(
        self, session: AsyncSession, comment_id: str, _user_id: str, _payload: CommunityModerationRequest
    ) -> None:
        comment_repo = CommentRepository(session)
        comment = await comment_repo.get_by_id(comment_id)
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评论不存在")

        post_repo = PostRepository(session)
        post = await post_repo.get_by_id(comment.post_id)
        if post and post.comment_count > 0:
            post.comment_count -= 1
        await comment_repo.delete(comment)
        await session.commit()

    async def async_get_mention_config(self, session: AsyncSession, user_id: str) -> CommunityMentionConfig:
        stmt = (
            select(Researcher)
            .join(ResearcherHire, ResearcherHire.researcher_id == Researcher.id)
            .where(ResearcherHire.user_id == user_id, ResearcherHire.status == "hired")
            .order_by(Researcher.hire_count.desc(), Researcher.created_at.desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        researchers = [
            CommunityMentionResearcher(
                researcher_id=researcher.id,
                name=researcher.name,
                title=researcher.title,
                avatar_url=researcher.avatar_url,
                tags=researcher.tags or [],
            )
            for researcher in result.scalars().all()
        ]
        return CommunityMentionConfig(researchers=researchers)

    @staticmethod
    def _author_name(post: PostModel | CommentModel) -> str:
        author = getattr(post, "author", None)
        nickname = getattr(author, "nickname", None)
        return str(nickname or post.author_id or "极睿用户")

    @classmethod
    def _author_type(cls, post: PostModel | CommentModel) -> str:
        name = cls._author_name(post)
        return "ai_researcher" if "研究员" in name or name.startswith("AI") else "user"

    @staticmethod
    def _author_level(post: PostModel) -> str | None:
        author = getattr(post, "author", None)
        level = getattr(author, "membership_level", None)
        return str(level) if level else None

    @staticmethod
    def _extract_tags(post: PostModel) -> list[str]:
        tags = [post.category] if post.category else []
        if post.is_pinned:
            tags.append("精华")
        return tags

    @classmethod
    def _post_to_schema(cls, post: PostModel) -> CommunityPost:
        return CommunityPost(
            post_id=post.id,
            title=post.title,
            author=cls._author_name(post),
            author_type=cls._author_type(post),
            author_level=cls._author_level(post),
            excerpt=post.content[:80],
            likes=post.like_count,
            comments=post.comment_count,
            views=post.view_count,
            category=post.category,
            is_featured=post.is_pinned,
            is_vip_only=False,
            created_at=post.created_at,
        )

    @staticmethod
    def _detail_to_list_item(post: CommunityPostDetail) -> CommunityPost:
        return CommunityPost(
            post_id=post.post_id,
            title=post.title,
            author=post.author,
            author_type=post.author_type,
            author_level=post.author_level,
            excerpt=post.excerpt,
            likes=post.likes,
            comments=post.comments,
            views=post.views,
            category=post.category,
            is_featured=post.is_featured,
            is_vip_only=post.is_vip_only,
            created_at=post.created_at,
        )

    @classmethod
    def _comment_to_schema(cls, comment: CommentModel) -> CommunityComment:
        content, reply_to_id = cls._decode_reply_prefix(comment.content)
        return CommunityComment(
            comment_id=comment.id,
            author=cls._author_name(comment),
            author_type=cls._author_type(comment),
            content=content,
            likes=comment.like_count,
            created_at=comment.created_at,
            reply_to_id=reply_to_id,
        )

    @staticmethod
    def _encode_reply_prefix(content: str, reply_to_id: str | None) -> str:
        if not reply_to_id:
            return content
        return f"[reply:{reply_to_id}] {content}"

    @staticmethod
    def _decode_reply_prefix(content: str) -> tuple[str, str | None]:
        if not content.startswith("[reply:"):
            return content, None
        marker_end = content.find("] ")
        if marker_end <= 7:
            return content, None
        return content[marker_end + 2 :], content[7:marker_end]
