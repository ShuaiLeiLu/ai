/**
 * 市场强弱指标（趋势图） —— 15 日涨停/跌停/连板趋势折线图
 *
 * 布局：顶部 Segmented 切换维度 + ECharts 折线图（紧凑高度）
 * 数据流：useTrendsQuery → 后端 /preopen/trends
 */
'use client';

import { Segmented, Skeleton } from 'antd';
import { useState } from 'react';
import dynamic from 'next/dynamic';
import type { EChartsOption } from 'echarts';

const ReactECharts = dynamic(() => import('echarts-for-react'), {
  ssr: false,
  loading: () => <Skeleton active paragraph={{ rows: 4 }} />,
});

import { PageCard } from '@/components/ui/page-card';
import { useTrendsQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { TrendSeries } from '@/types/preopen';

/** 维度切换选项 */
const dimensionOpts = [
  { label: '涨停强度', value: 'daily_limit_up_count' },
  { label: '跌停比', value: 'daily_limit_down_count' },
  { label: '连板家数', value: 'consecutive_limit_up_count' },
];

export function TrendsChartCard() {
  const [dimension, setDimension] = useState('daily_limit_up_count'); // 当前维度
  const { data, isLoading, error } = useTrendsQuery();
  const sel: TrendSeries | undefined = data?.series.find((s) => s.metric === dimension);

  /** 图表配置 */
  const chartOpt: EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 12, top: 8, bottom: 24 },
    xAxis: {
      type: 'category',
      data: sel?.points.map((p) => p.trade_date) ?? [],
      axisLabel: { fontSize: 10, color: '#94a3b8' },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { fontSize: 10, color: '#94a3b8' },
    },
    series: [
      {
        type: 'bar',
        data: sel?.points.map((p) => p.value) ?? [],
        itemStyle: {
          borderRadius: [3, 3, 0, 0],
          color: dimension === 'daily_limit_down_count' ? '#22c55e' : '#f43f5e',
        },
        barMaxWidth: 18,
      },
    ],
  };

  return (
    <StateWrapper
      data={data}
      isLoading={isLoading}
      error={error}
      title="市场强弱指标"
      nonTradingDayMessage={data && !data.calendar.is_trading_day ? data.calendar.notice : undefined}
    >
      <PageCard
        title="市场强弱指标"
        extra={
          <Segmented
            options={dimensionOpts}
            value={dimension}
            onChange={(v) => setDimension(v as string)}
            size="small"
          />
        }
      >
        {data?.window_days === 1 && (
          <div className="mb-2 text-xs text-slate-400">
            当前仅展示最新真实快照；多日趋势需等待每日快照沉淀。
          </div>
        )}
        <ReactECharts option={chartOpt} style={{ height: 200 }} notMerge />
      </PageCard>
    </StateWrapper>
  );
}
