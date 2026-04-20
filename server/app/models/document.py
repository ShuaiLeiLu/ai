"""
文档模型 —— 研究员产出的研究文档

研究员通过 AI 生成或用户手动创建的研究报告/分析文档。
关联到研究员和用户，支持浏览数和评论数统计。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 文档类型：report / analysis / strategy / note
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, default="report")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    researcher = relationship("Researcher", back_populates="documents")
