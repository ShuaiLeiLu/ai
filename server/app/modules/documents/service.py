from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.modules.documents.schemas import DocumentDetail, DocumentSummary, DocumentType


class DocumentService:
    """研究文档领域服务。

    当前先用内存数据支撑页面联调，后续接入文档表与检索索引。
    """

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
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
            ),
        }

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

    def hot_documents(self, limit: int = 5) -> list[DocumentSummary]:
        sorted_items = sorted(
            self._documents.values(),
            key=lambda item: (item.view_count, item.like_count),
            reverse=True,
        )[:limit]
        return [DocumentSummary(**item.model_dump(include=set(DocumentSummary.model_fields.keys()))) for item in sorted_items]
