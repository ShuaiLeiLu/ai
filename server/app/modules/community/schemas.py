from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import SchemaModel


class CommunityPost(SchemaModel):
    post_id: str
    title: str
    author: str
    excerpt: str
    likes: int
    comments: int
    created_at: datetime


class CommunityComment(SchemaModel):
    comment_id: str
    author: str
    content: str
    created_at: datetime


class CommunityPostDetail(CommunityPost):
    content: str
    tags: list[str]
    comment_list: list[CommunityComment]


class CommunityCreatePostRequest(SchemaModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)
