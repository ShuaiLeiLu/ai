"""
AKShare 数据源统一封装

功能：
  - 封装 AKShare 各类接口调用（行情、新闻、涨停池、指数等）
  - 内置 TTL 内存缓存，避免短时间内重复请求外部接口
  - 提供 async 包装函数，在 asyncio 事件循环中通过 run_in_executor 调用
  - 异常安全：网络错误返回空结果，不影响上游服务

可用数据源（已验证网络连通）：
  - 同花顺 7x24 快讯：stock_info_global_ths → 20 条（标题+内容+时间+链接）★主力
  - 财联社快讯：stock_info_global_cls → 20 条（标题+内容+时间）★补充
  - 财经新闻（财新）：stock_news_main_cx → 100 条
  - 个股新闻（东方财富）：stock_news_em → 10 条/股
  - 涨停池（东方财富）：stock_zt_pool_em → 70+ 条
  - 跌停池（东方财富）：stock_zt_pool_dtgc_em
  - 强势股池（东方财富）：stock_zt_pool_strong_em → 200+ 条
  - 炸板池（东方财富）：stock_zt_pool_zbgc_em
  - A 股实时行情（新浪）：stock_zh_a_spot（仅交易时间可用）
  - A 股指数实时（新浪）：stock_zh_index_spot_sina（仅交易时间可用）
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
from threading import Lock
from typing import Any, TypeVar
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)

# 用于 run_in_executor 的线程池（AKShare 是同步阻塞调用）
_executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix="akshare")
T = TypeVar("T")
_AKSHARE_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_no_proxy_url_opener = build_opener(ProxyHandler({}))
_proxy_bypass_installed = False
_proxy_install_lock = Lock()
_external_data_lock = Lock()
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 10
_CN_TZ = ZoneInfo("Asia/Shanghai")


def _install_proxy_bypass() -> None:
    """一次性清除代理环境变量并 patch requests.Session，之后所有 AKShare 调用无需加锁。"""
    global _proxy_bypass_installed
    if _proxy_bypass_installed:
        return
    with _proxy_install_lock:
        if _proxy_bypass_installed:
            return
        for key in _AKSHARE_PROXY_ENV_KEYS:
            os.environ.pop(key, None)

        import requests
        _original_merge = requests.sessions.Session.merge_environment_settings
        _original_request = requests.sessions.Session.request

        def merge_without_proxy(
            self: Any,
            url: str,
            proxies: Any,
            stream: Any,
            verify: Any,
            cert: Any,
        ) -> dict[str, Any]:
            settings = _original_merge(self, url, proxies, stream, verify, cert)
            settings["proxies"] = {}
            return settings

        def request_with_default_timeout(self: Any, method: str, url: str, **kwargs: Any) -> Any:
            kwargs.setdefault("timeout", _DEFAULT_REQUEST_TIMEOUT_SECONDS)
            return _original_request(self, method, url, **kwargs)

        requests.sessions.Session.merge_environment_settings = merge_without_proxy  # type: ignore[assignment]
        requests.sessions.Session.request = request_with_default_timeout  # type: ignore[assignment]
        _proxy_bypass_installed = True
        logger.info("[AKShare] 代理绕过已安装，后续调用无需加锁")


# ════════════════════════════════════════════════════════════
# 异步包装：将同步 AKShare 调用放到线程池执行
# ════════════════════════════════════════════════════════════

async def run_sync(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在线程池中执行同步函数，返回异步结果。

    用法：result = await run_sync(get_limit_up_pool, trade_date)
    """
    loop = asyncio.get_running_loop()
    func = partial(fn, *args, **kwargs)
    return await loop.run_in_executor(_executor, func)


def call_akshare_api(api_name: str, /, *args: Any, **kwargs: Any) -> Any:
    """Call an AKShare API while serializing access to fragile upstream data sources."""
    _install_proxy_bypass()
    import akshare as ak

    api = getattr(ak, api_name)
    with _external_data_lock:
        return api(*args, **kwargs)


def _open_external_data_url(request: Request, *, timeout: float):
    _install_proxy_bypass()
    with _external_data_lock:
        return _no_proxy_url_opener.open(request, timeout=timeout)


# ════════════════════════════════════════════════════════════
# 内存 TTL 缓存
# ════════════════════════════════════════════════════════════

@dataclass
class _CacheEntry:
    """缓存条目：保存数据和过期时间。"""
    data: Any
    expires_at: float  # time.monotonic 时间戳


class TTLCache:
    """简易 TTL 内存缓存，线程安全性由 GIL 保证（单进程场景足够）。"""

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        """获取缓存值，过期返回 None。"""
        entry = self._store.get(key)
        if entry is None or time.monotonic() > entry.expires_at:
            return None
        return entry.data

    def set(self, key: str, data: Any, ttl_seconds: int) -> None:
        """写入缓存。"""
        self._store[key] = _CacheEntry(
            data=data,
            expires_at=time.monotonic() + ttl_seconds,
        )

    def invalidate(self, prefix: str = "") -> None:
        """清除指定前缀的缓存，空前缀则清除全部。"""
        if not prefix:
            self._store.clear()
        else:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]


# 全局缓存实例
_cache = TTLCache()
_stock_quotes_lock = Lock()
_stock_quote_locks_guard = Lock()
_stock_quote_locks: dict[str, Lock] = {}

# 缓存 TTL 配置（秒）
CACHE_TTL_REALTIME = 15       # 实时行情：15 秒
CACHE_TTL_INDEX = 15          # 指数行情：15 秒
CACHE_TTL_NEWS = 60           # 新闻资讯：60 秒
CACHE_TTL_INDUSTRY = 60       # 行业板块：60 秒
CACHE_TTL_LIMIT_UP = 30       # 涨停池/天梯：30 秒
CACHE_TTL_LIMIT_DOWN = 15     # 跌停/跌幅榜：15 秒
CACHE_TTL_STRONG = 15         # 强势股/涨幅榜：15 秒
CACHE_TTL_HISTORICAL_POOL = 24 * 3600  # 历史涨跌停池：1 天
CACHE_TTL_POOL_FAILURE = 60   # 外部池数据失败负缓存：1 分钟


# ════════════════════════════════════════════════════════════
# 数据返回类型（纯 dataclass，不依赖 pydantic）
# ════════════════════════════════════════════════════════════

@dataclass
class HistoryBar:
    """个股历史日 K 线一根。"""
    symbol: str          # 代码（不含交易所前缀）
    date: str            # 交易日 YYYY-MM-DD
    open: float          # 开盘价
    close: float         # 收盘价
    high: float          # 最高价
    low: float           # 最低价
    volume: float        # 成交量（股）
    amount: float        # 成交额（元）
    change_pct: float    # 涨跌幅（%）
    turnover: float      # 换手率（%）


