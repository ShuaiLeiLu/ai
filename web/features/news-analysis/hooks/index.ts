// web/features/news-analysis/hooks/index.ts
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as api from '../api';
import type { GetNewsFeedParams, NewsFeedItem } from '@/types/news-analysis';

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

function matchesStock(item: NewsFeedItem, stockCode: string): boolean {
  const normalized = stockCode.trim();
  if (!normalized) return true;
  return item.stock_relations.some((stock) => stock.stock_code === normalized || stock.stock_name.includes(normalized));
}

function filterFeed(items: NewsFeedItem[] | undefined, params?: GetNewsFeedParams): NewsFeedItem[] | undefined {
  if (!items) return undefined;
  const category = params?.category ?? 'all';
  const importantOnly = Boolean(params?.important_only);
  const stockCode = params?.stock_code;
  return items.filter((item) => {
    if (category !== 'all' && item.category !== category) return false;
    if (importantOnly && !item.is_important) return false;
    if (stockCode && !matchesStock(item, stockCode)) return false;
    return true;
  });
}

export const useNewsFeed = (params?: GetNewsFeedParams) => {
  const query = useNewsAnalysisAll();
  const data = useMemo(() => filterFeed(query.data?.feed, params), [params, query.data?.feed]);
  return { ...query, data };
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
