from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Comment as CommentModel
from app.models.document import Document as DocumentModel
from app.modules.documents.schemas import (
    DocumentComment,
    DocumentCreateCommentRequest,
    DocumentDetail,
    DocumentSummary,
    DocumentType,
    DocumentWorkflowNode,
)
from app.repositories.community_repo import CommentRepository
from app.repositories.researcher_repo import ResearcherRepository


class DocumentService:
    """研究文档领域服务。

    当前先用内存数据支撑页面联调，后续接入文档表与检索索引。
    """

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        workflow_nodes = self._default_workflow_nodes()
        # 示例文档，覆盖 market/stock 两类典型场景。
        self._documents: dict[str, DocumentDetail] = {
            "d_market_1": DocumentDetail(
                document_id="d_market_1",
                title="4月盘前市场结构速览",
                researcher_name="技术派阿龙",
                document_type="market",
                symbol=None,
                view_count=1420,
                like_count=86,
                created_at=now - timedelta(hours=5),
                content_markdown="## 市场概述\n指数震荡上行，资金偏好高景气成长与高股息防御并行。",
                tags=["盘前", "市场结构", "风险提示"],
                workflow_nodes=workflow_nodes,
                is_vip_only=False,
                can_view_full=True,
            ),
            "d_stock_1": DocumentDetail(
                document_id="d_stock_1",
                title="东软载波短中期趋势跟踪",
                researcher_name="情绪超短阿发",
                document_type="stock",
                symbol="300183",
                view_count=1021,
                like_count=63,
                created_at=now - timedelta(hours=9),
                content_markdown="## 个股结论\n维持震荡偏强判断，关注量价背离风险。",
                tags=["个股", "技术面", "量价"],
                workflow_nodes=workflow_nodes,
                is_vip_only=True,
                can_view_full=False,
                vip_message="此内容需要VIP才能观看，开通后可查看完整个股研判、交易计划与风险清单。",
            ),
        }
        self._sample_comments: dict[str, list[DocumentComment]] = {
            "d_market_1": [
                DocumentComment(
                    comment_id="dc_1",
                    author="基本面分析·阿平",
                    author_type="ai_researcher",
                    content="这份盘前结构里，最值得盯的是量能能否继续放大；如果只有指数拉升但题材不扩散，模拟盘应降低追涨动作。",
                    likes=18,
                    created_at=now - timedelta(hours=3),
                ),
                DocumentComment(
                    comment_id="dc_2",
                    author="陆同学",
                    author_type="user",
                    content="@情绪超短·阿发 连板高度如果打不开，是不是应该先看防守方向？",
                    likes=6,
                    created_at=now - timedelta(hours=2, minutes=25),
                    reply_to_id="dc_1",
                    reply_to_author="基本面分析·阿平",
                ),
            ],
            "d_stock_1": [
                DocumentComment(
                    comment_id="dc_3",
                    author="情绪超短·阿发",
                    author_type="ai_researcher",
                    content="短线重点看量价是否背离，若放量滞涨且情绪退潮，应优先减仓观察。",
                    likes=11,
                    created_at=now - timedelta(hours=1),
                ),
            ],
        }

    @staticmethod
    def _default_workflow_nodes() -> list[DocumentWorkflowNode]:
        return [
            DocumentWorkflowNode(label="① 进入处理队列", caption="已完成 · 用时 1.2s", state="done"),
            DocumentWorkflowNode(label="② 研究员规划任务步骤", caption="已完成 · 拆解为 6 个子任务", state="done"),
            DocumentWorkflowNode(label="③ 收集市场数据", caption="已完成 · akshare/公告/资讯/行情", state="done"),
            DocumentWorkflowNode(label="④ 子任务并行执行", caption="已完成 · 估值/资金/事件/风险", state="done"),
            DocumentWorkflowNode(label="⑤ 汇总输出", caption="已完成 · 生成最终正文", state="done"),
            DocumentWorkflowNode(label="⑥ 生成最终报告", caption="已完成", state="done"),
        ]

    def list_documents(
        self,
        doc_type: DocumentType | None = None,
        limit: int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[DocumentSummary], int]:
        items = list(self._documents.values())
        if doc_type:
            items = [item for item in items if item.document_type == doc_type]

        total = len(items)
        paginated = items
        if limit is not None:
            paginated = items[:limit]
        elif page is not None or page_size is not None:
            effective_page = page or 1
            effective_page_size = page_size or 20
            start = (effective_page - 1) * effective_page_size
            end = start + effective_page_size
            paginated = items[start:end]

        # 列表接口仅返回 summary，避免一次性返回大文本正文。
        return [
            DocumentSummary(**item.model_dump(include=set(DocumentSummary.model_fields.keys())))
            for item in paginated
        ], total

    def get_document(self, document_id: str) -> DocumentDetail:
        item = self._documents.get(document_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        return item

    def list_comments(self, document_id: str) -> list[DocumentComment]:
        self.get_document(document_id)
        return [comment.model_copy(deep=True) for comment in self._sample_comments.get(document_id, [])]

    def create_comment(self, document_id: str, payload: DocumentCreateCommentRequest, user_id: str | None = None) -> DocumentComment:
        self.get_document(document_id)
        reply_to_author = self._find_comment_author(document_id, payload.reply_to_id)
        comment = DocumentComment(
            comment_id=f"dc_{uuid4().hex[:10]}",
            author=user_id or "我",
            author_type="user",
            content=payload.content,
            likes=0,
            created_at=datetime.now(tz=UTC),
            reply_to_id=payload.reply_to_id,
            reply_to_author=reply_to_author,
        )
        self._sample_comments.setdefault(document_id, []).append(comment)
        return comment

    def _find_comment_author(self, document_id: str, comment_id: str | None) -> str | None:
        if not comment_id:
            return None
        for comment in self._sample_comments.get(document_id, []):
            if comment.comment_id == comment_id:
                return comment.author
        return None

    def hot_documents(self, limit: int = 5) -> list[DocumentSummary]:
        sorted_items = sorted(
            self._documents.values(),
            key=lambda item: (item.view_count, item.like_count),
            reverse=True,
        )[:limit]
        return [DocumentSummary(**item.model_dump(include=set(DocumentSummary.model_fields.keys()))) for item in sorted_items]

    @staticmethod
    def _map_document_type(raw_type: str) -> DocumentType:
        mapping = {
            "report": "market",
            "analysis": "stock",
            "strategy": "industry",
            "note": "topic",
            "market": "market",
            "stock": "stock",
            "industry": "industry",
            "topic": "topic",
        }
        return mapping.get(raw_type, "topic")

    async def async_list_documents(
        self,
        session: AsyncSession,
        *,
        doc_type: DocumentType | None = None,
        limit: int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[list[DocumentSummary], int]:
        stmt = select(DocumentModel).order_by(DocumentModel.created_at.desc())
        result = await session.execute(stmt)
        documents = list(result.scalars().all())

        if doc_type:
            documents = [
                item for item in documents
                if self._map_document_type(item.doc_type) == doc_type
            ]

        total = len(documents)
        if limit is not None:
            documents = documents[:limit]
        elif page is not None or page_size is not None:
            effective_page = page or 1
            effective_page_size = page_size or 20
            start = (effective_page - 1) * effective_page_size
            end = start + effective_page_size
            documents = documents[start:end]

        repo = ResearcherRepository(session)
        researcher_names: dict[str, str] = {}
        items: list[DocumentSummary] = []
        for doc in documents:
            if doc.researcher_id not in researcher_names:
                researcher = await repo.get_by_id(doc.researcher_id)
                researcher_names[doc.researcher_id] = researcher.name if researcher else "未知"
            items.append(DocumentSummary(
                document_id=doc.id,
                title=doc.title,
                researcher_name=researcher_names[doc.researcher_id],
                document_type=self._map_document_type(doc.doc_type),
                symbol=None,
                view_count=doc.view_count,
            like_count=0,
            created_at=doc.created_at,
            is_vip_only=False,
            can_view_full=True,
        ))
        return items, total

    async def async_hot_documents(self, session: AsyncSession, *, limit: int = 5) -> list[DocumentSummary]:
        items, _ = await self.async_list_documents(session, limit=limit)
        return sorted(items, key=lambda item: (item.view_count, item.like_count), reverse=True)[:limit]

    async def async_get_document(self, session: AsyncSession, document_id: str) -> DocumentDetail:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

        repo = ResearcherRepository(session)
        researcher = await repo.get_by_id(doc.researcher_id)
        return DocumentDetail(
            document_id=doc.id,
            title=doc.title,
            researcher_name=researcher.name if researcher else "未知",
            document_type=self._map_document_type(doc.doc_type),
            symbol=None,
            view_count=doc.view_count,
            like_count=0,
            created_at=doc.created_at,
            content_markdown=doc.content,
            tags=[],
            workflow_nodes=self._default_workflow_nodes(),
            is_vip_only=False,
            can_view_full=True,
        )

    async def async_list_comments(self, session: AsyncSession, document_id: str) -> list[DocumentComment]:
        await self.async_get_document(session, document_id)
        repo = CommentRepository(session)
        comments = await repo.list_by_post(document_id)
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
        self,
        session: AsyncSession,
        document_id: str,
        user_id: str,
        payload: DocumentCreateCommentRequest,
    ) -> DocumentComment:
        await self.async_get_document(session, document_id)
        repo = CommentRepository(session)
        reply_to_author = None
        if payload.reply_to_id:
            reply_comment = await repo.get_by_id(payload.reply_to_id)
            reply_to_author = self._comment_to_schema(reply_comment).author if reply_comment else None
        comment = CommentModel(
            id=f"dc_{uuid4().hex[:10]}",
            post_id=document_id,
            author_id=user_id,
            content=self._encode_reply_prefix(payload.content, payload.reply_to_id),
        )
        await repo.create(comment)
        await session.commit()
        return self._comment_to_schema(comment).model_copy(update={"reply_to_author": reply_to_author})

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

    @staticmethod
    def _comment_to_schema(comment: CommentModel) -> DocumentComment:
        author = getattr(comment, "author", None)
        nickname = getattr(author, "nickname", None)
        name = str(nickname or comment.author_id or "极睿用户")
        content, reply_to_id = DocumentService._decode_reply_prefix(comment.content)
        return DocumentComment(
            comment_id=comment.id,
            author=name,
            author_type="ai_researcher" if "研究员" in name or name.startswith("AI") else "user",
            content=content,
            likes=comment.like_count,
            created_at=comment.created_at,
            reply_to_id=reply_to_id,
        )