@dataclass
class StockQuote:
    """个股实时行情快照。"""
    symbol: str          # 代码（如 "300308"，不含交易所前缀）
    name: str            # 名称
    price: float         # 最新价
    change: float        # 涨跌额
    change_pct: float    # 涨跌幅（%）
    open: float          # 今开
    high: float          # 最高
    low: float           # 最低
    prev_close: float    # 昨收
    volume: float        # 成交量（股）
    amount: float        # 成交额（元）
    timestamp: str       # 数据时间戳
    turnover_ratio: float = 0.0        # 换手率（%）
    volume_ratio: float = 0.0          # 量比
    industry: str = ""                 # 所属行业
    main_net_inflow: float = 0.0       # 主力净流入（元）
    main_net_inflow_pct: float = 0.0   # 主力净占比（%）


@dataclass
class IndexQuote:
    """指数实时行情快照。"""
    code: str            # 指数代码
    name: str            # 指数名称
    price: float         # 最新价
    change: float        # 涨跌额
    change_pct: float    # 涨跌幅（%）
    volume: float        # 成交量
    amount: float        # 成交额


@dataclass
class LiveNewsItem:
    """7x24 实时快讯条目（同花顺/财联社）。"""
    title: str           # 标题
    content: str         # 正文内容
    publish_time: str    # 发布时间（如 "2026-04-19 22:10:55"）
    url: str             # 原文链接
    source: str          # 来源（"同花顺" / "财联社"）


@dataclass
class NewsItem:
    """财经新闻条目（财新）。"""
    tag: str             # 分类标签
    summary: str         # 摘要内容
    url: str             # 原文链接
    source: str = ""     # 来源（如 "财新"）


@dataclass
class StockNewsItem:
    """个股新闻条目。"""
    symbol: str          # 关联股票代码
    title: str           # 新闻标题
    content: str         # 新闻内容
    publish_time: str    # 发布时间
    source: str          # 来源
    url: str             # 原文链接


@dataclass
class LimitUpStock:
    """涨停股信息。"""
    symbol: str          # 代码
    name: str            # 名称
    change_pct: float    # 涨跌幅（%）
    price: float         # 最新价
    amount: float        # 成交额
    turnover_ratio: float  # 换手率
    seal_amount: float   # 封板资金
    first_seal_time: str # 首次封板时间
    last_seal_time: str  # 最后封板时间
    break_count: int     # 炸板次数
    consecutive: int     # 连板数
    industry: str        # 所属行业


@dataclass
class LimitDownStock:
    """跌停股信息。"""
    symbol: str
    name: str
    change_pct: float
    price: float
    amount: float
    turnover_ratio: float


@dataclass
class StrongStock:
    """强势股信息。"""
    symbol: str
    name: str
    change_pct: float
    price: float
    amount: float
    turnover_ratio: float


@dataclass
class IndustryBoard:
    """同花顺行业板块涨跌概况。"""
    name: str             # 板块名称
    change_pct: float     # 涨跌幅（%）
    total_volume: float   # 总成交量（万手）
    total_amount: float   # 总成交额（亿元）
    net_inflow: float     # 净流入（亿元）
    rise_count: int       # 上涨家数
    fall_count: int       # 下跌家数
    leading_stock: str    # 领涨股名称
    leading_stock_pct: float  # 领涨股涨跌幅


# ════════════════════════════════════════════════════════════
# 核心获取函数
# ════════════════════════════════════════════════════════════

def _safe_float(val: Any, default: float = 0.0) -> float:
    """安全转换为 float。"""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """安全转换为 int。"""
    try:
        if pd.isna(val):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val: Any, default: str = "") -> str:
    """安全转换为 str。"""
    try:
        if pd.isna(val):
            return default
        return str(val).strip()
    except (ValueError, TypeError):
        return default


def _strip_exchange_prefix(code: str) -> str:
    """去掉新浪行情返回的交易所前缀（sh/sz）。"""
    if code.startswith(("sh", "sz", "SH", "SZ")):
        return code[2:]
    return code


def _stock_quote_cache_key(symbol: str) -> str:
    return f"stock_quote:{symbol}"


def _eastmoney_secid(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"1.{symbol}"
    return f"0.{symbol}"


def _tencent_realtime_symbol(symbol: str) -> str:
    return f"sh{symbol}" if symbol.startswith(("6", "9")) else f"sz{symbol}"


def _parse_tencent_timestamp(raw: str) -> str:
    if len(raw) >= 14 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]}:{raw[12:14]}"
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fetch_stock_quote_tencent(symbol: str) -> StockQuote | None:
    url = f"https://qt.gtimg.cn/q={_tencent_realtime_symbol(symbol)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    response = _open_external_data_url(request, timeout=8)
    text = response.read().decode("gbk", errors="ignore")
    if '="' not in text:
        return None
    payload = text.split('="', 1)[1].split('";', 1)[0]
    parts = payload.split("~")
    if len(parts) < 50:
        return None
    code = _safe_str(parts[2])
    price = _safe_float(parts[3])
    if not code or price <= 0:
        return None
    quote = StockQuote(
        symbol=code,
        name=_safe_str(parts[1], code),
        price=price,
        change=_safe_float(parts[31]),
        change_pct=_safe_float(parts[32]),
        open=_safe_float(parts[5]),
        high=_safe_float(parts[33]),
        low=_safe_float(parts[34]),
        prev_close=_safe_float(parts[4]),
        volume=_safe_float(parts[36]),
        amount=_safe_float(parts[37]) * 10000,
        timestamp=_parse_tencent_timestamp(_safe_str(parts[30])),
        turnover_ratio=_safe_float(parts[38]),
        volume_ratio=_safe_float(parts[49]),
    )
    _cache.set(_stock_quote_cache_key(code), quote, CACHE_TTL_REALTIME)
    return quote


def _fetch_stock_quotes_eastmoney(symbols: list[str]) -> dict[str, StockQuote]:
    if not symbols:
        return {}

    fields = "f2,f3,f4,f5,f6,f8,f10,f12,f14,f15,f16,f17,f18,f62,f100,f184"
    params = urlencode({
        "fltt": "2",
        "fields": fields,
        "secids": ",".join(_eastmoney_secid(symbol) for symbol in symbols),
    })
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?{params}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    response = _open_external_data_url(request, timeout=8)
    payload = json.loads(response.read().decode("utf-8"))

    quotes: dict[str, StockQuote] = {}
    for row in (payload.get("data") or {}).get("diff") or []:
        symbol = _safe_str(row.get("f12"))
        price = _safe_float(row.get("f2"))
        if not symbol or price <= 0:
            continue
        quote = StockQuote(
            symbol=symbol,
            name=_safe_str(row.get("f14"), symbol),
            price=price,
            change=_safe_float(row.get("f4")),
            change_pct=_safe_float(row.get("f3")),
            open=_safe_float(row.get("f17")),
            high=_safe_float(row.get("f15")),
            low=_safe_float(row.get("f16")),
            prev_close=_safe_float(row.get("f18")),
            volume=_safe_float(row.get("f5")),
            amount=_safe_float(row.get("f6")),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            turnover_ratio=_safe_float(row.get("f8")),
            volume_ratio=_safe_float(row.get("f10")),
            industry=_safe_str(row.get("f100")),
            main_net_inflow=_safe_float(row.get("f62")),
            main_net_inflow_pct=_safe_float(row.get("f184")),
        )
        _cache.set(_stock_quote_cache_key(symbol), quote, CACHE_TTL_REALTIME)
        quotes[symbol] = quote
    return quotes


