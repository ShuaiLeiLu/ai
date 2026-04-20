"""
资讯领域服务 —— 真实数据版

数据来源：
  - 新闻列表：AKShare stock_news_main_cx（财新头条）
  - AI 摘要：基于涨停池统计数据自动生成
"""
from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from app.integrations.akshare.client import get_limit_up_pool, get_live_news_merged
from app.modules.news.schemas import NewsDigest, NewsItem, Sentiment

logger = logging.getLogger(__name__)

# 情绪关键词
_POSITIVE_KW = ("涨", "突破", "新高", "利好", "增长", "上调", "预增")
_NEGATIVE_KW = ("跌", "利空", "风险", "下降", "战争", "制裁", "预亏", "暴跌")


class NewsService:
    """资讯领域服务 —— 基于 AKShare 真实数据。"""

    def list_news(
        self,
        important_only: bool = False,
        sentiment: Sentiment | None = None,
    ) -> list[NewsItem]:
        """获取新闻列表 —— 同花顺 7x24 快讯 + 财联社快讯。"""
        live_news = get_live_news_merged()
        now = datetime.now(tz=UTC)

        items: list[NewsItem] = []
        for i, raw in enumerate(live_news):
            news_id = "n_" + hashlib.md5(raw.title.encode()).hexdigest()[:8]

            # 分类映射
            text = raw.title + raw.content
            if any(w in text for w in ("公告", "披露", "上交所", "深交所")):
                cat = "announcement"
            elif any(w in text for w in ("研报", "研究", "评级", "券商")):
                cat = "report"
            else:
                cat = "flash"

            # 情绪判断
            if any(w in text for w in _POSITIVE_KW):
                sent: Sentiment = "positive"
            elif any(w in text for w in _NEGATIVE_KW):
                sent = "negative"
            else:
                sent = "neutral"

            # 重要性
            importance = 2
            important_kw = ("涨停", "跌停", "暴涨", "暴跌", "重大", "央行", "降息", "加息", "战争", "制裁")
            count = sum(1 for kw in important_kw if kw in text)
            if count >= 2:
                importance = 5
            elif count >= 1:
                importance = 4
            elif any(w in text for w in ("突破", "新高", "预增")):
                importance = 3

            # 过滤
            if important_only and importance < 4:
                continue
            if sentiment and sent != sentiment:
                continue

            # 解析真实发布时间
            try:
                published_at = datetime.fromisoformat(raw.publish_time.replace(" ", "T"))
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=UTC)
            except (ValueError, AttributeError):
                published_at = now - timedelta(minutes=i * 5)

            items.append(NewsItem(
                news_id=news_id,
                title=raw.title,
                summary=raw.content[:200] if raw.content else raw.title,
                category=cat,
                sentiment=sent,
                source=raw.source,
                symbols=[],
                importance=importance,
                published_at=published_at,
            ))

        return items

    def latest_digest(self) -> NewsDigest:
        """AI 摘要 —— 基于涨停池真实数据生成。"""
        pool = get_limit_up_pool()
        now = datetime.now(tz=UTC)

        total_zt = len(pool)
        max_consecutive = max((s.consecutive for s in pool), default=0) if pool else 0

        # 行业分布
        industry_counter = Counter(s.industry for s in pool if s.industry)
        top_industries = industry_counter.most_common(3)
        industry_text = "、".join(f"{ind}" for ind, _ in top_industries) if top_industries else "暂无数据"

        if total_zt > 60:
            mood = "偏积极"
        elif total_zt < 30:
            mood = "偏谨慎"
        else:
            mood = "中性偏稳"

        return NewsDigest(
            digest_id=f"digest_{now.strftime('%Y%m%d')}",
            headline=f"24小时市场情绪：{mood}",
            key_points=[
                f"涨停 {total_zt} 家，最高 {max_consecutive} 连板，资金主攻 {industry_text}。",
                f"{'赚钱效应较好，可适当积极。' if total_zt > 50 else '赚钱效应一般，建议控制仓位。'}",
                "关注涨停梯队延续性与行业轮动节奏。",
            ],
            generated_at=now,
        )
