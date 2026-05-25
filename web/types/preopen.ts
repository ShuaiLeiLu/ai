export type { ApiResponse, ListResponse } from './api';

export interface TradingCalendarHint {
  trade_date: string;
  is_trading_day: boolean;
  notice: string;
}

export interface HotNewsItem {
  news_id: string;
  title: string;
  summary: string;
  source: string;
  published_at: string;
  heat: number;
  sentiment: 'bullish' | 'neutral' | 'bearish';
  symbols: string[];
  jump_type: 'news' | 'analysis';
  jump_target: string;
}

export interface AiDigest {
  digest_id: string;
  report_title?: string | null;
  headline: string;
  interval_start: string;
  interval_end: string;
  generated_at: string;
  sentiment: 'bullish' | 'neutral' | 'bearish';
  key_points: string[];
  report_sections?: AiDigestSection[];
  news_drivers?: string[];
  opportunity_sectors?: string[];
  risk_sectors?: string[];
  intraday_watch?: string[];
  simulation_plan?: string[];
}

export interface AiDigestSection {
  title: string;
  paragraphs: string[];
  bullets: string[];
  table: Record<string, string>[];
}

export interface MarketIndicator {
  indicator: string;
  label: string;
  value: number;
  unit: string;
  direction: 'up' | 'down' | 'flat';
  reference: string;
}

export interface AnomalyItem {
  symbol: string;
  name: string;
  category: 'tail-session-move' | 'severe-volatility';
  change_pct: number;
  turnover_ratio: number;
  risk_tags: string[];
  note: string;
  risk_type?: string | null;
  risk_window?: string | null;
  is_new?: boolean;
}

export interface AnomalyOverview {
  calendar: TradingCalendarHint;
  tail_session_moves: AnomalyItem[];
  severe_volatility: AnomalyItem[];
}

export interface TrendPoint {
  trade_date: string;
  value: number;
}

export interface TrendSeries {
  metric: string;
  label: string;
  unit: string;
  points: TrendPoint[];
}

export interface TrendOverview {
  calendar: TradingCalendarHint;
  window_days: number;
  series: TrendSeries[];
}

export interface LimitUpLadderItem {
  symbol: string;
  name: string;
  trade_date?: string | null;
  ladder_level: number;
  change_pct?: number | null;
  first_seal_time: string;
  final_seal_time: string;
  reason: string;
  risk_tags: string[];
}

/** 行业板块涨跌条目 */
export interface IndustryBoardItem {
  name: string;                // 板块名称
  change_pct: number;          // 涨跌幅（%）
  total_amount: number;        // 总成交额（亿元）
  net_inflow: number;          // 净流入（亿元）
  rise_count: number;          // 上涨家数
  fall_count: number;          // 下跌家数
  leading_stock: string;       // 领涨股
  leading_stock_pct: number;   // 领涨股涨跌幅
}

/** 涨跌榜个股条目 */
export interface StockRankItem {
  symbol: string;              // 代码
  name: string;                // 名称
  change_pct: number;          // 涨跌幅（%）
  price: number;               // 最新价
  amount: number;              // 成交额
  turnover_ratio: number;      // 换手率
  industry: string;            // 所属行业
  reason: string;              // 入选理由
}

/** 盘前速览聚合数据 */
export interface PreopenAllData {
  hot_news: HotNewsItem[];
  market_indicators: MarketIndicator[];
  anomalies: AnomalyOverview | null;
  trends: TrendOverview | null;
  limit_up_ladder: LimitUpLadderItem[];
  industry_boards: IndustryBoardItem[];
  stock_rank_up: StockRankItem[];
  stock_rank_down: StockRankItem[];
}
