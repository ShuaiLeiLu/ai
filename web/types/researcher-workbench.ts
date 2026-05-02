export type RankSortBy = 'today' | 'month';

export interface HiredResearcher {
  researcher_id: string;
  avatar_url: string | null;
  name: string;
  summary: string;
  status: string;
  tags: string[];
  today_yield: number | null;
  today_yield_rate: number | null;
  month_yield_rate: number | null;
  total_asset: number | null;
  win_rate_30d: number | null;
  has_trading_account: boolean;
  level: string;
}

export interface HotDocument {
  id: string;
  title: string;
  summary: string;
  researcher_name: string;
  create_time: string;
  view_count: number | null;
  comment_count: number | null;
  metrics_ready: boolean;
}

export interface PublicRankItem {
  researcher_id: string;
  name: string;
  total_asset: number;
  today_yield_rate: number;
  month_yield_rate: number;
  risk_note: string;
}

export interface QuickAction {
  action_key: string;
  title: string;
  description: string;
}

export interface WorkbenchOverview {
  hired: HiredResearcher[];
  hot_documents: HotDocument[];
  rankings: PublicRankItem[];
  quick_actions: QuickAction[];
  risk_disclaimer: string;
  partial_failures: string[];
}
