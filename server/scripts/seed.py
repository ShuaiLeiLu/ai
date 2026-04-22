"""
种子数据脚本 —— 向 cyber_invest 数据库插入演示数据

用法：
    cd server
    python -m scripts.seed

插入内容：
  - 1 个演示用户（13800138000）
  - 1 个 AI 研究员（小市值轮动）+ 策略配置 + 雇佣关系
  - 2 篇研究文档
  - 2 个社区帖子 + 若干评论
  - 1 个模拟交易账户（初始资金 10 万）

注意：脚本幂等 —— 先清空旧数据再重新插入。
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import get_settings


# ── 工具函数 ──

def _id(prefix: str = "") -> str:
    """生成短 UUID"""
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _hash_pw(password: str) -> str:
    """密码哈希（与 auth service 一致）"""
    from app.core.security import hash_password
    return hash_password(password)


def _now(offset_hours: int = 0) -> datetime:
    return datetime.now(tz=UTC) + timedelta(hours=offset_hours)


# ── 模拟盘初始资金 ──
INITIAL_CASH = 1_000_000.0

# ── 种子数据定义 ──

DEMO_USER_ID = "u_demo"  # 固定 ID，与 security.py fallback 一致
DEMO_USER_PHONE = "13800138000"
DEMO_USER_PASSWORD = "test1234"
DEMO_USER_NICKNAME = "赛博投研员"

# ── 研究员配置（仅保留「小市值轮动」）──
RESEARCHERS = [
    {
        "name": "小市值轮动",
        "title": "A股小市值轮动策略专家",
        "style": "因子轮动+小市值+量化执行",
        "description": (
            "专注A股全市场小市值轮动策略。通过SG（5年营收增长率）、MS（复合成长因子）、"
            "PEG三大因子选股，取并集后按流通市值升序排列，持仓10只，每日调仓。"
            "内置10%硬止损、涨停打开自动卖出、近20日涨停股黑名单等风控规则。"
        ),
        "prompt": (
            "你是一名名叫「小市值轮动」的A股量化策略研究员，专注小市值股票的因子轮动策略。\n\n"
            "## 策略核心逻辑\n\n"
            "### 选股体系（三因子融合）\n"
            "1. **SG因子**：5年营业收入增长率（sales_growth）前10%，过滤EPS≤0，按流通市值升序\n"
            "2. **MS因子（复合成长因子）**：\n"
            "   - 营收增长率权重10% + 利润总额增长率权重35% + 净利润增长率权重15% + 盈利增长率权重40%\n"
            "   - 综合评分前10%，过滤EPS≤0，按流通市值升序\n"
            "3. **PEG因子**：PEG前20% → 换手率波动率前50%，按流通市值升序\n"
            "4. **合并**：三池取并集 → 按流通市值升序 → 取前10只\n\n"
            "### 过滤规则\n"
            "- 排除：ST/*ST/退市股、科创板(688)、次新股(上市<375天)、停牌股、涨停股、跌停股\n"
            "- 黑名单：近20个交易日内持仓过且期间涨停过的股票不再买入\n\n"
            "### 风控规则\n"
            "- **止损线**：持仓个股亏损达-10%立即卖出\n"
            "- **涨停管理**：昨日涨停股在14:00检查，若涨停打开则立即卖出，否则继续持有\n"
            "- **调仓频率**：每个交易日9:30执行调仓\n"
            "- **持仓数量**：目标持仓10只，等权分配资金\n\n"
            "### 交易成本\n"
            "- 买入佣金万三，卖出佣金万三 + 印花税千一，最低5元\n\n"
            "## 输出要求\n"
            "每次回复需包含以下结构：\n"
            "1. **今日选股池**：列出SG/MS/PEG三个子池及合并后的最终候选\n"
            "2. **调仓信号**：需卖出的持仓（及原因）、需买入的标的（及入选因子）\n"
            "3. **风控状态**：当前止损监控、涨停持仓状态、黑名单股票\n"
            "4. **策略指标**：最高连板数、封板率、持仓盈亏分布\n"
            "5. **风险提示**：明确标注小市值策略的流动性风险和极端回撤风险\n"
        ),
        "status": "active",
        "visibility": "public",
        "publish_status": "published",
        "level": "LV.2",
        "today_pnl": 0.0,
        "win_rate_30d": 0.0,
        "tags": ["小市值", "因子轮动", "量化", "每日调仓"],
        "skills": ["skill_smallcap_rotation", "skill_quant_factor", "skill_risk_management"],
        "knowledge_bases": ["kb_market_daily", "kb_factor_data", "kb_smallcap_data"],
        "mcp_servers": ["mcp_financial_news", "mcp_fund_flow"],
        "self_drive_tasks": [
            "9:05 执行选股（SG+MS+PEG三因子合并）并输出候选池",
            "9:30 执行每日调仓（卖出不在目标池 + 买入新目标）",
            "14:00 检查昨日涨停持仓是否打开，打开则卖出",
            "14:30 检查持仓止损（亏损超-10%自动卖出）",
            "15:01 输出收盘选股摘要与信号推送",
            "15:10 输出每日持仓明细报告",
        ],
        "hire_count": 67,
        "strategy_config": {
            "strategy_type": "smallcap_rotation",
            "description": "A股小市值三因子轮动策略（基于聚宽实盘验证）",
            "benchmark": "000300.XSHG",
            "stock_count": 10,
            "factors": [
                {
                    "name": "SG",
                    "description": "5年营业收入增长率（sales_growth）",
                    "top_pct": 0.10,
                    "pool_size": 5,
                    "require_positive_eps": True,
                    "sort_by": "circulating_market_cap",
                    "sort_ascending": True,
                },
                {
                    "name": "MS",
                    "description": "复合成长因子",
                    "sub_factors": [
                        {"name": "operating_revenue_growth_rate", "weight": 0.10},
                        {"name": "total_profit_growth_rate", "weight": 0.35},
                        {"name": "net_profit_growth_rate", "weight": 0.15},
                        {"name": "earnings_growth", "weight": 0.40},
                    ],
                    "top_pct": 0.10,
                    "pool_size": 5,
                    "require_positive_eps": True,
                    "sort_by": "circulating_market_cap",
                    "sort_ascending": True,
                },
                {
                    "name": "PEG",
                    "description": "PEG估值因子 + 换手率波动率过滤",
                    "peg_top_pct": 0.20,
                    "turnover_volatility_top_pct": 0.50,
                    "sort_by": "circulating_market_cap",
                    "sort_ascending": True,
                },
            ],
            "merge_method": "union",
            "final_sort": "circulating_market_cap_asc",
            "filters": {
                "exclude_st": True,
                "exclude_kcb": True,
                "exclude_new_days": 375,
                "exclude_paused": True,
                "exclude_limit_up": True,
                "exclude_limit_down": True,
            },
            "blacklist": {
                "enabled": True,
                "lookback_days": 20,
                "rule": "近N个交易日内持仓过且期间涨停过的股票不再买入",
            },
            "risk_control": {
                "stop_loss": -0.10,
                "limit_up_check_time": "14:00",
                "limit_up_action": "涨停打开则卖出，否则继续持有",
                "stop_loss_check_time": "14:30",
            },
            "schedule": {
                "prepare_time": "09:05",
                "trade_time": "09:30",
                "limit_check_time": "14:00",
                "stop_loss_time": "14:30",
                "summary_time": "15:01",
                "report_time": "15:10",
            },
            "cost": {
                "open_tax": 0,
                "close_tax": 0.001,
                "open_commission": 0.0003,
                "close_commission": 0.0003,
                "min_commission": 5,
            },
            "notification": {
                "webhook_enabled": True,
                "server_sync_enabled": True,
                "events": ["trade", "stop_loss", "limit_up_open", "daily_summary", "position_report"],
            },
        },
    },
]

# 文档（绑定到小市值轮动研究员）
DOCUMENTS = [
    {
        "title": "小市值轮动策略日报：三因子选股与调仓执行",
        "summary": "SG/MS/PEG三因子融合选出10只小市值标的，今日调仓卖出2只买入3只，附止损与涨停管理。",
        "content": "一、今日选股池（SG池/MS池/PEG池/合并）...\n二、调仓明细...\n三、风控状态...",
        "doc_type": "report",
        "view_count": 876,
        "comment_count": 22,
        "researcher_idx": 0,
    },
    {
        "title": "小市值轮动策略周度复盘：本周收益+3.2%",
        "summary": "本周策略累计收益+3.2%，最大回撤-1.8%，止损触发1次，涨停打开卖出2次。",
        "content": "一、周度业绩回顾...\n二、因子有效性评估...\n三、下周展望...",
        "doc_type": "strategy",
        "view_count": 1536,
        "comment_count": 45,
        "researcher_idx": 0,
    },
]

# 社区帖子
POSTS = [
    {
        "title": "小市值轮动策略实盘一个月，收益超15%！",
        "content": "用小市值轮动研究员跑了一个月模拟盘，SG+MS+PEG三因子选股效果很好，每日调仓虽然频繁但胜率不错。分享下我的配置。",
        "category": "strategy",
        "view_count": 1245,
        "comment_count": 47,
        "like_count": 203,
    },
    {
        "title": "新手请教：SG因子和PEG因子的区别是什么？",
        "content": "刚注册不久，看到小市值轮动策略里有SG、MS、PEG三个因子，但不太理解它们各自选的是什么类型的股票。有大佬能解释下吗？",
        "category": "question",
        "view_count": 234,
        "comment_count": 8,
        "like_count": 17,
    },
]

# 评论模板
COMMENTS = [
    "写得好，学习了！",
    "感谢分享，非常有帮助",
    "大佬带带我",
    "这个思路很有意思，回头试试",
    "请问数据源是从哪里获取的？",
    "回测结果很不错，实盘效果如何？",
    "同求配置方案",
    "技术分析和基本面结合才是王道",
]


async def seed(session: AsyncSession) -> None:
    """主种子函数"""

    # ── 1. 创建演示用户 ──
    from app.models.user import User
    existing = await session.execute(
        select(User).where(User.phone == DEMO_USER_PHONE)
    )
    user = existing.scalar_one_or_none()
    if user:
        user_id = user.id
        print(f"✓ 用户已存在: {user_id} ({user.nickname})")
    else:
        user_id = DEMO_USER_ID
        user = User(
            id=user_id,
            phone=DEMO_USER_PHONE,
            password_hash=_hash_pw(DEMO_USER_PASSWORD),
            nickname=DEMO_USER_NICKNAME,
            membership_level="VIP1",
            battery_balance=9999,
        )
        session.add(user)
        await session.flush()
        print(f"✓ 创建用户: {user_id} ({DEMO_USER_NICKNAME})")

    # ── 2. 创建研究员 + 雇佣关系 + 模拟交易账户（每个研究员 10 万初始资金）──
    from app.models.researcher import Researcher, ResearcherHire
    from app.models.trading import TradingAccount

    researcher_ids: list[str] = []
    for i, cfg in enumerate(RESEARCHERS):
        rid = _id("r_")
        researcher_ids.append(rid)

        r = Researcher(
            id=rid,
            owner_id=user_id,
            name=cfg["name"],
            title=cfg["title"],
            style=cfg["style"],
            description=cfg["description"],
            prompt=cfg["prompt"],
            status=cfg["status"],
            visibility=cfg["visibility"],
            publish_status=cfg["publish_status"],
            published_version="v1",
            version="v1",
            level=cfg["level"],
            today_pnl=cfg["today_pnl"],
            win_rate_30d=cfg["win_rate_30d"],
            tags=cfg["tags"],
            skills=cfg.get("skills", []),
            knowledge_bases=cfg.get("knowledge_bases", []),
            mcp_servers=cfg.get("mcp_servers", []),
            self_drive_tasks=cfg.get("self_drive_tasks", []),
            strategy_config=cfg.get("strategy_config"),
            is_system=True,  # 系统内定研究员，所有用户可见
            hire_count=cfg["hire_count"],
        )
        session.add(r)

        # 雇佣关系
        hire = ResearcherHire(
            id=_id("rh_"),
            user_id=user_id,
            researcher_id=rid,
            status="hired",
        )
        session.add(hire)

        # 模拟交易账户（每个研究员独立，初始 100 万）
        acct = TradingAccount(
            id=_id("acct_"),
            user_id=user_id,
            researcher_id=rid,
            total_asset=INITIAL_CASH,
            available_cash=INITIAL_CASH,
            holding_value=0.0,
            daily_pnl=0.0,
        )
        session.add(acct)

        print(f"  ✓ 研究员: {cfg['name']} ({rid}) + 模拟盘 {INITIAL_CASH:.0f}元")

    await session.flush()

    # ── 3. 创建文档 ──
    from app.models.document import Document

    for doc_cfg in DOCUMENTS:
        doc = Document(
            id=_id("doc_"),
            researcher_id=researcher_ids[doc_cfg["researcher_idx"]],
            author_id=user_id,
            title=doc_cfg["title"],
            summary=doc_cfg["summary"],
            content=doc_cfg["content"],
            doc_type=doc_cfg["doc_type"],
            view_count=doc_cfg["view_count"],
            comment_count=doc_cfg["comment_count"],
        )
        session.add(doc)
        print(f"  ✓ 文档: {doc_cfg['title'][:30]}...")

    await session.flush()

    # ── 4. 创建社区帖子 + 评论 ──
    from app.models.community import Post, Comment

    for j, post_cfg in enumerate(POSTS):
        post_id = _id("p_")
        post = Post(
            id=post_id,
            author_id=user_id,
            title=post_cfg["title"],
            content=post_cfg["content"],
            category=post_cfg["category"],
            view_count=post_cfg["view_count"],
            comment_count=post_cfg["comment_count"],
            like_count=post_cfg["like_count"],
        )
        session.add(post)

        for k in range(2):
            comment = Comment(
                id=_id("c_"),
                post_id=post_id,
                author_id=user_id,
                content=COMMENTS[(j * 2 + k) % len(COMMENTS)],
                like_count=(j + k) * 3,
            )
            session.add(comment)
        print(f"  ✓ 帖子: {post_cfg['title'][:25]}...")

    await session.flush()

    # ── 提交 ──
    await session.commit()
    print("\n🎉 种子数据插入完成!")
    print(f"   研究员: {len(RESEARCHERS)} 个")
    print(f"   模拟盘: {len(RESEARCHERS)} 个 × {INITIAL_CASH:.0f}元")
    print(f"   文档: {len(DOCUMENTS)} 篇")
    print(f"   帖子: {len(POSTS)} 篇")


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # 先清空旧种子数据（幂等）
    async with session_factory() as session:
        for table in [
            "trade_logs", "trade_records", "positions", "trading_accounts",
            "comments", "posts", "documents",
            "researcher_hires", "researchers",
            "battery_ledger", "membership_orders",
            "mcp_authorizations",
            "users",
        ]:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
        print("✓ 已清空旧数据\n")

    # 插入种子数据
    async with session_factory() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
