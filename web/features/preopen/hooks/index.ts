'use client';

import { useQuery } from '@tanstack/react-query';
import { getPreopenAll } from '@/features/preopen/api';

const PREOPEN_QUERY_KEY = 'preopen';

/**
 * 聚合查询 —— 一次请求获取盘前速览全量数据。
 * 各子 hook 通过 select 从聚合数据中提取所需字段，共享同一份缓存。
 */
function usePreopenAll() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'all'],
    queryFn: getPreopenAll,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useHotNewsQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.hot_news };
}

export function useAiDigestQuery() {
  const query = usePreopenAll();
  return { ...query, data: query.data?.ai_digest };
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
  return { ...query, data: direction === 'up' ? query.data?.stock_rank_up : query.data?.stock_rank_down };
}
