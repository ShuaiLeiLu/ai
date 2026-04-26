'use client';

import { useQuery } from '@tanstack/react-query';
import {
  getAiDigest,
  getAnomalies,
  getHotNews,
  getIndustryBoards,
  getLimitUpLadder,
  getMarketIndicators,
  getStockRank,
  getTrends,
} from '@/features/preopen/api';

const PREOPEN_QUERY_KEY = 'preopen';

const realtimeQueryOptions = {
  staleTime: 60_000,
  refetchOnWindowFocus: false,
};

export function useHotNewsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'hot-news'],
    queryFn: getHotNews,
    ...realtimeQueryOptions,
  });
}

export function useAiDigestQuery(enabled = false) {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'ai-digest'],
    queryFn: getAiDigest,
    enabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useMarketIndicatorsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'market-indicators'],
    queryFn: getMarketIndicators,
    ...realtimeQueryOptions,
  });
}

export function useAnomaliesQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'anomalies'],
    queryFn: getAnomalies,
    ...realtimeQueryOptions,
  });
}

export function useTrendsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'trends'],
    queryFn: getTrends,
    ...realtimeQueryOptions,
  });
}

export function useLimitUpLadderQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'limit-up-ladder'],
    queryFn: getLimitUpLadder,
    ...realtimeQueryOptions,
  });
}

/** 行业板块涨跌查询 */
export function useIndustryBoardsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'industry-boards'],
    queryFn: getIndustryBoards,
    ...realtimeQueryOptions,
  });
}

/** 涨跌榜查询 */
export function useStockRankQuery(direction: 'up' | 'down' = 'up') {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'stock-rank', direction],
    queryFn: () => getStockRank(direction),
    ...realtimeQueryOptions,
  });
}
