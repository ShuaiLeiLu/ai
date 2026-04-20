/**
 * 市场核心指标 —— 水平紧凑统计卡片行
 *
 * 布局：等分卡片横排，每张卡片显示标签、大数值、副标题引用
 * 数据流：useMarketIndicatorsQuery → 后端 /preopen/market-indicators
 */
'use client';

import { Skeleton } from 'antd';

import { useMarketIndicatorsQuery } from '@/features/preopen/hooks';
import type { MarketIndicator } from '@/types/preopen';

/** 方向对应颜色 */
const dirColor = (d: string) =>
  d === 'up' ? 'text-rose-600' : d === 'down' ? 'text-green-600' : 'text-slate-700';

export function MarketIndicatorsCard() {
  const { data, isLoading } = useMarketIndicatorsQuery();
  const indicators = data ?? [];

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-slate-100 bg-white p-4">
            <Skeleton active paragraph={{ rows: 1 }} title={false} />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {indicators.map((item: MarketIndicator) => (
        <div
          key={item.indicator}
          className="rounded-xl border border-slate-100 bg-white px-4 py-3 shadow-sm"
        >
          {/* 标签 */}
          <div className="mb-1 text-xs text-slate-500">{item.label}</div>
          {/* 大数值 + 单位 */}
          <div className={`text-xl font-semibold leading-tight ${dirColor(item.direction)}`}>
            {item.value % 1 === 0 ? item.value : item.value.toFixed(2)}
            <span className="ml-0.5 text-sm font-normal">{item.unit}</span>
          </div>
          {/* 引用说明 */}
          <div className="mt-1 truncate text-[11px] text-slate-400">{item.reference}</div>
        </div>
      ))}
    </div>
  );
}
