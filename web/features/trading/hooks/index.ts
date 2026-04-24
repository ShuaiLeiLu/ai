/**
 * 模拟交易 React Query Hooks
 *
 * 核心优化：页面数据走 /trading/all 聚合接口（单次请求），
 * 拆分到 account / positions / records / logs 四个 queryKey 以供组件消费。
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';

import type { PositionItem, TradeLogItem, TradeRecord, TradingAccount, TradingAllData, TradingPortfolioData, TradingStats } from '@/types/trading';
import * as api from '../api';

const featureKey = 'trading';

// ──────────── 聚合查询（核心） ────────────

/** 一次请求获取全部模拟盘数据，拆分到各 queryKey */
export const useTradingAll = (researcherId?: string, enabled: boolean = true) => {
  const qc = useQueryClient();
  return useQuery({
    queryKey: [featureKey, 'all', researcherId ?? 'default'],
    queryFn: async () => {
      const data = await api.getTradingAll(researcherId);
      // 同步写入子 queryKey，让独立 hook 也能读到数据
      qc.setQueryData([featureKey, 'account', researcherId], data.account);
      qc.setQueryData([featureKey, 'positions', researcherId], data.positions);
      qc.setQueryData([featureKey, 'records', researcherId], data.records);
      qc.setQueryData([featureKey, 'logs', researcherId], data.logs);
      return data;
    },
    enabled: Boolean(researcherId) && enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });
};

/** 工作台轻量模拟盘数据：只请求账户和持仓 */
export const useTradingPortfolio = (researcherId?: string, enabled: boolean = true) => {
  const qc = useQueryClient();
  return useQuery({
    queryKey: [featureKey, 'portfolio', researcherId ?? 'default'],
    queryFn: async () => {
      const data = await api.getTradingPortfolio(researcherId);
      qc.setQueryData([featureKey, 'account', researcherId], data.account);
      qc.setQueryData([featureKey, 'positions', researcherId], data.positions);
      return data;
    },
    enabled: Boolean(researcherId) && enabled,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
  });
};

// ──────────── 子数据消费 hooks（从缓存读取） ────────────

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
