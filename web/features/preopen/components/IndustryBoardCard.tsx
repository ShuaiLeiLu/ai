/**
 * 行业板块涨跌卡片 —— 同花顺行业板块实时涨跌
 *
 * 布局：紧凑列表，每行显示板块名称、领涨股描述、涨跌幅色块
 * 仿截图中"电力/热力"等行业条目样式
 * 数据流：useIndustryBoardsQuery → 后端 /preopen/industry-boards
 */
'use client';

import { Skeleton } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useIndustryBoardsQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { IndustryBoardItem } from '@/types/preopen';

/** 涨跌幅 → 背景色 */
const pctBg = (v: number) =>
  v > 0 ? 'bg-rose-500 text-white' : v < 0 ? 'bg-green-600 text-white' : 'bg-slate-200 text-slate-600';

export function IndustryBoardCard() {
  const { data, isLoading, error } = useIndustryBoardsQuery();

  if (isLoading) {
    return (
      <PageCard title="行业板块涨跌">
        <Skeleton active paragraph={{ rows: 8 }} />
      </PageCard>
    );
  }

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="行业板块涨跌">
      <PageCard title="行业板块涨跌">
        <div className="divide-y divide-slate-50">
          {(data ?? []).slice(0, 20).map((item: IndustryBoardItem) => (
            <div
              key={item.name}
              className="flex items-center gap-3 py-2 transition-colors hover:bg-slate-50"
            >
              {/* 板块名称 */}
              <span className="w-20 shrink-0 text-sm font-medium text-slate-800">
                {item.name}
              </span>

              {/* 领涨股 + 描述 */}
              <span className="min-w-0 flex-1 truncate text-xs text-slate-500">
                {item.leading_stock}
                {item.leading_stock_pct !== 0 && (
                  <span className={item.leading_stock_pct > 0 ? 'text-rose-500' : 'text-green-600'}>
                    {' '}{item.leading_stock_pct > 0 ? '+' : ''}{item.leading_stock_pct.toFixed(1)}%
                  </span>
                )}
                {' · '}涨{item.rise_count}/跌{item.fall_count}
              </span>

              {/* 涨跌幅色块 */}
              <span
                className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium tabular-nums ${pctBg(item.change_pct)}`}
              >
                {item.change_pct > 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      </PageCard>
    </StateWrapper>
  );
}
