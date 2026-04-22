/**
 * 模拟交易 React Query Hooks
 *
 * 支持按 researcherId 查询特定研究员的模拟盘数据。
 * 当 researcherId 为空时，返回默认 mock 数据。
 */
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { createSseClient } from '@/lib/sse/create-sse-client';
import { TradingStats, TradingStreamSnapshot } from '@/types/trading';
import * as api from '../api';

const featureKey = 'trading';

/** 查询模拟账户概况 */
export const useTradingAccount = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'account', researcherId ?? 'default'],
    queryFn: () => api.getTradingAccount(researcherId),
    enabled: Boolean(researcherId),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

export const useTradingAccountWhenEnabled = (researcherId?: string, enabled: boolean = true) =>
  useQuery({
    queryKey: [featureKey, 'account', researcherId ?? 'default'],
    queryFn: () => api.getTradingAccount(researcherId),
    enabled: Boolean(researcherId) && enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

/** 查询持仓列表 */
export const useTradingPositions = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'positions', researcherId ?? 'default'],
    queryFn: () => api.getTradingPositions(researcherId),
    enabled: Boolean(researcherId),
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

export const useTradingPositionsWhenEnabled = (researcherId?: string, enabled: boolean = true) =>
  useQuery({
    queryKey: [featureKey, 'positions', researcherId ?? 'default'],
    queryFn: () => api.getTradingPositions(researcherId),
    enabled: Boolean(researcherId) && enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });

/** 查询成交记录 */
export const useTradingRecords = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'records', researcherId ?? 'default'],
    queryFn: () => api.getTradingRecords(researcherId),
    enabled: Boolean(researcherId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

/** 查询交易日志（trade 表格 + analysis 富文本） */
export const useTradingLogs = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'logs', researcherId ?? 'default'],
    queryFn: () => api.getTradingLogs(researcherId),
    enabled: Boolean(researcherId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

/** 查询历史交易统计（收益曲线、月度收益、风控指标） */
export const useTradingStats = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'stats', researcherId ?? 'default'],
    queryFn: () => api.getTradingStats(researcherId),
    enabled: Boolean(researcherId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useTradingStatsWhenEnabled = (researcherId?: string, enabled: boolean = true) =>
  useQuery({
    queryKey: [featureKey, 'stats', researcherId ?? 'default'],
    queryFn: () => api.getTradingStats(researcherId),
    enabled: Boolean(researcherId) && enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export type TradingStreamStatus = 'idle' | 'connecting' | 'live' | 'error';

/** 交易实时流（SSE）—— 实时推送账户与持仓快照 */
export const useTradingRealtimeStream = (researcherId?: string) => {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<TradingStreamStatus>(researcherId ? 'connecting' : 'idle');
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!researcherId || typeof window === 'undefined') {
      setStatus('idle');
      setLastUpdatedAt(null);
      return;
    }

    const search = new URLSearchParams({ researcher_id: researcherId });
    const token = window.localStorage.getItem('access_token');
    if (token) {
      // EventSource 无法携带 Authorization 头，这里用 query 参数透传给 SSE 端点。
      search.set('access_token', token);
    }

    setStatus('connecting');
    const sse = createSseClient(`/trading/stream?${search.toString()}`);

    sse.addEventListener('open', () => {
      setStatus('live');
    });

    sse.addEventListener('snapshot', (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as TradingStreamSnapshot;
        queryClient.setQueryData([featureKey, 'account', researcherId], payload.account);
        queryClient.setQueryData([featureKey, 'positions', researcherId], payload.positions);
        queryClient.setQueryData<TradingStats | undefined>(
          [featureKey, 'stats', researcherId],
          (previous) => (previous ? { ...previous, total_asset: payload.account.total_asset } : previous),
        );
        setLastUpdatedAt(payload.generated_at);
        setStatus('live');
      } catch {
        setStatus('error');
      }
    });

    sse.addEventListener('error', () => {
      setStatus('error');
    });

    return () => {
      sse.close();
    };
  }, [queryClient, researcherId]);

  return { status, lastUpdatedAt };
};
