import { http } from '@/lib/request/http-client';
import {
  ApiResponse,
  AiDigest,
  AnomalyOverview,
  HotNewsItem,
  IndustryBoardItem,
  ListResponse,
  LimitUpLadderItem,
  MarketIndicator,
  PreopenAllData,
  StockRankItem,
  TrendOverview
} from '@/types/preopen';

export const getHotNews = (): Promise<HotNewsItem[]> => {
  return http<ApiResponse<ListResponse<HotNewsItem>>>('/preopen/hot-news').then((res) => res.data.items);
};

export const getAiDigest = (): Promise<AiDigest> => {
  return http<ApiResponse<AiDigest>>('/preopen/ai-digest').then((res) => res.data);
};

export const getMarketIndicators = (): Promise<MarketIndicator[]> => {
  return http<ApiResponse<ListResponse<MarketIndicator>>>('/preopen/market-indicators').then(
    (res) => res.data.items
  );
};

export const getAnomalies = (): Promise<AnomalyOverview> => {
  return http<ApiResponse<AnomalyOverview>>('/preopen/anomalies').then((res) => res.data);
};

export const getTrends = (): Promise<TrendOverview> => {
  return http<ApiResponse<TrendOverview>>('/preopen/trends').then((res) => res.data);
};

export const getLimitUpLadder = (): Promise<LimitUpLadderItem[]> => {
  return http<ApiResponse<ListResponse<LimitUpLadderItem>>>('/preopen/limit-up-ladder').then(
    (res) => res.data.items
  );
};

/** 获取行业板块涨跌数据 */
export const getIndustryBoards = (): Promise<IndustryBoardItem[]> => {
  return http<ApiResponse<ListResponse<IndustryBoardItem>>>('/preopen/industry-boards').then(
    (res) => res.data.items
  );
};

/** 获取涨跌榜数据 */
export const getStockRank = (direction: 'up' | 'down' = 'up'): Promise<StockRankItem[]> => {
  return http<ApiResponse<ListResponse<StockRankItem>>>(`/preopen/stock-rank?direction=${direction}`).then(
    (res) => res.data.items
  );
};

/** 聚合接口 —— 一次请求获取盘前速览全量快照数据 */
export const getPreopenAll = (): Promise<PreopenAllData> => {
  return http<ApiResponse<PreopenAllData>>('/preopen/all').then((res) => res.data);
};