def _get_stock_quote_lock(symbol: str) -> Lock:
    with _stock_quote_locks_guard:
        lock = _stock_quote_locks.get(symbol)
        if lock is None:
            lock = Lock()
            _stock_quote_locks[symbol] = lock
        return lock


def _find_quote_in_all_cache(symbol: str) -> StockQuote | None:
    cached = _cache.get("stock_quotes_all")
    if not isinstance(cached, list):
        return None
    for quote in cached:
        if isinstance(quote, StockQuote) and quote.symbol == symbol:
            return quote
    return None


def _peek_stock_quote(symbol: str) -> StockQuote | None:
    cached = _cache.get(_stock_quote_cache_key(symbol))
    if isinstance(cached, StockQuote):
        return cached
    return _find_quote_in_all_cache(symbol)


def _fetch_stock_quote(symbol: str) -> StockQuote | None:
    cached = _peek_stock_quote(symbol)
    if cached is not None:
        return cached

    quote_lock = _get_stock_quote_lock(symbol)
    with quote_lock:
        cached = _peek_stock_quote(symbol)
        if cached is not None:
            return cached

        try:
            df = call_akshare_api("stock_bid_ask_em", symbol=symbol)
        except Exception:
            logger.warning("AKShare 单股实时行情失败，尝试腾讯行情：%s", symbol)
            try:
                return _fetch_stock_quote_tencent(symbol)
            except Exception:
                logger.exception("获取个股实时行情失败：%s", symbol)
                return None

        if df.empty:
            return None

        item_map = {
            _safe_str(row.get("item")): row.get("value")
            for _, row in df.iterrows()
        }
        price = _safe_float(item_map.get("最新"))
        if price <= 0:
            return None

        quote = StockQuote(
            symbol=symbol,
            name=symbol,
            price=price,
            change=_safe_float(item_map.get("涨跌")),
            change_pct=_safe_float(item_map.get("涨幅")),
            open=_safe_float(item_map.get("今开")),
            high=_safe_float(item_map.get("最高")),
            low=_safe_float(item_map.get("最低")),
            prev_close=_safe_float(item_map.get("昨收")),
            volume=_safe_float(item_map.get("总手")),
            amount=_safe_float(item_map.get("金额")),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            turnover_ratio=_safe_float(item_map.get("换手")),
            volume_ratio=_safe_float(item_map.get("量比")),
        )
        _cache.set(_stock_quote_cache_key(symbol), quote, CACHE_TTL_REALTIME)
        return quote


def get_stock_quotes() -> list[StockQuote]:
    """获取 A 股全市场实时行情（新浪数据源）。

    返回约 5500 只股票的实时行情快照。
    数据缓存 15 秒。
    """
    cache_key = "stock_quotes_all"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    # 并发去重：同一时刻只允许一个线程去外部拉全市场行情。
    # 其他请求等待第一个请求完成后直接读缓存，避免并发时重复打满外部源。
    with _stock_quotes_lock:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            df = call_akshare_api("stock_zh_a_spot")
        except Exception:
            logger.exception("获取 A 股实时行情失败")
            return []

        quotes: list[StockQuote] = []
        for _, row in df.iterrows():
            symbol = _strip_exchange_prefix(_safe_str(row.get("代码")))
            if not symbol:
                continue
            quotes.append(StockQuote(
                symbol=symbol,
                name=_safe_str(row.get("名称")),
                price=_safe_float(row.get("最新价")),
                change=_safe_float(row.get("涨跌额")),
                change_pct=_safe_float(row.get("涨跌幅")),
                open=_safe_float(row.get("今开")),
                high=_safe_float(row.get("最高")),
                low=_safe_float(row.get("最低")),
                prev_close=_safe_float(row.get("昨收")),
                volume=_safe_float(row.get("成交量")),
                amount=_safe_float(row.get("成交额")),
                timestamp=_safe_str(row.get("时间戳")),
            ))

        _cache.set(cache_key, quotes, CACHE_TTL_REALTIME)
        logger.info("获取 A 股实时行情成功：%d 条", len(quotes))
        return quotes


def get_stock_quote_by_symbols(symbols: list[str]) -> dict[str, StockQuote]:
    """按股票代码批量获取行情，返回 {代码: 行情} 字典。

    交易模块只需要当前持仓的少量股票，不应该为此触发全市场行情拉取。
    这里使用东方财富批量接口，并对每只股票做 15 秒缓存。
    """
    normalized_symbols = sorted({symbol for symbol in symbols if symbol})
    quotes: dict[str, StockQuote] = {}
    missing_symbols: list[str] = []
    for symbol in normalized_symbols:
        quote = _peek_stock_quote(symbol)
        if quote is not None:
            quotes[symbol] = quote
        else:
            missing_symbols.append(symbol)

    if missing_symbols:
        try:
            quotes.update(_fetch_stock_quotes_eastmoney(missing_symbols))
        except Exception:
            logger.warning(
                "批量获取个股实时行情失败，逐只尝试备用源：%s",
                ",".join(missing_symbols),
            )
            for symbol in missing_symbols:
                quote = _fetch_stock_quote(symbol)
                if quote is not None:
                    quotes[symbol] = quote
    return quotes


def peek_stock_quote_by_symbols(symbols: list[str]) -> dict[str, StockQuote]:
    """只从本地缓存读取个股行情，不触发外部行情拉取。"""
    normalized_symbols = sorted({symbol for symbol in symbols if symbol})
    quotes: dict[str, StockQuote] = {}
    for symbol in normalized_symbols:
        quote = _peek_stock_quote(symbol)
        if quote is not None:
            quotes[symbol] = quote
    return quotes


