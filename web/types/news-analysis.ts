export type NewsCategory = 'all' | 'flash' | 'announcement' | 'report';

export type NewsSentiment = 'bullish' | 'neutral' | 'bearish';

export type AIPanelKey =
  | '24h_digest'
  | 'hotspot_tracking'
  | 'macro_impact'
  | 'stock_interpretation';

export interface GetNewsFeedParams {
  category?: NewsCategory;
  important_only?: boolean;
  stock_code?: string;
}

export interface NewsStockRelation {
  stock_code: string;
  stock_name: string;
}

export interface NewsThemeRelation {
  theme_name: string;
}

export interface NewsInterpretation {
  interpretation_id: string;
  interpretation_type: 'event' | 'theme' | 'macro' | 'stock';
  content: string;
  confidence: number;
}

export interface NewsFeedItem {
  news_id: string;
  category: Exclude<NewsCategory, 'all'>;
  source: string;
  title: string;
  summary: string;
  content: string;
  importance: number;
  is_important: boolean;
  publish_time: string;
  stock_relations: NewsStockRelation[];
  theme_relations: NewsThemeRelation[];
  ai_interpretations: NewsInterpretation[];
}

export interface AIPanelData {
  panel_key: AIPanelKey;
  title: string;
  summary: string;
  highlights: string[];
  confidence: number;
  updated_at: string;
}

export interface HotStock {
  stock_code: string;
  stock_name: string;
  heat: number;
  label: string;
}

export interface HotNewsItem {
  rank: number;
  news_id: string;
  title: string;
  source: string;
  publish_time: string;
  category: Exclude<NewsCategory, 'all'>;
  heat_score: number;
}

export interface StockNewsSummary {
  stock_code: string;
  stock_name: string;
  conclusion: string;
  related_news_count: number;
  sentiment_distribution: Record<NewsSentiment, number>;
  related_themes: string[];
  avg_confidence: number;
  latest_publish_time: string | null;
}

/** 资讯分析聚合数据 */
export interface NewsAnalysisAllData {
  feed: NewsFeedItem[];
  ai_panels: AIPanelData[];
  hot_stocks: HotStock[];
  hot_news: HotNewsItem[];
}
