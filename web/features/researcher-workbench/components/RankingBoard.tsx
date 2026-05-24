/**
 * 5A 右侧 AI 战绩榜单
 *
 * 对标设计稿：
 *  - 头部 segmented：今日收益率 / 本月收益率
 *  - 5 行排行：第 1-2 名金色序号、第 3-5 灰色
 *  - 每行：序号 + 流派色头像 + 名称 + 等级 chip + 今日/月收益率 + 总资产（万）
 */
'use client';

import { Skeleton, Empty } from 'antd';
import { PageCard } from '@/components/ui/page-card';
import { ResearcherAvatar } from './ResearcherAvatar';
import type { PublicRankItem, RankSortBy } from '@/types/researcher-workbench';

interface Props {
  rankings: PublicRankItem[];
  loading: boolean;
  sortBy: RankSortBy;
  onSortChange: (value: RankSortBy) => void;
  onSelect?: (researcherId: string) => void;
}

function formatPct(value: number) {
  const pct = (value * 100).toFixed(2);
  return value > 0 ? `+${pct}%` : `${pct}%`;
}

function yieldColor(value: number) {
  if (value > 0) return 'text-up-600';
  if (value < 0) return 'text-down-600';
  return 'text-ink-500';
}

function formatWan(value: number) {
  return (value / 10000).toFixed(2);
}

export function RankingBoard({ rankings, loading, sortBy, onSortChange, onSelect }: Props) {
  return (
    <PageCard
      accent="gold"
      title={
        <span className="inline-flex items-baseline gap-2">
          AI 战绩榜单
          <span className="text-[11px] font-normal text-ink-400">公开研究员模拟交易排名</span>
        </span>
      }
      extra={
        <div className="inline-flex rounded-md bg-ink-25 p-0.5 text-[11px]">
          <button
            type="button"
            onClick={() => onSortChange('today')}
            className={[
              'rounded px-2 py-0.5 font-semibold transition-colors',
              sortBy === 'today' ? 'bg-gold-500 text-white' : 'text-ink-500 hover:text-ink-700',
            ].join(' ')}
          >
            今日收益率
          </button>
          <button
            type="button"
            onClick={() => onSortChange('month')}
            className={[
              'rounded px-2 py-0.5 font-semibold transition-colors',
              sortBy === 'month' ? 'bg-gold-500 text-white' : 'text-ink-500 hover:text-ink-700',
            ].join(' ')}
          >
            本月收益率
          </button>
        </div>
      }
      flush
    >
      <div className="px-2 py-1.5">
        {loading ? (
          <div className="px-3 py-2">
            <Skeleton active paragraph={{ rows: 5 }} title={false} />
          </div>
        ) : rankings.length === 0 ? (
          <div className="px-3 py-8">
            <Empty description="暂无排名数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
        ) : (
          rankings.slice(0, 5).map((item, idx) => {
            const rank = idx + 1;
            const isTop = rank <= 2;
            return (
              <button
                key={item.researcher_id}
                type="button"
                onClick={() => onSelect?.(item.researcher_id)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-ink-25 transition-colors"
              >
                <span
                  className={[
                    'serif w-4 shrink-0 text-center text-[14px] font-bold tnum',
                    isTop ? 'text-gold-600' : 'text-ink-300',
                  ].join(' ')}
                >
                  {rank}
                </span>
                <ResearcherAvatar name={item.name} size="md" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <b className="truncate text-[13px] text-ink-900">{item.name}</b>
                    {item.risk_note && (
                      <span className="shrink-0 rounded bg-brand-50 px-1.5 py-px text-[10px] font-semibold text-brand-700">
                        {item.risk_note}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[11px]">
                    <span className={['tnum font-semibold', yieldColor(item.today_yield_rate)].join(' ')}>
                      今日 {formatPct(item.today_yield_rate)}
                    </span>
                    <span className="text-ink-300">·</span>
                    <span className={['tnum', yieldColor(item.month_yield_rate)].join(' ')}>
                      月 {formatPct(item.month_yield_rate)}
                    </span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="serif tnum text-[16px] font-bold text-ink-900">
                    {formatWan(item.total_asset)}
                    <span className="ml-0.5 text-[11px] font-normal text-ink-500">万</span>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </PageCard>
  );
}
