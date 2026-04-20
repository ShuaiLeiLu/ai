// web/features/news-analysis/hooks/index.ts
import { useQuery } from '@tanstack/react-query';
import * as api from '../api';
import { GetNewsFeedParams } from '@/types/news-analysis';

const FEATURE_KEY = 'news-analysis';

export const useNewsFeed = (params: GetNewsFeedParams) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'feed', params],
    queryFn: () => api.getNewsFeed(params),
  });
};

export const useAIPanels = () => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'ai-panels'],
    queryFn: api.getAIPanels,
  });
};

export const useHotStocks = () => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'hot-stocks'],
    queryFn: api.getHotStocks,
  });
};

export const useHotNews = () => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'hot-news'],
    queryFn: api.getHotNews,
  });
};

export const useNewsSummaryByStock = (stockCode: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'summary', stockCode],
    queryFn: () => api.getNewsSummaryByStock(stockCode),
    enabled: options?.enabled ?? false,
  });
};
