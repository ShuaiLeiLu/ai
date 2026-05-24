/** 题材掘金 · 前端类型定义（对齐 server Pydantic schema） */

export type ThemeStatus = 'today_hot' | 'yesterday_hot' | 'waiting' | 'lurking';
export type SentimentDirection = 'bullish' | 'bearish' | 'neutral';
export type ImpactLevel = 'high' | 'medium' | 'low';
export type EventCategory = 'policy' | 'theme' | 'sentiment' | 'industry' | 'company' | 'macro' | 'other';
export type RoleGroup = 'sentiment_core' | 'logic_core' | 'trend_anchor';
export type DeviationDirection = 'undervalued' | 'overvalued';
export type OpinionStance = 'bullish' | 'bearish' | 'neutral' | 'watch';
export type ScenarioKind = 'optimistic' | 'neutral' | 'pessimistic';
export type RecommendHorizon = 'today' | 'this_week';

export interface AccessStatus {
  vip: boolean;
  unlocked_today: boolean;
  battery_balance: number;
  unlock_cost: number;
}

export interface UnlockResult {
  success: boolean;
  battery_balance: number;
  unlocked_until: string;
}

export interface ThemeListItem {
  id: string;
  rank: number;
  name: string;
  status: ThemeStatus;
  limit_up_count: number;
  event_count: number;
}

export interface TheySayBoard {
  generated_at: string;
  sentiment_direction: SentimentDirection;
  sentiment_label: string;
  bullish_count: number;
  neutral_count: number;
  bearish_count: number;
  confidence: number;
  cycle: string;
  cycle_note: string;
  summary: string;
}

export interface PastEvent {
  id: string;
  title: string;
  description: string;
  impact: ImpactLevel;
  category: EventCategory;
  occurred_at: string;
  source?: string | null;
}

export interface FutureExpectation {
  id: string;
  kind: 'catalyst' | 'risk';
  title: string;
  description: string;
  when: string;
}

export interface CoreTarget {
  symbol: string;
  name: string;
  metric: string;
  note: string;
}

export interface CoreTargetGroup {
  role: RoleGroup;
  label: string;
  items: CoreTarget[];
}

export interface EventDrivenChain {
  past_events: PastEvent[];
  future_expectations: FutureExpectation[];
  core_target_groups: CoreTargetGroup[];
}

export interface ExpectationGap {
  id: string;
  direction: DeviationDirection;
  target_label: string;
  title: string;
  magnitude_pct: number;
  reasoning: string;
}

export interface MarketStorySegment {
  time_range: string;
  headline: string;
  narrative: string;
}

export interface MarketStory {
  today: MarketStorySegment[];
  yesterday: MarketStorySegment[];
}

export interface HiddenLogicItem {
  id: string;
  title: string;
  description: string;
  tags: string[];
}

export interface AnchorRecommendItem {
  horizon: RecommendHorizon;
  label: string;
  title: string;
  description: string;
  related_symbols: string[];
}

export interface Scenario {
  kind: ScenarioKind;
  label: string;
  probability: number;
  title: string;
  strategy: string;
  key_observation: string;
}

export interface ResearcherOpinion {
  id: string;
  researcher_id: string;
  researcher_name: string;
  avatar_initial: string;
  avatar_color: string;
  stance: OpinionStance;
  confidence_pct: number;
  related_symbol?: string | null;
  content: string;
}

export interface ConsensusBreakdown {
  bullish: number;
  neutral: number;
  bearish: number;
  watch: number;
  summary: string;
}

export interface ThemeDetail {
  id: string;
  name: string;
  status: ThemeStatus;
  limit_up_count: number;
  researcher_count: number;
  they_say: TheySayBoard;
  event_chain: EventDrivenChain;
  expectation_gaps: ExpectationGap[];
  market_story: MarketStory;
  hidden_logic: HiddenLogicItem[];
  anchor_recommendations: AnchorRecommendItem[];
  scenarios: Scenario[];
  opinions: ResearcherOpinion[];
  consensus: ConsensusBreakdown;
}