def get_index_quotes() -> list[IndexQuote]:
    """获取 A 股主要指数实时行情（新浪数据源）。

    数据缓存 15 秒。
    """
    cache_key = "index_quotes"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_zh_index_spot_sina")
    except Exception:
        logger.exception("获取指数实时行情失败")
        return []

    quotes: list[IndexQuote] = []
    for _, row in df.iterrows():
        code = _safe_str(row.get("代码"))
        if not code:
            continue
        quotes.append(IndexQuote(
            code=code,
            name=_safe_str(row.get("名称")),
            price=_safe_float(row.get("最新价")),
            change=_safe_float(row.get("涨跌额")),
            change_pct=_safe_float(row.get("涨跌幅")),
            volume=_safe_float(row.get("成交量")),
            amount=_safe_float(row.get("成交额")),
        ))

    _cache.set(cache_key, quotes, CACHE_TTL_INDEX)
    logger.info("获取指数行情成功：%d 条", len(quotes))
    return quotes


def get_main_index_quotes() -> dict[str, IndexQuote]:
    """获取主要指数（上证、深证、创业板）行情。"""
    all_idx = get_index_quotes()
    # 新浪指数代码格式：sh000001（上证综指）、sz399001（深证成指）、sz399006（创业板指）
    target_map = {"sh000001": "上证综指", "sz399001": "深证成指", "sz399006": "创业板指"}
    return {code: q for q in all_idx for code in target_map if q.code == code}


def get_news_main() -> list[NewsItem]:
    """获取财经头条新闻（财新数据源）。

    返回约 100 条最新财经新闻。
    数据缓存 60 秒。
    """
    cache_key = "news_main"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_news_main_cx")
    except Exception:
        logger.exception("获取财经新闻失败")
        return []

    items: list[NewsItem] = []
    for _, row in df.iterrows():
        items.append(NewsItem(
            tag=_safe_str(row.get("tag")),
            summary=_safe_str(row.get("summary")),
            url=_safe_str(row.get("url")),
            source="财新",
        ))

    _cache.set(cache_key, items, CACHE_TTL_NEWS)
    logger.info("获取财经新闻成功：%d 条", len(items))
    return items


def get_stock_news(symbol: str, limit: int = 20) -> list[StockNewsItem]:
    """获取个股新闻（东方财富数据源）。

    数据缓存 60 秒（按个股缓存）。
    """
    cache_key = f"stock_news:{symbol}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached[:limit]

    try:
        df = call_akshare_api("stock_news_em", symbol=symbol)
    except Exception:
        logger.exception("获取个股新闻失败：%s", symbol)
        return []

    items: list[StockNewsItem] = []
    for _, row in df.iterrows():
        items.append(StockNewsItem(
            symbol=symbol,
            title=_safe_str(row.get("新闻标题")),
            content=_safe_str(row.get("新闻内容")),
            publish_time=_safe_str(row.get("发布时间")),
            source=_safe_str(row.get("文章来源")),
            url=_safe_str(row.get("新闻链接")),
        ))

    _cache.set(cache_key, items, CACHE_TTL_NEWS)
    logger.info("获取个股新闻成功：%s -> %d 条", symbol, len(items))
    return items[:limit]


def get_live_news_ths() -> list[LiveNewsItem]:
    """获取同花顺 7x24 全球快讯。

    数据质量高：有标题、正文、精确时间和原文链接。
    返回约 20 条最新快讯。
    数据缓存 60 秒。
    """
    cache_key = "live_news_ths"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_info_global_ths")
    except Exception:
        logger.exception("获取同花顺 7x24 快讯失败")
        return []

    items: list[LiveNewsItem] = []
    for _, row in df.iterrows():
        items.append(LiveNewsItem(
            title=_safe_str(row.get("标题")),
            content=_safe_str(row.get("内容")),
            publish_time=_safe_str(row.get("发布时间")),
            url=_safe_str(row.get("链接")),
            source="同花顺",
        ))

    _cache.set(cache_key, items, CACHE_TTL_NEWS)
    logger.info("获取同花顺 7x24 快讯成功：%d 条", len(items))
    return items


def get_live_news_cls() -> list[LiveNewsItem]:
    """获取财联社全球快讯。

    返回约 20 条最新快讯。
    数据缓存 60 秒。
    """
    cache_key = "live_news_cls"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_info_global_cls")
    except Exception:
        logger.exception("获取财联社快讯失败")
        return []

    items: list[LiveNewsItem] = []
    for _, row in df.iterrows():
        pub_date = _safe_str(row.get("发布日期"))
        pub_time = _safe_str(row.get("发布时间"))
        publish_time = f"{pub_date} {pub_time}" if pub_date and pub_time else (pub_date or pub_time)
        items.append(LiveNewsItem(
            title=_safe_str(row.get("标题")),
            content=_safe_str(row.get("内容")),
            publish_time=publish_time,
            url="",  # 财联社接口不含链接
            source="财联社",
        ))

    _cache.set(cache_key, items, CACHE_TTL_NEWS)
    logger.info("获取财联社快讯成功：%d 条", len(items))
    return items


def get_live_news_merged() -> list[LiveNewsItem]:
    """合并同花顺 + 财联社快讯，按时间倒序排列。

    同花顺为主力数据源，财联社为补充。
    合并后去重（按标题前 20 字去重）。
    """
    ths = get_live_news_ths()
    cls = get_live_news_cls()

    # 用标题前 20 字做简单去重
    seen: set[str] = set()
    merged: list[LiveNewsItem] = []
    for item in ths + cls:
        key = item.title[:20]
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    # 按发布时间倒序
    merged.sort(key=lambda x: x.publish_time, reverse=True)
    return merged


def get_industry_boards() -> list[IndustryBoard]:
    """获取同花顺行业板块涨跌概况。

    返回约 90 个行业板块的实时涨跌数据。
    数据缓存 60 秒。
    """
    cache_key = "industry_boards"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_board_industry_summary_ths")
    except Exception:
        logger.exception("获取行业板块涨跌失败")
        return []

    items: list[IndustryBoard] = []
    for _, row in df.iterrows():
        items.append(IndustryBoard(
            name=_safe_str(row.get("板块")),
            change_pct=_safe_float(row.get("涨跌幅")),
            total_volume=_safe_float(row.get("总成交量")),
            total_amount=_safe_float(row.get("总成交额")),
            net_inflow=_safe_float(row.get("净流入")),
            rise_count=_safe_int(row.get("上涨家数")),
            fall_count=_safe_int(row.get("下跌家数")),
            leading_stock=_safe_str(row.get("领涨股")),
            leading_stock_pct=_safe_float(row.get("领涨股-涨跌幅")),
        ))

    _cache.set(cache_key, items, CACHE_TTL_INDUSTRY)
    logger.info("获取行业板块成功：%d 个板块", len(items))
    return items


