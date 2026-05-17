from __future__ import annotations

import pandas as pd
from app.engine.strategies.sentiment_ultrashort import (
    _calculate_sentiment_score,
    _enrich_quotes_with_mainline_industries,
    _gen_sentiment_daily_summary,
    _is_main_board_normal_stock,
    _select_halfway_targets,
    _sort_breakout_candidates,
    SentimentScore,
)
from app.integrations.akshare.client import LimitUpStock


def _limit_stock(
    symbol: str,
    *,
    industry: str,
    first_seal_time: str,
    turnover: float = 12.0,
    break_count: int = 0,
    seal_amount: float = 100_000_000.0,
) -> LimitUpStock:
    return LimitUpStock(
        symbol=symbol,
        name=f"测试{symbol}",
        change_pct=10.0,
        price=10.0,
        amount=500_000_000.0,
        turnover_ratio=turnover,
        seal_amount=seal_amount,
        first_seal_time=first_seal_time,
        last_seal_time=first_seal_time,
        break_count=break_count,
        consecutive=3,
        industry=industry,
    )


def test_sentiment_score_uses_linear_segments() -> None:
    score = _calculate_sentiment_score(
        limit_up_count=45,
        limit_down_count=7,
        yesterday_premium_pct=1.0,
        height_breakthrough=2,
        break_rate=0.40,
        mainline_limit_up_count=5,
    )

    assert score.details["limit_up_count"] == 12.5
    assert score.details["limit_down_count"] == 13.0
    assert score.details["yesterday_premium"] == 12.5
    assert score.details["height_breakthrough"] == 10.0
    assert score.details["break_rate"] == 7.5
    assert score.details["mainline_limit_up_count"] == 5.0
    assert score.total == 60.5
    assert score.stage == "fermentation"


def test_main_board_filter_excludes_20cm_bj_and_st() -> None:
    assert _is_main_board_normal_stock("600000", "浦发银行") is True
    assert _is_main_board_normal_stock("002594", "比亚迪") is True
    assert _is_main_board_normal_stock("300750", "宁德时代") is False
    assert _is_main_board_normal_stock("688981", "中芯国际") is False
    assert _is_main_board_normal_stock("430047", "北交样例") is False
    assert _is_main_board_normal_stock("600001", "*ST样例") is False


def test_breakout_sort_prefers_topic_then_seal_time_then_quality() -> None:
    stocks = [
        _limit_stock("600001", industry="芯片", first_seal_time="10:00:00"),
        _limit_stock("600002", industry="新能源", first_seal_time="09:35:00"),
        _limit_stock("600003", industry="新能源", first_seal_time="09:45:00"),
        _limit_stock(
            "600004",
            industry="新能源",
            first_seal_time="09:35:00",
            break_count=1,
        ),
    ]
    counts = {"芯片": 1, "新能源": 3}
    quotes = {
        stock.symbol: {"circulating_market_cap": 5_000_000_000.0}
        for stock in stocks
    }

    ordered = _sort_breakout_candidates(stocks, counts, quotes)

    assert [stock.symbol for stock in ordered] == [
        "600002",
        "600004",
        "600003",
        "600001",
    ]


def test_halfway_targets_use_enriched_mainline_industry(monkeypatch) -> None:
    def fake_call_api(api_name: str, **kwargs):
        assert api_name == "stock_board_industry_cons_em"
        assert kwargs["symbol"] == "新能源"
        return pd.DataFrame([
            {"代码": "600010", "名称": "测试600010"},
            {"代码": "600011", "名称": "测试600011"},
        ])

    monkeypatch.setattr(
        "app.engine.strategies.sentiment_ultrashort.call_akshare_api",
        fake_call_api,
    )
    quotes = [
        {
            "symbol": "600010",
            "name": "测试600010",
            "price": 10.7,
            "prev_close": 10.0,
            "volume": 20_000,
            "change_pct": 7.0,
            "amount": 200_000_000,
            "turnover_ratio": 10.0,
            "circulating_market_cap": 5_000_000_000,
        }
    ]
    config = {
        "filters": {
            "min_circulating_market_cap": 2_000_000_000,
            "max_circulating_market_cap": 15_000_000_000,
            "min_daily_amount": 100_000_000,
            "min_turnover_ratio": 5,
            "max_turnover_ratio": 25,
        },
        "halfway": {"start": "09:40", "end": "10:30", "min_change_pct": 5, "max_change_pct": 8},
        "topic_confirmation": {"halfway_min_follow_limit_up": 2},
    }

    enriched = _enrich_quotes_with_mainline_industries(
        quotes,
        {"新能源": 2},
        config,
    )
    targets = _select_halfway_targets(
        all_quotes=enriched,
        today_limit_counts={"新能源": 2},
        config=config,
        now_shanghai=pd.Timestamp("2026-04-24 10:00:00").to_pydatetime(),
    )

    assert enriched[0]["industry"] == "新能源"
    assert [target["symbol"] for target in targets] == ["600010"]


def test_halfway_targets_records_rejected_candidates() -> None:
    audit: list[dict[str, str]] = []
    config = {
        "filters": {
            "min_circulating_market_cap": 2_000_000_000,
            "max_circulating_market_cap": 15_000_000_000,
            "min_daily_amount": 100_000_000,
            "min_turnover_ratio": 5,
            "max_turnover_ratio": 25,
        },
        "halfway": {"start": "09:40", "end": "10:30", "min_change_pct": 5, "max_change_pct": 8},
        "topic_confirmation": {"halfway_min_follow_limit_up": 2},
    }

    targets = _select_halfway_targets(
        all_quotes=[
            {
                "symbol": "600012",
                "name": "题材不足",
                "industry": "冷门",
                "change_pct": 6.2,
                "amount": 200_000_000,
                "turnover_ratio": 10,
                "circulating_market_cap": 5_000_000_000,
            }
        ],
        today_limit_counts={"冷门": 1},
        config=config,
        now_shanghai=pd.Timestamp("2026-04-24 10:00:00").to_pydatetime(),
        audit=audit,
    )

    assert targets == []
    assert audit[0]["stage"] == "半路"
    assert "题材确认不足" in audit[0]["reason"]


def test_sentiment_summary_lists_why_no_buy() -> None:
    content = _gen_sentiment_daily_summary(
        score=SentimentScore(total=42.0, stage="launch", details={}),
        meta={
            "limit_up_pool": [],
            "limit_down_pool": [],
            "yesterday_premium_pct": 0.0,
            "today_height": 0,
            "recent_height": 0,
            "break_rate": 0.0,
        },
        sell_count=0,
        buy_count=0,
        daily_pnl=0,
        total_asset=1_000_000,
        available_cash=1_000_000,
        hold_names=[],
        buy_audit=[
            {
                "stage": "半路",
                "symbol": "600012",
                "name": "题材不足",
                "reason": "题材确认不足：冷门 涨停少于 2 家",
            }
        ],
    )

    assert "## 为什么没买" in content
    assert "题材不足(600012)" in content
    assert "题材确认不足" in content
