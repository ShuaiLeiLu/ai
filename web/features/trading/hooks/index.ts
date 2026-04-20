/**
 * 模拟交易 React Query Hooks
 *
 * 支持按 researcherId 查询特定研究员的模拟盘数据。
 * 当 researcherId 为空时，返回默认 mock 数据。
 */
import { useQuery } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'trading';

/** 查询模拟账户概况 */
export const useTradingAccount = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'account', researcherId ?? 'default'],
    queryFn: () => api.getTradingAccount(researcherId),
    enabled: Boolean(researcherId),
  });

/** 查询持仓列表 */
export const useTradingPositions = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'positions', researcherId ?? 'default'],
    queryFn: () => api.getTradingPositions(researcherId),
    enabled: Boolean(researcherId),
  });

/** 查询成交记录 */
export const useTradingRecords = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'records', researcherId ?? 'default'],
    queryFn: () => api.getTradingRecords(researcherId),
    enabled: Boolean(researcherId),
  });

/** 查询交易日志（trade 表格 + analysis 富文本） */
export const useTradingLogs = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'logs', researcherId ?? 'default'],
    queryFn: () => api.getTradingLogs(researcherId),
    enabled: Boolean(researcherId),
  });

/** 查询历史交易统计（收益曲线、月度收益、风控指标） */
export const useTradingStats = (researcherId?: string) =>
  useQuery({
    queryKey: [featureKey, 'stats', researcherId ?? 'default'],
    queryFn: () => api.getTradingStats(researcherId),
    enabled: Boolean(researcherId),
  });

