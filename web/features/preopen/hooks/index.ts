'use client';

import { useQuery } from '@tanstack/react-query';
import {
  getAiDigest,
  getPreopenAll,
} from '@/features/preopen/api';

const PREOPEN_QUERY_KEY = 'preopen';

/**
 * 聚合查询 —— 一次请求获取盘前速览全量快照数据。
 * 各子 hook 从聚合数据中提取所需字段，共享同一份缓存。
 */
function usePreopenAll() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'all'],
    queryFn: getPreopenAll,
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
  });
}

export function useHotNewsQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.hot_news };
}

export function useAiDigestQuery(enabled = true) {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'ai-digest'],
    queryFn: getAiDigest,
    enabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useMarketIndicatorsQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.market_indicators };
}

export function useAnomaliesQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.anomalies };
}

export function useTrendsQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.trends };
}

export function useLimitUpLadderQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.limit_up_ladder };
}

/** 行业板块涨跌查询 */
export function useIndustryBoardsQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.industry_boards };
}

/** 涨跌榜查询 */
export function useStockRankQuery(direction: 'up' | 'down' = 'up') {
  const query = usePreopenAll();
  return {
    ...query,
    data: direction === 'down' ? query.data?.stock_rank_down : query.data?.stock_rank_up,
  };
}