def get_limit_up_pool(trade_date: date | None = None) -> list[LimitUpStock]:
    """获取涨停股池（东方财富数据源）。

    数据缓存 30 秒。
    """
    latest_trade_date = _latest_trade_date()
    target_date = trade_date or latest_trade_date
    dt_str = target_date.strftime("%Y%m%d")
    cache_key = f"limit_up:{dt_str}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_zt_pool_em", date=dt_str)
    except Exception:
        logger.exception("获取涨停池失败：%s", dt_str)
        _cache.set(cache_key, [], CACHE_TTL_POOL_FAILURE)
        return []

    items: list[LimitUpStock] = []
    for _, row in df.iterrows():
        items.append(LimitUpStock(
            symbol=_safe_str(row.get("代码")),
            name=_safe_str(row.get("名称")),
            change_pct=_safe_float(row.get("涨跌幅")),
            price=_safe_float(row.get("最新价")),
            amount=_safe_float(row.get("成交额")),
            turnover_ratio=_safe_float(row.get("换手率")),
            seal_amount=_safe_float(row.get("封板资金")),
            first_seal_time=_safe_str(row.get("首次封板时间")),
            last_seal_time=_safe_str(row.get("最后封板时间")),
            break_count=_safe_int(row.get("炸板次数")),
            consecutive=_safe_int(row.get("连板数")),
            industry=_safe_str(row.get("所属行业")),
        ))

    ttl = CACHE_TTL_LIMIT_UP if target_date >= latest_trade_date else CACHE_TTL_HISTORICAL_POOL
    _cache.set(cache_key, items, ttl)
    logger.info("获取涨停池成功：%s -> %d 条", dt_str, len(items))
    return items


def get_limit_down_pool(trade_date: date | None = None) -> list[LimitDownStock]:
    """获取跌停股池（东方财富数据源）。"""
    latest_trade_date = _latest_trade_date()
    target_date = trade_date or latest_trade_date
    dt_str = target_date.strftime("%Y%m%d")
    cache_key = f"limit_down:{dt_str}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_zt_pool_dtgc_em", date=dt_str)
    except Exception:
        logger.exception("获取跌停池失败：%s", dt_str)
        _cache.set(cache_key, [], CACHE_TTL_POOL_FAILURE)
        return []

    items: list[LimitDownStock] = []
    for _, row in df.iterrows():
        items.append(LimitDownStock(
            symbol=_safe_str(row.get("代码")),
            name=_safe_str(row.get("名称")),
            change_pct=_safe_float(row.get("涨跌幅")),
            price=_safe_float(row.get("最新价")),
            amount=_safe_float(row.get("成交额")),
            turnover_ratio=_safe_float(row.get("换手率")),
        ))

    ttl = CACHE_TTL_LIMIT_DOWN if target_date >= latest_trade_date else CACHE_TTL_HISTORICAL_POOL
    _cache.set(cache_key, items, ttl)
    return items


def get_strong_pool(trade_date: date | None = None) -> list[StrongStock]:
    """获取强势股池（东方财富数据源）。"""
    dt_str = (trade_date or _latest_trade_date()).strftime("%Y%m%d")
    cache_key = f"strong:{dt_str}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_zt_pool_strong_em", date=dt_str)
    except Exception:
        logger.exception("获取强势股池失败：%s", dt_str)
        return []

    items: list[StrongStock] = []
    for _, row in df.iterrows():
        items.append(StrongStock(
            symbol=_safe_str(row.get("代码")),
            name=_safe_str(row.get("名称")),
            change_pct=_safe_float(row.get("涨跌幅")),
            price=_safe_float(row.get("最新价")),
            amount=_safe_float(row.get("成交额")),
            turnover_ratio=_safe_float(row.get("换手率")),
        ))

    _cache.set(cache_key, items, CACHE_TTL_STRONG)
    return items


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def _latest_trade_date() -> date:
    """推算最近一个交易日（简单按工作日回推）。

    注意：不考虑法定假日，仅排除周末。
    实际生产环境应接入交易日历服务。
    """
    from datetime import timedelta
    now = datetime.now(tz=_CN_TZ)
    cursor = now.date()
    # 如果是周末或当天集合竞价尚未开始（时间 < 09:15），回退。
    # 盘前快照刷新从 09:15 启动，交易日判断要和刷新窗口保持一致。
    if now.hour < 9 or (now.hour == 9 and now.minute < 15):
        cursor -= timedelta(days=1)
    while cursor.weekday() >= 5:  # 周六=5, 周日=6
        cursor -= timedelta(days=1)
    return cursor


def get_market_data_trade_date() -> date:
    """Return the trade date used by intraday market-pool APIs."""
    return _latest_trade_date()


def invalidate_cache(prefix: str = "") -> None:
    """手动清除缓存。可选按前缀清除。"""
    _cache.invalidate(prefix)


# ════════════════════════════════════════════════════════════
# 历史日 K 线（用于回放 / backfill）
# ════════════════════════════════════════════════════════════

CACHE_TTL_HISTORY = 24 * 3600   # 历史 K 线缓存 24 小时


def get_stock_history(
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    adjust: str = "qfq",
) -> list[HistoryBar]:
    """获取个股历史日 K 线（前复权，AKShare ak.stock_zh_a_hist）。

    参数：
        symbol: 6 位代码（如 "600519"），不含交易所前缀
        start_date / end_date: 闭区间日期
        adjust: "qfq" 前复权 / "hfq" 后复权 / "" 不复权

    返回：
        按交易日升序排列的 HistoryBar 列表；停牌或区间无数据时返回 []。

    说明：
        AKShare 的 stock_zh_a_hist 返回列：
        日期 / 股票代码 / 开盘 / 收盘 / 最高 / 最低 / 成交量 / 成交额 /
        振幅 / 涨跌幅 / 涨跌额 / 换手率
    """
    if not symbol:
        return []

    cache_key = f"hist:{symbol}:{start_date.isoformat()}:{end_date.isoformat()}:{adjust}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api(
            "stock_zh_a_hist",
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust=adjust,
        )
    except Exception as exc:
        logger.warning(
            "AKShare 历史日 K 失败，尝试腾讯行情：%s %s~%s (%s)",
            symbol,
            start_date,
            end_date,
            exc,
        )
        bars = _get_stock_history_from_tencent(symbol, start_date, end_date, adjust=adjust)
        _cache.set(cache_key, bars, CACHE_TTL_HISTORY)
        return bars

    bars: list[HistoryBar] = []
    if df is None or df.empty:
        _cache.set(cache_key, bars, CACHE_TTL_HISTORY)
        return bars

    for _, row in df.iterrows():
        raw_date = row.get("日期")
        date_str = ""
        if isinstance(raw_date, str):
            date_str = raw_date[:10]
        else:
            try:
                date_str = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
            except Exception:
                date_str = str(raw_date)[:10]
        bars.append(HistoryBar(
            symbol=symbol,
            date=date_str,
            open=_safe_float(row.get("开盘")),
            close=_safe_float(row.get("收盘")),
            high=_safe_float(row.get("最高")),
            low=_safe_float(row.get("最低")),
            volume=_safe_float(row.get("成交量")),
            amount=_safe_float(row.get("成交额")),
            change_pct=_safe_float(row.get("涨跌幅")),
            turnover=_safe_float(row.get("换手率")),
        ))

    _cache.set(cache_key, bars, CACHE_TTL_HISTORY)
    return bars


