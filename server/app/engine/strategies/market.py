from __future__ import annotations

import logging

import pandas as pd

from app.integrations.akshare.client import call_akshare_api

logger = logging.getLogger(__name__)


def safe_float(val, default: float = 0.0) -> float:
    """Safely convert AKShare/东方财富 values to float."""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def fetch_realtime_quotes() -> list[dict]:
    """Fetch A-share realtime quotes through AKShare/东方财富."""
    try:
        df = call_akshare_api("stock_zh_a_spot_em")
    except Exception:
        logger.warning("[选股] AKShare(em) 获取行情失败，尝试新浪基础行情")
        return fetch_realtime_quotes_basic()

    quotes: list[dict] = []
    for _, row in df.iterrows():
        symbol = str(row.get("代码", "")).strip()
        if not symbol:
            continue

        price = safe_float(row.get("最新价"))
        if price <= 0:
            continue

        quotes.append({
            "symbol": symbol,
            "name": str(row.get("名称", "")),
            "price": price,
            "change_pct": safe_float(row.get("涨跌幅")),
            "amount": safe_float(row.get("成交额")),
            "open": safe_float(row.get("今开")),
            "prev_close": safe_float(row.get("昨收")),
            "volume": safe_float(row.get("成交量")),
            "circulating_market_cap": safe_float(row.get("流通市值")),
            "pe_ratio": safe_float(row.get("市盈率-动态")),
            "pb_ratio": safe_float(row.get("市净率")),
            "turnover_ratio": safe_float(row.get("换手率")),
            "volume_ratio": safe_float(row.get("量比")),
            "change_pct_60d": safe_float(row.get("60日涨跌幅")),
            "change_pct_ytd": safe_float(row.get("年初至今涨跌幅")),
        })
    logger.info("[选股] 获取 A 股行情(em) %d 条", len(quotes))
    return quotes


def fetch_realtime_quotes_basic() -> list[dict]:
    """Fallback A-share quote source with fewer factors but broad coverage."""
    try:
        df = call_akshare_api("stock_zh_a_spot")
    except Exception:
        logger.exception("[选股] AKShare(sina) 获取行情失败，回退空列表")
        return []

    quotes: list[dict] = []
    for _, row in df.iterrows():
        symbol = str(row.get("代码", "")).strip()
        if symbol.startswith(("sh", "sz", "bj")):
            symbol = symbol[2:]
        if not symbol:
            continue

        price = safe_float(row.get("最新价"))
        if price <= 0:
            continue

        quotes.append({
            "symbol": symbol,
            "name": str(row.get("名称", "")),
            "price": price,
            "change_pct": safe_float(row.get("涨跌幅")),
            "amount": safe_float(row.get("成交额")),
            "open": safe_float(row.get("今开")),
            "prev_close": safe_float(row.get("昨收")),
            "volume": safe_float(row.get("成交量")),
            "high": safe_float(row.get("最高")),
            "low": safe_float(row.get("最低")),
            "circulating_market_cap": 0.0,
            "pe_ratio": 0.0,
            "pb_ratio": 0.0,
            "turnover_ratio": 0.0,
            "volume_ratio": 0.0,
            "change_pct_60d": safe_float(row.get("涨跌幅")),
            "change_pct_ytd": safe_float(row.get("涨跌幅")),
            "_source": "sina_basic",
        })
    logger.info("[选股] 获取 A 股行情(sina) %d 条", len(quotes))
    return quotes
