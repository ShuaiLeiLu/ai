/** 题材列表侧栏（4 个状态筛选 Tab） */
import { useMemo, useState } from 'react';

import type { ThemeListItem, ThemeStatus } from '@/features/event-driven/types';

interface Props {
  themes: ThemeListItem[];
  activeId: string | undefined;
  onSelect: (id: string) => void;
  generatedAt?: string;
}

type FilterKey = 'all' | ThemeStatus;

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'today_hot', label: '今日火爆' },
  { key: 'yesterday_hot', label: '昨日火爆' },
  { key: 'waiting', label: '暂避锋芒' },
  { key: 'lurking', label: '潜伏中' },
];

const STATUS_STYLE: Record<ThemeStatus, { label: string; className: string }> = {
  today_hot: { label: '今日火爆', className: 'bg-up-500 text-white' },
  yesterday_hot: { label: '昨日火爆', className: 'bg-gold-500 text-white' },
  waiting: { label: '暂避锋芒', className: 'bg-ink-400 text-white' },
  lurking: { label: '潜伏中', className: 'bg-[#6c3aed] text-white' },
};

export function ThemeListSidebar({ themes, activeId, onSelect, generatedAt }: Props) {
  const [filter, setFilter] = useState<FilterKey>('all');

  const visible = useMemo(() => {
    if (filter === 'all') return themes;
    return themes.filter((t) => t.status === filter);
  }, [themes, filter]);

  return (
    <aside className="flex h-full flex-col overflow-hidden rounded-2xl border border-ink-50 bg-white">
      <div className="px-4 pb-2 pt-4">
        <div className="serif text-[15px] font-bold text-ink-900">
          题材掘金{' '}
          <span className="text-[11px] font-normal text-ink-400">
            {generatedAt ? `${generatedAt} · ` : ''}共 {themes.length} 个题材
          </span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1 text-[11.5px]">
          {FILTERS.map((f) => {
            const active = f.key === filter;
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                className={[
                  'rounded px-2.5 py-[3px] transition',
                  active ? 'bg-gold-500 font-semibold text-white' : 'text-ink-500 hover:text-brand-600',
                ].join(' ')}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2.5 pb-3">
        {visible.length === 0 && (
          <div className="px-3 py-6 text-center text-[12px] text-ink-400">该筛选下暂无题材</div>
        )}
        {visible.map((t) => {
          const active = t.id === activeId;
          const statusStyle = STATUS_STYLE[t.status];
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelect(t.id)}
              className={[
                'mb-1.5 block w-full rounded-[10px] px-3 py-2.5 text-left transition',
                active
                  ? 'border border-gold-300 bg-gradient-to-br from-[#fdf4d8] to-[#fcefc6]'
                  : 'border border-transparent hover:bg-ink-25',
              ].join(' ')}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-ink-400">{t.rank}</span>
                  <b className="text-[13px] text-ink-900">{t.name}</b>
                </div>
                <span className={`rounded px-1.5 py-[1px] text-[10.5px] ${statusStyle.className}`}>
                  {statusStyle.label}
                </span>
              </div>
              <div className="mt-1 text-[11px] text-ink-500">
                {t.limit_up_count} 个涨停 · {t.event_count} 个事件
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
