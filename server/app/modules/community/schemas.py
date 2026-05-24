from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import SchemaModel


class CommunityPost(SchemaModel):
    post_id: str
    title: str
    author: str
    author_type: str = "user"
    author_level: str | None = None
    excerpt: str
    likes: int
    comments: int
    views: int = 0
    category: str = "discussion"
    is_featured: bool = False
    is_vip_only: bool = False
    created_at: datetime


class CommunityComment(SchemaModel):
    comment_id: str
    author: str
    author_type: str = "user"
    content: str
    likes: int = 0
    created_at: datetime
    reply_to_id: str | None = None
    reply_to_author: str | None = None


class CommunityPostDetail(CommunityPost):
    content: str
    tags: list[str]
    comment_list: list[CommunityComment]


class CommunityCreatePostRequest(SchemaModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)


class CommunityCreateCommentRequest(SchemaModel):
    post_id: str
    content: str = Field(min_length=1, max_length=2000)
    reply_to_id: str | None = None


class CommunityModerationRequest(SchemaModel):
    reason: str = Field(default="违反社区规范", max_length=200)
    note: str | None = Field(default=None, max_length=500)


class CommunityFeatureRequest(SchemaModel):
    is_featured: bool


class CommunityMentionResearcher(SchemaModel):
    researcher_id: str
    name: str
    title: str | None = None
    avatar_url: str | None = None
    tags: list[str] = Field(default_factory=list)


class CommunityMentionConfig(SchemaModel):
    researchers: list[CommunityMentionResearcher]
