from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.modules.community.schemas import (
    CommunityCreateCommentRequest,
    CommunityFeatureRequest,
    CommunityModerationRequest,
)
from app.modules.community.service import CommunityService


def test_post_schema_exposes_author_and_interaction_fields() -> None:
    post = SimpleNamespace(
        id="p_1",
        title="中微分红怎么看？",
        author_id="u_1",
        author=SimpleNamespace(nickname="极睿智投员", membership_level="VIP1"),
        content="分红率进入电子行业前列，仍要观察 Q2 订单验证。",
        like_count=18,
        comment_count=3,
        view_count=256,
        category="discussion",
        is_pinned=True,
        created_at=datetime(2026, 5, 24, 9, 30, tzinfo=UTC),
    )

    schema = CommunityService._post_to_schema(post)  # type: ignore[arg-type]

    assert schema.author == "极睿智投员"
    assert schema.author_level == "VIP1"
    assert schema.views == 256
    assert schema.is_featured is True
    assert schema.category == "discussion"


@pytest.mark.asyncio
async def test_list_posts_filters_featured_and_searches_author(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = [
        SimpleNamespace(
            id="p_1",
            title="半导体设备跟踪",
            author_id="u_1",
            author=SimpleNamespace(nickname="港股老王", membership_level="VIP1"),
            content="中微公司分红与订单节奏。",
            like_count=18,
            comment_count=3,
            view_count=256,
            category="discussion",
            is_pinned=True,
            created_at=datetime(2026, 5, 24, 9, 30, tzinfo=UTC),
        ),
        SimpleNamespace(
            id="p_2",
            title="新能源观察",
            author_id="u_2",
            author=SimpleNamespace(nickname="价值小马", membership_level="普通用户"),
            content="销量回暖。",
            like_count=8,
            comment_count=1,
            view_count=56,
            category="discussion",
            is_pinned=False,
            created_at=datetime(2026, 5, 24, 10, 30, tzinfo=UTC),
        ),
    ]
    calls: list[dict[str, object]] = []

    class FakePostRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def list_posts(self, **kwargs: object) -> list[object]:
            calls.append(kwargs)
            return [post for post in posts if kwargs.get("featured") is not True or post.is_pinned]

    monkeypatch.setattr("app.modules.community.service.PostRepository", FakePostRepo)

    result = await CommunityService().async_list_posts(
        object(),  # type: ignore[arg-type]
        q="老王",
        scope="featured",
        sort="latest",
        user_id="u_1",
    )

    assert [post.post_id for post in result] == ["p_1"]
    assert calls[0]["featured"] is True


@pytest.mark.asyncio
async def test_list_posts_mine_requires_user_id() -> None:
    result = await CommunityService().async_list_posts(
        object(),  # type: ignore[arg-type]
        scope="mine",
        user_id=None,
    )

    assert result == []


@pytest.mark.asyncio
async def test_create_comment_updates_post_count(monkeypatch: pytest.MonkeyPatch) -> None:
    post = SimpleNamespace(id="p_1", comment_count=7)
    created_comments: list[object] = []

    class FakePostRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _post_id: str) -> object:
            return post

    class FakeCommentRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def create(self, comment: object) -> object:
            comment.like_count = 0
            comment.created_at = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
            created_comments.append(comment)
            return comment

    class FakeSession:
        async def commit(self) -> None:
            pass

    monkeypatch.setattr("app.modules.community.service.PostRepository", FakePostRepo)
    monkeypatch.setattr("app.modules.community.service.CommentRepository", FakeCommentRepo)

    comment = await CommunityService().async_create_comment(
        FakeSession(),  # type: ignore[arg-type]
        "u_1",
        CommunityCreateCommentRequest(post_id="p_1", content="@阿平 请看一下"),
    )

    assert post.comment_count == 8
    assert len(created_comments) == 1
    assert comment.author == "u_1"
    assert comment.content == "@阿平 请看一下"


@pytest.mark.asyncio
async def test_delete_comment_decrements_post_count(monkeypatch: pytest.MonkeyPatch) -> None:
    post = SimpleNamespace(id="p_1", comment_count=2)
    comment = SimpleNamespace(id="c_1", post_id="p_1")
    deleted: list[object] = []

    class FakePostRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _post_id: str) -> object:
            return post

    class FakeCommentRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _comment_id: str) -> object:
            return comment

        async def delete(self, instance: object) -> None:
            deleted.append(instance)

    class FakeSession:
        async def commit(self) -> None:
            pass

    monkeypatch.setattr("app.modules.community.service.PostRepository", FakePostRepo)
    monkeypatch.setattr("app.modules.community.service.CommentRepository", FakeCommentRepo)

    await CommunityService().async_delete_comment(
        FakeSession(),  # type: ignore[arg-type]
        "c_1",
        "u_1",
        CommunityModerationRequest(reason="违反社区规范"),
    )

    assert post.comment_count == 1
    assert deleted == [comment]


@pytest.mark.asyncio
async def test_set_featured_updates_post(monkeypatch: pytest.MonkeyPatch) -> None:
    post = SimpleNamespace(
        id="p_1",
        title="精华测试",
        author_id="u_1",
        author=SimpleNamespace(nickname="极睿智投员", membership_level="VIP1"),
        content="值得保留的投研讨论。",
        like_count=5,
        comment_count=0,
        view_count=10,
        category="discussion",
        is_pinned=False,
        created_at=datetime(2026, 5, 24, 11, 0, tzinfo=UTC),
    )

    class FakePostRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _post_id: str) -> object:
            return post

    class FakeCommentRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def list_by_post(self, _post_id: str) -> list[object]:
            return []

    class FakeSession:
        async def flush(self) -> None:
            pass

        async def commit(self) -> None:
            pass

    monkeypatch.setattr("app.modules.community.service.PostRepository", FakePostRepo)
    monkeypatch.setattr("app.modules.community.service.CommentRepository", FakeCommentRepo)

    detail = await CommunityService().async_set_featured(
        FakeSession(),  # type: ignore[arg-type]
        "p_1",
        "u_1",
        CommunityFeatureRequest(is_featured=True),
    )

    assert post.is_pinned is True
    assert detail.is_featured is True
