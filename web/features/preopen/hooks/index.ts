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
  getTrends
} from '@/features/preopen/api';

const PREOPEN_QUERY_KEY = 'preopen';

export function useHotNewsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'hot-news'],
    queryFn: getHotNews
  });
}

export function useAiDigestQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'ai-digest'],
    queryFn: getAiDigest
  });
}

export function useMarketIndicatorsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'market-indicators'],
    queryFn: getMarketIndicators
  });
}

export function useAnomaliesQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'anomalies'],
    queryFn: getAnomalies
  });
}

export function useTrendsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'trends'],
    queryFn: getTrends
  });
}

export function useLimitUpLadderQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'limit-up-ladder'],
    queryFn: getLimitUpLadder
  });
}

/** 行业板块涨跌查询 */
export function useIndustryBoardsQuery() {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'industry-boards'],
    queryFn: getIndustryBoards
  });
}

/** 涨跌榜查询 */
export function useStockRankQuery(direction: 'up' | 'down' = 'up') {
  return useQuery({
    queryKey: [PREOPEN_QUERY_KEY, 'stock-rank', direction],
    queryFn: () => getStockRank(direction)
  });
}
