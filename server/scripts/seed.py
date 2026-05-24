"""
种子数据脚本 —— 向 cyber_invest 数据库插入演示数据

用法：
    cd server
    python -m scripts.seed

插入内容：
  - 1 个演示用户（13800138000）
  - 2 个 AI 研究员（小市值轮动、超短情绪）+ 策略配置 + 雇佣关系
  - 2 篇研究文档
  - 2 个社区帖子 + 若干评论
  - 每个研究员 1 个模拟交易账户（初始资金 100 万）

注意：脚本幂等 —— 先清空旧数据再重新插入。
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
DEMO_USER_NICKNAME = "极睿智投员"

# ── 研究员配置 ──
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
            "   - 营收增长率权重10% + 利润总额增长率权重35% + "
            "净利润增长率权重15% + 盈利增长率权重40%\n"
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
        # 演示持仓（小市值股票，5 只）
        "demo_positions": [
            {"symbol": "300223", "name": "北京君正",   "quantity": 500,  "cost_price": 85.20,  "current_price": 92.36},
            {"symbol": "002138", "name": "顺络电子",   "quantity": 800,  "cost_price": 24.50,  "current_price": 26.18},
            {"symbol": "300316", "name": "晶盛机电",   "quantity": 600,  "cost_price": 42.30,  "current_price": 41.85},
            {"symbol": "300433", "name": "蓝思科技",   "quantity": 1500, "cost_price": 18.90,  "current_price": 20.42},
            {"symbol": "002384", "name": "东山精密",   "quantity": 1000, "cost_price": 32.80,  "current_price": 35.21},
        ],
        # 演示成交记录（近 7 个交易日）
        "demo_trades": [
            {"symbol": "300223", "name": "北京君正", "side": "buy",  "quantity": 500,  "price": 85.20},
            {"symbol": "002138", "name": "顺络电子", "side": "buy",  "quantity": 800,  "price": 24.50},
            {"symbol": "300316", "name": "晶盛机电", "side": "buy",  "quantity": 600,  "price": 42.30},
            {"symbol": "300433", "name": "蓝思科技", "side": "buy",  "quantity": 1500, "price": 18.90},
            {"symbol": "002384", "name": "东山精密", "side": "buy",  "quantity": 1000, "price": 32.80},
            {"symbol": "600519", "name": "贵州茅台", "side": "sell", "quantity": 100,  "price": 1820.00},
            {"symbol": "000001", "name": "平安银行", "side": "sell", "quantity": 2000, "price": 13.45},
            {"symbol": "300750", "name": "宁德时代", "side": "buy",  "quantity": 200,  "price": 215.60},
        ],
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
                "events": [
                    "trade",
                    "stop_loss",
                    "limit_up_open",
                    "daily_summary",
                    "position_report",
                ],
            },
        },
    },
    {
        "name": "超短情绪",
        "title": "A股情绪超短高低切策略研究员",
        "style": "情绪周期+龙头接力+严格风控",
        "description": (
            "围绕A股超短情绪周期执行交易：盘后定预案，盘中认承接。"
            "用涨跌停、昨日涨停开盘溢价、连板高度、炸板率和题材联动判断情绪，"
            "按冰点、退潮、启动、发酵、高潮切换低吸、打板和半路模式。"
        ),
        "prompt": (
            "你是一名名叫「超短情绪」的A股情绪超短研究员。\n\n"
            "## 核心认知\n"
            "- 情绪定涨跌，位置定盈亏，龙头掌方向，预期差赚银子。\n"
            "- 盘后定预案，盘中做确认；不做无准备交易，不买不符合预期的标的。\n"
            "- 主板是基本盘，创业板/科创板只做主线第一个20cm领涨龙头。\n\n"
            "## 情绪打分\n"
            "总分100分，核心60分+辅助40分：涨停数量20分、跌停数量20分、"
            "昨日涨停开盘溢价20分、连板高度突破15分、炸板率15分、主线题材涨停数量10分。\n"
            "0-15为冰点，15-30为退潮，30-55为启动/弱修复，55-80为发酵，80-100为高潮。\n\n"
            "## 交易模式\n"
            "- 冰点：轻仓试错第一个突破近10日连板高度的破局龙。\n"
            "- 退潮：原则不开新仓，只处理持仓；只保本金，不追反弹。\n"
            "- 启动：破局龙首次突破只打板确认，次日-3%到+1%允许低吸。\n"
            "- 发酵：主线龙头打板，主线补涨9:40-10:30按5%-8%半路确认。\n"
            "- 高潮：不开新仓，只持有核心并按信号止盈。\n\n"
            "## 股票池和过滤\n"
            "- 主板为核心交易池；ST、北交所、上市1个月内新股排除。\n"
            "- 流通市值20亿-150亿，最佳30亿-100亿；日均成交额大于1亿。\n"
            "- 启动首板换手5%-25%，炸板超过2次不打，封单金额需不低于流通市值1%。\n\n"
            "## 风控纪律\n"
            "- 主板单票不超过20%，20cm单票不超过15%。\n"
            "- 固定止损5%，盈利10%先卖一半，盈利15%清仓；强势连板龙头可拿到不涨停再走。\n"
            "- 最长持仓3个交易日，连续3笔亏损或账户回撤超10%暂停交易。\n"
        ),
        "status": "active",
        "visibility": "public",
        "publish_status": "published",
        "level": "LV.3",
        "today_pnl": 0.0,
        "win_rate_30d": 0.0,
        "tags": ["情绪周期", "超短", "龙头", "高低切", "模拟盘"],
        "skills": [
            "skill_sentiment_cycle",
            "skill_limit_up_ladder",
            "skill_intraday_execution",
            "skill_risk_management",
        ],
        "knowledge_bases": ["kb_market_daily", "kb_limit_up_pool", "kb_hot_topics"],
        "mcp_servers": ["mcp_financial_news", "mcp_fund_flow"],
        "self_drive_tasks": [
            "15:10 盘后计算情绪分数并生成次日预案",
            "9:30-9:40 校验破局龙低吸条件",
            "9:40-10:30 校验主线补涨半路条件",
            "盘中只在打板确认、低吸窗口、半路窗口内触发交易",
            "14:00 检查涨停持仓是否开板",
            "15:05 输出情绪周期、持仓和风控复盘",
        ],
        "hire_count": 42,
        # 演示持仓（短线热点股，5 只）
        "demo_positions": [
            {"symbol": "688256", "name": "寒武纪-U", "quantity": 200,  "cost_price": 245.00, "current_price": 288.66},
            {"symbol": "688012", "name": "中微公司", "quantity": 300,  "cost_price": 182.50, "current_price": 198.42},
            {"symbol": "300059", "name": "东方财富", "quantity": 2000, "cost_price": 14.20,  "current_price": 15.86},
            {"symbol": "600519", "name": "贵州茅台", "quantity": 50,   "cost_price": 1780.0, "current_price": 1825.50},
            {"symbol": "002594", "name": "比亚迪",   "quantity": 400,  "cost_price": 238.00, "current_price": 250.93},
        ],
        # 演示成交记录（近 7 个交易日）
        "demo_trades": [
            {"symbol": "688256", "name": "寒武纪-U", "side": "buy",  "quantity": 200,  "price": 245.00},
            {"symbol": "688012", "name": "中微公司", "side": "buy",  "quantity": 300,  "price": 182.50},
            {"symbol": "300059", "name": "东方财富", "side": "buy",  "quantity": 2000, "price": 14.20},
            {"symbol": "002594", "name": "比亚迪",   "side": "buy",  "quantity": 400,  "price": 238.00},
            {"symbol": "600519", "name": "贵州茅台", "side": "buy",  "quantity": 50,   "price": 1780.0},
            {"symbol": "300750", "name": "宁德时代", "side": "sell", "quantity": 300,  "price": 218.40},
            {"symbol": "601318", "name": "中国平安", "side": "sell", "quantity": 1000, "price": 52.80},
            {"symbol": "300760", "name": "迈瑞医疗", "side": "buy",  "quantity": 150,  "price": 295.00},
        ],
        "strategy_config": {
            "strategy_type": "sentiment_ultrashort",
            "description": "A股情绪超短高低切/破局龙头策略 v1.0",
            "benchmark": "000001.XSHG",
            "max_single_position_ratio": 0.20,
            "max_20cm_position_ratio": 0.15,
            "max_daily_new_positions": 2,
            "max_daily_new_positions_strong": 3,
            "allow_20cm_front_runner": True,
            "emotion_score": {
                "total": 100,
                "core_weight": 60,
                "aux_weight": 40,
                "recent_height_days": 10,
                "stages": {
                    "ice": [0, 15],
                    "retreat": [15, 30],
                    "launch": [30, 55],
                    "fermentation": [55, 80],
                    "climax": [80, 100],
                },
            },
            "filters": {
                "exclude_st": True,
                "exclude_bj": True,
                "exclude_new_days": 30,
                "min_circulating_market_cap": 2000000000,
                "max_circulating_market_cap": 15000000000,
                "best_circulating_market_cap_min": 3000000000,
                "best_circulating_market_cap_max": 10000000000,
                "min_daily_amount": 100000000,
                "min_turnover_ratio": 5,
                "max_turnover_ratio": 25,
                "max_break_count": 2,
                "low_position_percentile_1y": 0.20,
            },
            "topic_confirmation": {
                "launch_min_limit_up": 3,
                "fermentation_min_limit_up": 5,
                "halfway_min_follow_limit_up": 2,
            },
            "low_absorb": {
                "start": "09:30",
                "end": "09:40",
                "min_open_pct": -3,
                "max_open_pct": 1,
                "observe_max_open_pct": 3,
                "observe_budget_multiplier": 0.5,
            },
            "halfway": {
                "start": "09:40",
                "end": "10:30",
                "min_change_pct": 5,
                "max_change_pct": 8,
            },
            "board_buy": {
                "prefer_morning_board": True,
                "latest_first_seal_time": "143000",
                "min_seal_amount_ratio": 0.01,
                "exclude_one_word_board": True,
                "exclude_t_board": True,
            },
            "position_limits": {
                "ice": 0.20,
                "retreat": 0.20,
                "launch": 0.40,
                "fermentation": 0.70,
                "climax": 0.30,
            },
            "risk_control": {
                "stop_loss": -0.05,
                "take_profit_half": 0.10,
                "take_profit_full": 0.15,
                "max_hold_days": 3,
                "pause_after_loss_count": 3,
                "pause_after_account_drawdown": 0.10,
            },
            "cost": {
                "open_tax": 0,
                "close_tax": 0.001,
                "open_commission": 0.0003,
                "close_commission": 0.0003,
                "min_commission": 5,
                "buy_slippage": 0.001,
                "sell_slippage": 0.001,
            },
            "data_scope": {
                "premium_scope": "main_board_only",
                "exclude_st": True,
                "exclude_new_days": 30,
                "exclude_bj": True,
                "exclude_20cm_from_premium": True,
                "topic_source": "eastmoney_industry_or_concept",
            },
            "notification": {
                "webhook_enabled": True,
                "server_sync_enabled": True,
                "events": [
                    "emotion_score",
                    "trade",
                    "stop_loss",
                    "take_profit",
                    "daily_summary",
                ],
            },
        },
    },
]

# 文档（绑定到小市值轮动研究员）
DOCUMENTS = [
    {
        "title": "小市值轮动策略日报：三因子选股与调仓执行",
        "summary": (
            "SG/MS/PEG三因子融合选出10只小市值标的，"
            "今日调仓卖出2只买入3只，附止损与涨停管理。"
        ),
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
        "content": (
            "用小市值轮动研究员跑了一个月模拟盘，SG+MS+PEG三因子选股效果很好，"
            "每日调仓虽然频繁但胜率不错。分享下我的配置。"
        ),
        "category": "strategy",
        "view_count": 1245,
        "comment_count": 47,
        "like_count": 203,
    },
    {
        "title": "新手请教：SG因子和PEG因子的区别是什么？",
        "content": (
            "刚注册不久，看到小市值轮动策略里有SG、MS、PEG三个因子，"
            "但不太理解它们各自选的是什么类型的股票。有大佬能解释下吗？"
        ),
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

    # ── 2. 创建研究员 + 雇佣关系 + 模拟交易账户（每个研究员 100 万初始资金）──
    from app.models.researcher import Researcher, ResearcherHire
    from app.models.trading import TradingAccount

    researcher_ids: list[str] = []
    for cfg in RESEARCHERS:
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
        acct_id = _id("acct_")
        acct = TradingAccount(
            id=acct_id,
            user_id=user_id,
            researcher_id=rid,
            total_asset=INITIAL_CASH,
            available_cash=INITIAL_CASH,
            holding_value=0.0,
            daily_pnl=0.0,
        )
        session.add(acct)

        # ── 演示持仓 + 交易记录（让前端有真实可视化数据）──
        from app.models.trading import Position, TradeRecord
        demo_positions = cfg.get("demo_positions", [])
        demo_trades = cfg.get("demo_trades", [])

        # 持仓
        holding_value = 0.0
        for pos in demo_positions:
            pnl = (pos["current_price"] - pos["cost_price"]) * pos["quantity"]
            session.add(Position(
                id=_id("pos_"),
                account_id=acct_id,
                symbol=pos["symbol"],
                name=pos["name"],
                quantity=pos["quantity"],
                cost_price=pos["cost_price"],
                current_price=pos["current_price"],
                pnl=pnl,
            ))
            holding_value += pos["current_price"] * pos["quantity"]

        # 交易记录（按时间倒序，最近 7 天）
        used_cash = sum(p["cost_price"] * p["quantity"] for p in demo_positions)
        for idx, tr in enumerate(demo_trades):
            session.add(TradeRecord(
                id=_id("tr_"),
                account_id=acct_id,
                symbol=tr["symbol"],
                name=tr["name"],
                side=tr["side"],
                quantity=tr["quantity"],
                price=tr["price"],
                commission=round(tr["price"] * tr["quantity"] * 0.00025, 2),
                created_at=_now(offset_hours=-24 * idx),
            ))

        # 更新账户聚合
        acct.holding_value = round(holding_value, 2)
        acct.available_cash = round(INITIAL_CASH - used_cash, 2)
        acct.total_asset = round(acct.available_cash + acct.holding_value, 2)
        # 今日盈亏 = 当前持仓盈亏（演示数据）
        acct.daily_pnl = round(sum(
            (p["current_price"] - p["cost_price"]) * p["quantity"]
            for p in demo_positions
        ), 2)

        print(f"  ✓ 研究员: {cfg['name']} ({rid}) · 模拟盘 资产 {acct.total_asset:.0f} 元 · 持仓 {len(demo_positions)} · 成交 {len(demo_trades)}")

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
    from app.models.community import Comment, Post

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

    # 先清空旧种子数据（幂等）—— 用 TRUNCATE ... CASCADE 解决 FK 依赖
    async with session_factory() as session:
        tables = [
            "trade_logs", "trade_records", "positions",
            "trading_account_snapshots", "trading_accounts",
            "pending_orders",
            "researcher_thesis_logs", "skill_run_logs", "daily_review_reports",
            "preopen_ai_digests",
            "minute_snapshots",
            "comments", "posts", "documents",
            "researcher_hires", "researchers",
            "battery_ledger", "membership_orders",
            "mcp_authorizations",
            "users",
        ]
        # 用 TRUNCATE CASCADE 一次性清干净所有依赖表（如果存在）
        existing = await session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(:tables)"
            ),
            {"tables": tables},
        )
        existing_tables = [row[0] for row in existing.fetchall()]
        if existing_tables:
            await session.execute(
                text(f"TRUNCATE TABLE {', '.join(existing_tables)} RESTART IDENTITY CASCADE")
            )
        await session.commit()
        print("✓ 已清空旧数据\n")

    # 插入种子数据
    async with session_factory() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
