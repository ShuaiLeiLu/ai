/**
 * 涨停天梯 ——「首板 / 连板 / 3连 / 5连 / 7+」5 格徽章 + 摘要
 *
 * 设计目标（对照设计稿）：
 *   顶部 5 格徽章（每格显示该层级股票数量）
 *   底部统计摘要：涨停 X 家 · 连板 X 家 · 最高度 X 板 · 炸板率
 *
 * 数据流：useLimitUpLadderQuery → 后端 /preopen/limit-up-ladder
 */
'use client';

import { useMemo } from 'react';
import { Skeleton } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useLimitUpLadderQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { LimitUpLadderItem } from '@/types/preopen';

/** 把所有股票按层级分桶到 5 个固定格子 */
function bucketize(items: LimitUpLadderItem[]) {
  // [1, 2, 3, 5, 7+]
  const buckets: { key: string; label: string; min: number; max: number; gold?: boolean; items: LimitUpLadderItem[] }[] = [
    { key: 'b1', label: '首板', min: 1, max: 1, items: [] },
    { key: 'b2', label: '连板', min: 2, max: 2, items: [] },
    { key: 'b3', label: '3 连', min: 3, max: 4, items: [] },
    { key: 'b5', label: '5 连', min: 5, max: 6, items: [] },
    { key: 'b7', label: '7+', min: 7, max: 999, gold: true, items: [] },
  ];
  for (const it of items) {
    const b = buckets.find((bb) => it.ladder_level >= bb.min && it.ladder_level <= bb.max);
    if (b) b.items.push(it);
  }
  return buckets;
}

export function LimitUpLadderCard() {
  const { data, isLoading, error } = useLimitUpLadderQuery();
  const items = data ?? [];
  const buckets = useMemo(() => bucketize(items), [items]);

  // 统计指标
  const total = items.length;
  const consecutive = items.filter((i) => i.ladder_level >= 2).length;
  const peak = items.reduce((m, i) => Math.max(m, i.ladder_level), 0);
  const peakStock = items.find((i) => i.ladder_level === peak);

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="涨停天梯">
      <PageCard title="涨停天梯" accent="up" extra={<span className="cursor-pointer">详情</span>}>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <>
            {/* 5 格徽章 */}
            <div className="grid grid-cols-5 gap-2">
              {buckets.map((b) => (
                <div
                  key={b.key}
                  className={[
                    'rounded-lg border px-2 py-2 text-center',
                    b.gold
                      ? 'border-gold-300 bg-gold-warm text-gold-600'
                      : 'border-up-100 bg-up-50 text-up-600',
                  ].join(' ')}
                >
                  <div className="tabular-nums text-[18px] font-bold leading-tight">
                    {b.items.length}
                  </div>
                  <div className="mt-0.5 text-[10.5px] text-ink-400">{b.label}</div>
                </div>
              ))}
            </div>

            {/* 摘要 */}
            <div className="mt-3.5 border-t border-dashed border-ink-50 pt-3 text-[12px] leading-[1.7] text-ink-600">
              今日涨停 <b className="text-up-600">{total} 家</b>，连板 <b>{consecutive} 家</b>。
              {peakStock ? (
                <>
                  <br />
                  最高度：<b>{peakStock.name} {peak} 板</b>
                </>
              ) : null}
            </div>
          </>
        )}
      </PageCard>
    </StateWrapper>
  );
}
