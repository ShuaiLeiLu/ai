/** 盘口故事（今日/昨日切换） */
import { useState } from 'react';

import { PageCard } from '@/components/ui/page-card';
import type { MarketStory as MarketStoryData } from '@/features/event-driven/types';

interface Props {
  data: MarketStoryData;
}

type Tab = 'today' | 'yesterday';

export function MarketStory({ data }: Props) {
  const [tab, setTab] = useState<Tab>('today');
  const segments = tab === 'today' ? data.today : data.yesterday;

  return (
    <PageCard
      title={`📊 ${tab === 'today' ? '今日' : '昨日'}盘口故事`}
      subtitle={`${segments.length} 段叙事`}
      accent="brand"
      extra={
        <div className="flex gap-1 text-[11.5px]">
          {(['today', 'yesterday'] as Tab[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setTab(k)}
              className={[
                'rounded px-2 py-[3px] transition',
                tab === k
                  ? 'bg-brand-600 font-semibold text-white'
                  : 'text-ink-500 hover:text-brand-600',
              ].join(' ')}
            >
              {k === 'today' ? '今日' : '昨日'}
            </button>
          ))}
        </div>
      }
    >
      {segments.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-ink-400">暂无叙事</div>
      ) : (
        segments.map((s, i) => (
          <div
            key={`${tab}-${s.time_range}`}
            className={[
              'grid gap-3.5 py-2',
              i !== segments.length - 1 ? 'border-b border-dashed border-ink-50' : '',
              'grid-cols-[90px_1fr]',
            ].join(' ')}
          >
            <div className="serif text-[14px] font-bold text-brand-700">{s.time_range}</div>
            <div>
              <div className="text-[13.5px] font-semibold text-ink-900">{s.headline}</div>
              <p className="mt-0.5 text-[12px] leading-[1.7] text-ink-600">{s.narrative}</p>
            </div>
          </div>
        ))
      )}
    </PageCard>
  );
}
