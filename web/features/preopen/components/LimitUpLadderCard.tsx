/**
 * 涨停天梯 —— 按连板数分层展示
 *
 * 布局：每层一行，左侧"N连M"标签，右侧流式排列股票标签（名称+涨跌幅+行业）
 * 数据流：useLimitUpLadderQuery → 后端 /preopen/limit-up-ladder
 */
'use client';

import { useMemo } from 'react';
import { Tag, Typography } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useLimitUpLadderQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { LimitUpLadderItem } from '@/types/preopen';

const { Text } = Typography;

/** 按连板数分组 */
function groupByLadder(items: LimitUpLadderItem[]) {
  const map = new Map<number, LimitUpLadderItem[]>();
  for (const item of items) {
    const arr = map.get(item.ladder_level) ?? [];
    arr.push(item);
    map.set(item.ladder_level, arr);
  }
  // 按连板数降序
  return [...map.entries()].sort((a, b) => b[0] - a[0]);
}

export function LimitUpLadderCard() {
  const { data, isLoading, error } = useLimitUpLadderQuery();
  const groups = useMemo(() => groupByLadder(data ?? []), [data]);

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="涨停天梯">
      <PageCard title="涨停天梯">
        <div className="divide-y divide-slate-100">
          {groups.map(([level, stocks]) => (
            <div key={level} className="flex gap-3 py-2.5">
              {/* 左侧层级标签 */}
              <div className="flex w-20 shrink-0 items-start gap-1 pt-0.5">
                <Tag color="volcano" className="!mr-0 font-bold">
                  {level}连{level + 1}
                </Tag>
                <Text type="secondary" className="text-xs">
                  {stocks.length}只
                </Text>
              </div>

              {/* 右侧股票流式排列 */}
              <div className="flex flex-1 flex-wrap gap-x-4 gap-y-1.5">
                {stocks.map((s) => (
                  <span key={s.symbol} className="inline-flex items-center gap-1 text-[13px]">
                    <span className="font-medium text-rose-600">{s.name}</span>
                    <span className="text-slate-400">({s.reason || s.symbol})</span>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </PageCard>
    </StateWrapper>
  );
}
