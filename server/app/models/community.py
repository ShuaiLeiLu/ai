"""
社区模型 —— 帖子与评论

帖子支持分类（全部/讨论/策略/热门），
带浏览/评论/点赞计数，关联到作者。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Post(Base, TimestampMixin):
    """社区帖子"""
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 分类：discussion / strategy / question / share
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="discussion")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 是否置顶
    is_pinned: Mapped[bool] = mapped_column(default=False)

    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", lazy="selectin")


class Comment(Base, TimestampMixin):
    """帖子评论"""
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    post = relationship("Post", back_populates="comments")