def _tencent_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _get_stock_history_from_tencent(
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    adjust: str = "qfq",
) -> list[HistoryBar]:
    """腾讯行情历史日 K fallback。

    返回字段足以支撑模拟盘每日账户快照：日期、开盘、收盘、最高、最低、成交量。
    """
    code = _tencent_symbol(symbol)
    series_key = "qfqday" if adjust == "qfq" else "hfqday" if adjust == "hfq" else "day"
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
        f"param={code},day,{start_date.isoformat()},{end_date.isoformat()},800,{adjust or 'qfq'}"
    )

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _open_external_data_url(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        logger.exception("腾讯历史日 K 失败：%s %s~%s", symbol, start_date, end_date)
        return []

    rows = (
        payload.get("data", {})
        .get(code, {})
        .get(series_key)
        or payload.get("data", {}).get(code, {}).get("day")
        or []
    )
    bars: list[HistoryBar] = []
    for row in rows:
        if len(row) < 6:
            continue
        try:
            trade_date = str(row[0])[:10]
            bars.append(
                HistoryBar(
                    symbol=symbol,
                    date=trade_date,
                    open=_safe_float(row[1]),
                    close=_safe_float(row[2]),
                    high=_safe_float(row[3]),
                    low=_safe_float(row[4]),
                    volume=_safe_float(row[5]),
                    amount=0.0,
                    change_pct=0.0,
                    turnover=0.0,
                )
            )
        except Exception:
            continue
    return bars


def get_stock_history_batch(
    symbols: list[str],
    start_date: date,
    end_date: date,
    *,
    adjust: str = "qfq",
) -> dict[str, list[HistoryBar]]:
    """批量获取多只股票的历史日 K 线（串行调用 + 单股缓存）。"""
    result: dict[str, list[HistoryBar]] = {}
    for symbol in sorted({s for s in symbols if s}):
        result[symbol] = get_stock_history(symbol, start_date, end_date, adjust=adjust)
    return result


def list_recent_trade_dates(end_date: date, count: int) -> list[date]:
    """返回截止 end_date（含）的最近 count 个 A 股交易日（升序）。

    实现：用上证指数 ak.stock_zh_index_daily(symbol="sh000001") 在最近 60 天内取
    实际交易日；不足时回退为简单工作日排除。
    """
    from datetime import timedelta

    cache_key = f"trade_dates:{end_date.isoformat()}:{count}"
    cached = _cache.get(cache_key)
    if isinstance(cached, list):
        return cached

    lookback_start = end_date - timedelta(days=count * 2 + 14)
    dates: list[date] = []
    try:
        df = call_akshare_api(
            "stock_zh_index_daily",
            symbol="sh000001",
        )
        if df is not None and not df.empty:
            for raw in df["date"].tolist():
                try:
                    d = pd.to_datetime(raw).date()
                except Exception:
                    continue
                if lookback_start <= d <= end_date:
                    dates.append(d)
            dates.sort()
    except Exception:
        logger.exception("获取上证交易日失败，回退为工作日推算")

    if not dates:
        cursor = end_date
        while len(dates) < count:
            if cursor.weekday() < 5:
                dates.append(cursor)
            cursor -= timedelta(days=1)
        dates.sort()

    trimmed = dates[-count:] if len(dates) >= count else dates
    _cache.set(cache_key, trimmed, CACHE_TTL_HISTORY)
    return trimmed


# ════════════════════════════════════════════════════════════
# Skill 框架新增数据源(2026-05-22)
# 用途:为盘前/盘后 AI skill 提供外盘、资金面、龙虎榜、技术面、催化日历等数据
# ════════════════════════════════════════════════════════════

CACHE_TTL_OVERSEAS = 300        # 隔夜外盘:5 分钟(开盘后基本不变)
CACHE_TTL_FUTURES = 60          # 期指夜盘:1 分钟
CACHE_TTL_HSGT = 300            # 北向资金:5 分钟
CACHE_TTL_LHB = 3600            # 龙虎榜:1 小时
CACHE_TTL_SECTOR_FLOW = 60      # 行业资金流:1 分钟
CACHE_TTL_CALENDAR = 3600       # 财报/解禁/新股日历:1 小时
CACHE_TTL_MARGIN = 3600         # 融资融券余额:1 小时


@dataclass
class OverseasIndex:
    """隔夜外盘指数快照。"""
    name: str
    symbol: str
    price: float
    change_pct: float


@dataclass
class FuturesQuote:
    """股指期货快照。"""
    symbol: str           # IF2506 等
    name: str             # IF主力 等
    price: float
    change_pct: float
    volume: float
    open_interest: float


@dataclass
class NorthboundFlow:
    """北向资金当日净流入。"""
    trade_date: str
    sh_net_amount: float  # 沪股通净流入(亿元)
    sz_net_amount: float  # 深股通净流入(亿元)
    total_net: float


@dataclass
class LonghubangItem:
    """龙虎榜个股席位明细。"""
    symbol: str
    name: str
    change_pct: float
    net_amount: float     # 买入-卖出(元)
    reason: str           # 上榜原因
    institution_buy: float
    institution_sell: float


@dataclass
class IndexDailyBar:
    """指数日线 K。"""
    trade_date: str
    open: float
    close: float
    high: float
    low: float
    volume: float


@dataclass
class SectorFlow:
    """行业板块当日资金流。"""
    name: str
    change_pct: float
    main_net_inflow: float   # 主力净流入(元)
    main_net_pct: float      # 主力净占比(%)
    leading_stock: str


@dataclass
class CatalystEvent:
    """今日财报/解禁/新股等事件。"""
    event_type: str       # earnings / unlock / ipo / policy
    symbol: str
    name: str
    trade_date: str
    detail: str           # 文本说明


@dataclass
class MarginBalance:
    """两融余额。"""
    trade_date: str
    financing_balance: float    # 融资余额(亿元)
    securities_balance: float   # 融券余额(亿元)
    total_balance: float


# ── 1. 隔夜外盘(美股三大指数 + 主要科技股)──
def get_overseas_indices() -> list[OverseasIndex]:
    """获取隔夜美股关键指数 + 科技股。"""
    cache_key = "overseas_indices"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    targets = [
        ("道琼斯", ".DJI"),
        ("纳斯达克", ".IXIC"),
        ("标普500", ".INX"),
        ("费城半导体", ".SOX"),
        ("纳指100", ".NDX"),
    ]
    items: list[OverseasIndex] = []
    try:
        df = call_akshare_api("index_us_stock_sina", symbol=".DJI")
        # 兜底:不同 akshare 版本接口可能差异,失败时尝试其他通用接口
        if df is None or df.empty:
            df = call_akshare_api("stock_us_spot_em")
            if df is not None and not df.empty:
                for _, row in df.head(50).iterrows():
                    name = _safe_str(row.get("名称") or row.get("简称"))
                    if not any(t[0] in name for t in targets):
                        continue
                    items.append(OverseasIndex(
                        name=name,
                        symbol=_safe_str(row.get("代码")),
                        price=_safe_float(row.get("最新价")),
                        change_pct=_safe_float(row.get("涨跌幅")),
                    ))
    except Exception:
        logger.exception("获取隔夜外盘失败")

    _cache.set(cache_key, items, CACHE_TTL_OVERSEAS)
    return items


# ── 2. 股指期货夜盘(IF / IH / IC 主力)──
def get_futures_night_quotes() -> list[FuturesQuote]:
    """获取沪深 IF/IH/IC 期指主力夜盘行情。"""
    cache_key = "futures_night_quotes"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[FuturesQuote] = []
    targets = ["IF", "IH", "IC", "IM"]
    try:
        df = call_akshare_api("futures_zh_realtime", symbol="股指期货")
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                symbol = _safe_str(row.get("symbol") or row.get("合约"))
                if not any(symbol.startswith(t) for t in targets):
                    continue
                items.append(FuturesQuote(
                    symbol=symbol,
                    name=_safe_str(row.get("name") or symbol),
                    price=_safe_float(row.get("price") or row.get("最新价")),
                    change_pct=_safe_float(row.get("change_pct") or row.get("涨跌幅")),
                    volume=_safe_float(row.get("volume") or row.get("成交量")),
                    open_interest=_safe_float(row.get("open_interest") or row.get("持仓量")),
                ))
    except Exception:
        logger.exception("获取期指夜盘失败")

    _cache.set(cache_key, items, CACHE_TTL_FUTURES)
    return items


# ── 3. 北向资金当日净流入 ──
def get_northbound_flow() -> NorthboundFlow | None:
    """获取北向资金最近一日净流入。"""
    cache_key = "northbound_flow"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = call_akshare_api("stock_hsgt_north_net_flow_in_em", symbol="北上")
        if df is None or df.empty:
            return None
        row = df.iloc[-1]
        flow = NorthboundFlow(
            trade_date=_safe_str(row.get("date") or row.get("日期")),
            sh_net_amount=_safe_float(row.get("sh") or row.get("沪股通")) / 100000000,
            sz_net_amount=_safe_float(row.get("sz") or row.get("深股通")) / 100000000,
            total_net=_safe_float(row.get("value") or row.get("北上资金")) / 100000000,
        )
        _cache.set(cache_key, flow, CACHE_TTL_HSGT)
        return flow
    except Exception:
        logger.exception("获取北向资金失败")
        return None


# ── 4. 龙虎榜(指定日期) ──
def get_longhubang(trade_date: date | None = None) -> list[LonghubangItem]:
    """获取龙虎榜个股明细。默认最近一个交易日。"""
    target_date = trade_date or _latest_trade_date()
    cache_key = f"longhubang:{target_date.isoformat()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[LonghubangItem] = []
    try:
        df = call_akshare_api(
            "stock_lhb_detail_em",
            start_date=target_date.strftime("%Y%m%d"),
            end_date=target_date.strftime("%Y%m%d"),
        )
        if df is None or df.empty:
            return []
        for _, row in df.iterrows():
            items.append(LonghubangItem(
                symbol=_strip_exchange_prefix(_safe_str(row.get("代码"))),
                name=_safe_str(row.get("名称")),
                change_pct=_safe_float(row.get("涨跌幅")),
                net_amount=_safe_float(row.get("龙虎榜净买额") or row.get("净买额")),
                reason=_safe_str(row.get("上榜原因")),
                institution_buy=_safe_float(row.get("机构买入额") or 0),
                institution_sell=_safe_float(row.get("机构卖出额") or 0),
            ))
    except Exception:
        logger.exception("获取龙虎榜失败")

    _cache.set(cache_key, items, CACHE_TTL_LHB)
    return items


# ── 5. 指数日线(用于技术面分析) ──
def get_index_daily_bars(symbol: str = "sh000001", days: int = 20) -> list[IndexDailyBar]:
    """获取指数最近 N 日 K 线。symbol 例:sh000001(上证)/sz399006(创业板指)。"""
    cache_key = f"index_daily:{symbol}:{days}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    bars: list[IndexDailyBar] = []
    try:
        df = call_akshare_api("stock_zh_index_daily", symbol=symbol)
        if df is not None and not df.empty:
            for _, row in df.tail(days).iterrows():
                bars.append(IndexDailyBar(
                    trade_date=str(row.get("date")),
                    open=_safe_float(row.get("open")),
                    close=_safe_float(row.get("close")),
                    high=_safe_float(row.get("high")),
                    low=_safe_float(row.get("low")),
                    volume=_safe_float(row.get("volume")),
                ))
    except Exception:
        logger.exception("获取指数日线失败 symbol=%s", symbol)

    _cache.set(cache_key, bars, CACHE_TTL_HISTORY)
    return bars


# ── 6. 行业板块资金流 ──
def get_sector_fund_flow() -> list[SectorFlow]:
    """获取行业板块当日资金流向。"""
    cache_key = "sector_fund_flow"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[SectorFlow] = []
    try:
        df = call_akshare_api(
            "stock_sector_fund_flow_rank",
            indicator="今日", sector_type="行业资金流",
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                items.append(SectorFlow(
                    name=_safe_str(row.get("名称")),
                    change_pct=_safe_float(row.get("今日涨跌幅") or row.get("涨跌幅")),
                    main_net_inflow=_safe_float(row.get("今日主力净流入-净额") or 0),
                    main_net_pct=_safe_float(row.get("今日主力净流入-净占比") or 0),
                    leading_stock=_safe_str(row.get("今日主力净流入最大股") or ""),
                ))
    except Exception:
        logger.exception("获取行业资金流失败")

    _cache.set(cache_key, items, CACHE_TTL_SECTOR_FLOW)
    return items


# ── 7. 今日财报披露 ──
def get_earnings_calendar(target_date: date | None = None) -> list[CatalystEvent]:
    """获取指定日期的财报披露名单。"""
    d = target_date or _latest_trade_date()
    cache_key = f"earnings_calendar:{d.isoformat()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[CatalystEvent] = []
    try:
        # akshare 提供按季度的财报披露日历
        df = call_akshare_api(
            "stock_yjbb_em",
            date=d.strftime("%Y%m%d"),
        )
        if df is not None and not df.empty:
            for _, row in df.head(50).iterrows():
                items.append(CatalystEvent(
                    event_type="earnings",
                    symbol=_strip_exchange_prefix(_safe_str(row.get("股票代码"))),
                    name=_safe_str(row.get("股票简称")),
                    trade_date=d.isoformat(),
                    detail=f"营收 {_safe_str(row.get('营业总收入-营业总收入'))}, "
                           f"净利润 {_safe_str(row.get('净利润-净利润'))}",
                ))
    except Exception:
        logger.exception("获取财报披露失败")

    _cache.set(cache_key, items, CACHE_TTL_CALENDAR)
    return items


# ── 8. 解禁名单 ──
def get_unlock_calendar(target_date: date | None = None) -> list[CatalystEvent]:
    """获取指定日期解禁名单。"""
    d = target_date or _latest_trade_date()
    cache_key = f"unlock_calendar:{d.isoformat()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[CatalystEvent] = []
    try:
        df = call_akshare_api(
            "stock_restricted_release_queue_em",
            start_date=d.strftime("%Y%m%d"),
            end_date=d.strftime("%Y%m%d"),
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                items.append(CatalystEvent(
                    event_type="unlock",
                    symbol=_strip_exchange_prefix(_safe_str(row.get("代码"))),
                    name=_safe_str(row.get("名称")),
                    trade_date=d.isoformat(),
                    detail=f"解禁数量 {_safe_str(row.get('解禁数量(股)'))}, "
                           f"占总股本 {_safe_str(row.get('占总股本比例'))}",
                ))
    except Exception:
        logger.exception("获取解禁名单失败")

    _cache.set(cache_key, items, CACHE_TTL_CALENDAR)
    return items


# ── 9. 新股申购日历 ──
def get_ipo_calendar() -> list[CatalystEvent]:
    """获取近期新股申购清单。"""
    cache_key = "ipo_calendar"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    items: list[CatalystEvent] = []
    try:
        df = call_akshare_api("stock_xgsglb_em", symbol="全部股票")
        if df is not None and not df.empty:
            today = date.today()
            from datetime import timedelta
            window_end = today + timedelta(days=7)
            for _, row in df.head(100).iterrows():
                raw_date = _safe_str(row.get("申购日期"))
                try:
                    purchase_date = pd.to_datetime(raw_date).date()
                except Exception:
                    continue
                if not (today - timedelta(days=1) <= purchase_date <= window_end):
                    continue
                items.append(CatalystEvent(
                    event_type="ipo",
                    symbol=_strip_exchange_prefix(_safe_str(row.get("股票代码"))),
                    name=_safe_str(row.get("股票简称")),
                    trade_date=purchase_date.isoformat(),
                    detail=f"发行价 {_safe_str(row.get('发行价格'))}, "
                           f"申购上限 {_safe_str(row.get('申购上限'))}",
                ))
    except Exception:
        logger.exception("获取新股申购失败")

    _cache.set(cache_key, items, CACHE_TTL_CALENDAR)
    return items


# ── 11. 除权除息事件 ──
@dataclass
class DividendEvent:
    """单只股票一次除权除息记录。"""
    symbol: str
    ex_date: str               # 除权除息日 YYYY-MM-DD
    cash_dividend: float       # 每股现金分红(税后,元)
    bonus_ratio: float         # 每股送股(10送 X → X/10)
    transfer_ratio: float      # 每股转增(10转 X → X/10)


def get_dividend_events(symbol: str, lookback_days: int = 365) -> list[DividendEvent]:
    """获取个股近 N 日除权除息记录。

    akshare 数据源:stock_history_dividend(返回历史送转/分红事件,字段格式不太统一)。
    本函数做防御性解析:任何字段缺失都跳过。
    """
    cache_key = f"dividend:{symbol}:{lookback_days}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    events: list[DividendEvent] = []
    try:
        df = call_akshare_api("stock_history_dividend_detail", symbol=symbol, indicator="分红")
        if df is None or df.empty:
            _cache.set(cache_key, events, CACHE_TTL_CALENDAR)
            return events
        from datetime import timedelta as _td
        cutoff = date.today() - _td(days=lookback_days)
        for _, row in df.iterrows():
            ex_date_raw = _safe_str(row.get("除权除息日") or row.get("除权日"))
            try:
                ex_date = pd.to_datetime(ex_date_raw).date()
            except Exception:
                continue
            if ex_date < cutoff:
                continue
            cash_per_share = _safe_float(row.get("派息(元/股)") or row.get("派息") or 0)
            bonus_ratio = _safe_float(row.get("送股") or row.get("送股(股/10股)") or 0) / 10
            transfer_ratio = _safe_float(row.get("转增") or row.get("转增(股/10股)") or 0) / 10
            events.append(DividendEvent(
                symbol=symbol,
                ex_date=ex_date.isoformat(),
                cash_dividend=cash_per_share,
                bonus_ratio=bonus_ratio,
                transfer_ratio=transfer_ratio,
            ))
    except Exception:
        logger.debug("获取除权除息失败 symbol=%s", symbol, exc_info=True)

    _cache.set(cache_key, events, CACHE_TTL_CALENDAR)
    return events


# ── 10. 融资融券余额 ──
def get_margin_balance() -> MarginBalance | None:
    """获取最近一日两融余额。"""
    cache_key = "margin_balance"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df_sh = call_akshare_api("stock_margin_sse")
        df_sz = call_akshare_api("stock_margin_szse")
        if (df_sh is None or df_sh.empty) and (df_sz is None or df_sz.empty):
            return None

        sh_finance = sh_securities = sz_finance = sz_securities = 0.0
        last_date = ""

        if df_sh is not None and not df_sh.empty:
            row = df_sh.iloc[-1]
            sh_finance = _safe_float(
                row.get("融资余额") or row.get("融资余额(元)") or 0
            ) / 100000000
            sh_securities = _safe_float(
                row.get("融券余额") or row.get("融券余额(元)") or 0
            ) / 100000000
            last_date = _safe_str(row.get("信用交易日期") or row.get("交易日期"))
        if df_sz is not None and not df_sz.empty:
            row = df_sz.iloc[-1]
            sz_finance = _safe_float(
                row.get("融资余额") or row.get("融资余额(元)") or 0
            ) / 100000000
            sz_securities = _safe_float(
                row.get("融券余额") or row.get("融券余额(元)") or 0
            ) / 100000000
            if not last_date:
                last_date = _safe_str(row.get("信用交易日期") or row.get("交易日期"))

        balance = MarginBalance(
            trade_date=last_date,
            financing_balance=sh_finance + sz_finance,
            securities_balance=sh_securities + sz_securities,
            total_balance=sh_finance + sz_finance + sh_securities + sz_securities,
        )
        _cache.set(cache_key, balance, CACHE_TTL_MARGIN)
        return balance
    except Exception:
        logger.exception("获取两融余额失败")
        return None
