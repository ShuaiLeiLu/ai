/**
 * 市场核心指标 —— 横向网格小卡片
 *
 * 设计：作为 Overview / 工作台首页的「第二焦点」，用 StatCard 网格展示
 * 数据流：useMarketIndicatorsQuery → 后端 /preopen/market-indicators
 */
'use client';

import { Skeleton } from 'antd';

import { StatCard } from '@/components/ui/stat-card';
import { PageCard } from '@/components/ui/page-card';
import { useMarketIndicatorsQuery } from '@/features/preopen/hooks';
import type { MarketIndicator } from '@/types/preopen';

function fmtValue(v: number) {
  return v % 1 === 0 ? v.toLocaleString('zh-CN') : v.toFixed(2);
}

export function MarketIndicatorsCard() {
  const { data, isLoading } = useMarketIndicatorsQuery();
  const indicators = data ?? [];

  if (isLoading) {
    return (
      <PageCard title="市场强弱" extra={<span className="cursor-pointer">明细</span>}>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-lg bg-ink-25 p-3">
              <Skeleton active paragraph={{ rows: 1 }} title={false} />
            </div>
          ))}
        </div>
      </PageCard>
    );
  }

  return (
    <PageCard title="市场强弱" extra={<span className="cursor-pointer">明细</span>}>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
        {indicators.slice(0, 6).map((item: MarketIndicator) => (
          <StatCard
            key={item.indicator}
            embedded
            label={item.label}
            value={fmtValue(item.value)}
            unit={item.unit}
            hint={item.reference}
            direction={item.direction}
          />
        ))}
      </div>
    </PageCard>
  );
}
