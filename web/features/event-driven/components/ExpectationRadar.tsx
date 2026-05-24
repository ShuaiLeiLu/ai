/** 预期差雷达 · 由市场快照规则派生 */
import { PageCard } from '@/components/ui/page-card';
import type { ExpectationGap } from '@/features/event-driven/types';

interface Props {
  items: ExpectationGap[];
}

export function ExpectationRadar({ items }: Props) {
  return (
    <PageCard title="🎯 预期差雷达 · 市场快照派生" accent="gold">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {items.map((g) => {
          const isUnder = g.direction === 'undervalued';
          return (
            <div
              key={g.id}
              className={[
                'border-l-[3px] px-3.5 py-2.5',
                isUnder ? 'border-up-500 bg-up-50' : 'border-down-500 bg-down-50',
              ].join(' ')}
            >
              <div className="flex items-center gap-2 text-[11px]">
                <span
                  className={
                    isUnder
                      ? 'rounded bg-up-500 px-1.5 py-[1px] text-white'
                      : 'rounded bg-down-500 px-1.5 py-[1px] text-white'
                  }
                >
                  {isUnder ? '被低估' : '被高估'}
                </span>
                <span className="text-ink-400">{g.target_label}</span>
              </div>
              <div className="serif mt-1.5 text-[13.5px] font-bold text-ink-900">{g.title}</div>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-[11px] text-ink-500">幅度</span>
                <span
                  className={
                    isUnder
                      ? 'tnum text-[13px] font-bold text-up-600'
                      : 'tnum text-[13px] font-bold text-down-600'
                  }
                >
                  {g.magnitude_pct > 0 ? '+' : ''}
                  {g.magnitude_pct.toFixed(1)}%
                </span>
              </div>
              <p className="mt-1 text-[11.5px] leading-[1.7] text-ink-600">{g.reasoning}</p>
            </div>
          );
        })}
      </div>
    </PageCard>
  );
}
