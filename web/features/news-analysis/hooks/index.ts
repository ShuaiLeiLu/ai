// web/features/news-analysis/hooks/index.ts
import { useQuery } from '@tanstack/react-query';
import * as api from '../api';
import { GetNewsFeedParams } from '@/types/news-analysis';

const FEATURE_KEY = 'news-analysis';

/**
 * 聚合查询 —— 一次请求获取资讯分析数据（不含 AI 面板）。
 * 各子 hook 从聚合数据中提取所需字段，共享同一份缓存。
 */
function useNewsAnalysisAll() {
  return useQuery({
    queryKey: [FEATURE_KEY, 'all'],
    queryFn: api.getNewsAnalysisAll,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export const useNewsFeed = (_params?: GetNewsFeedParams) => {
  const query = useNewsAnalysisAll();
  return { ...query, data: query.data?.feed };
};

/**
 * AI 智能分析面板 —— 独立查询，用户点击后才触发。
 * enabled 默认 false，由组件手动控制。
 */
export const useAIPanels = (enabled = false) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'ai-panels'],
    queryFn: api.getAIPanels,
    enabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
};

export const useHotStocks = () => {
  const query = useNewsAnalysisAll();
  return { ...query, data: query.data?.hot_stocks };
};

export const useHotNews = () => {
  const query = useNewsAnalysisAll();
  return { ...query, data: query.data?.hot_news };
};

export const useNewsSummaryByStock = (stockCode: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'summary', stockCode],
    queryFn: () => api.getNewsSummaryByStock(stockCode),
    enabled: options?.enabled ?? false,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
};
