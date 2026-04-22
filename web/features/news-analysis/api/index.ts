import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import {
  AIPanelData,
  GetNewsFeedParams,
  HotNewsItem,
  HotStock,
  NewsAnalysisAllData,
  NewsFeedItem,
  StockNewsSummary
} from '@/types/news-analysis';

const NEWS_ANALYSIS_API_BASE = '/news-analysis';

function buildQuery(params: GetNewsFeedParams): string {
  const search = new URLSearchParams();
  if (params.category) search.set('category', params.category);
  if (typeof params.important_only === 'boolean') {
    search.set('important_only', String(params.important_only));
  }
  if (params.stock_code) search.set('stock_code', params.stock_code);
  const query = search.toString();
  return query ? `?${query}` : '';
}

export const getNewsFeed = (params: GetNewsFeedParams): Promise<NewsFeedItem[]> => {
  return http<ApiResponse<ListResponse<NewsFeedItem>>>(
    `${NEWS_ANALYSIS_API_BASE}/feed${buildQuery(params)}`
  ).then((res) => res.data.items);
};

export const getAIPanels = (): Promise<AIPanelData[]> => {
  return http<ApiResponse<ListResponse<AIPanelData>>>(`${NEWS_ANALYSIS_API_BASE}/ai-panels`).then(
    (res) => res.data.items
  );
};

export const getHotStocks = (): Promise<HotStock[]> => {
  return http<ApiResponse<ListResponse<HotStock>>>(`${NEWS_ANALYSIS_API_BASE}/hot-stocks`).then(
    (res) => res.data.items
  );
};

export const getHotNews = (): Promise<HotNewsItem[]> => {
  return http<ApiResponse<ListResponse<HotNewsItem>>>(`${NEWS_ANALYSIS_API_BASE}/hot-news`).then(
    (res) => res.data.items
  );
};

export const getNewsSummaryByStock = (stockCode: string): Promise<StockNewsSummary> => {
  return http<ApiResponse<StockNewsSummary>>(
    `${NEWS_ANALYSIS_API_BASE}/by-stock/${stockCode}/summary`
  ).then((res) => res.data);
};

/** 聚合接口 —— 一次请求获取资讯分析全量数据 */
export const getNewsAnalysisAll = (): Promise<NewsAnalysisAllData> => {
  return http<ApiResponse<NewsAnalysisAllData>>(`${NEWS_ANALYSIS_API_BASE}/all`).then((res) => res.data);
};
