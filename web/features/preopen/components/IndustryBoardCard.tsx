/**
 * 行业板块涨跌卡片 —— 同花顺行业板块实时涨跌
 *
 * 设计目标（对照设计稿）：
 *   板块名 + 领涨股
 *   涨跌幅 bar（相对最大涨幅归一化）
 *   涨跌幅文字（红涨绿跌）
 *
 * 数据流：useIndustryBoardsQuery → 后端 /preopen/industry-boards
 */
'use client';

import { Skeleton } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useIndustryBoardsQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { IndustryBoardItem } from '@/types/preopen';

export function IndustryBoardCard() {
  const { data, isLoading, error } = useIndustryBoardsQuery();

  if (isLoading) {
    return (
      <PageCard title="板块涨跌">
        <Skeleton active paragraph={{ rows: 8 }} />
      </PageCard>
    );
  }

  const items = (data ?? []).slice(0, 10);
  // 归一化：以最大绝对涨跌幅做 100%
  const maxAbs = items.reduce((m, x) => Math.max(m, Math.abs(x.change_pct)), 0.01);

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="板块涨跌">
      <PageCard title="板块涨跌" extra={<span className="cursor-pointer">看全部</span>}>
        <div className="flex flex-col">
          {items.map((item: IndustryBoardItem) => {
            const isUp = item.change_pct > 0;
            const isDown = item.change_pct < 0;
            const widthPct = Math.min(100, (Math.abs(item.change_pct) / maxAbs) * 100);
            const barColor = isUp ? 'bg-up-500' : isDown ? 'bg-down-500' : 'bg-ink-200';
            const pctColor = isUp ? 'text-up-600' : isDown ? 'text-down-600' : 'text-ink-600';

            return (
              <div
                key={item.name}
                className="group grid grid-cols-[1fr_70px_60px] items-center gap-2.5 rounded-md px-2 py-2 transition-colors hover:bg-ink-25 sm:gap-3"
              >
                {/* 板块名 + 领涨股 */}
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-medium text-ink-800">{item.name}</div>
                  <div className="mt-0.5 truncate text-[11px] text-ink-400">
                    {item.leading_stock ? (
                      <>
                        领涨 · {item.leading_stock}
                        {item.leading_stock_pct !== 0 && (
                          <span className={item.leading_stock_pct > 0 ? 'text-up-600' : 'text-down-600'}>
                            {' '}
                            {item.leading_stock_pct > 0 ? '+' : ''}
                            {item.leading_stock_pct.toFixed(1)}%
                          </span>
                        )}
                      </>
                    ) : (
                      <>涨 {item.rise_count} / 跌 {item.fall_count}</>
                    )}
                  </div>
                </div>

                {/* 进度条 */}
                <div className="h-1 overflow-hidden rounded-full bg-ink-25">
                  <div
                    className={`h-full rounded-full transition-all ${barColor}`}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>

                {/* 涨跌幅文字 */}
                <div className={`text-right text-[13px] font-semibold tabular-nums ${pctColor}`}>
                  {isUp ? '+' : ''}
                  {item.change_pct.toFixed(2)}%
                </div>
              </div>
            );
          })}
        </div>
      </PageCard>
    </StateWrapper>
  );
}
