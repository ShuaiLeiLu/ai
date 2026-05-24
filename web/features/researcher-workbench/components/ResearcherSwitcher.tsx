/**
 * 5A 顶部 横向研究员切换 Tab
 *
 * 对标设计稿：
 *  - 左侧 "切 换 研 究 员"（字间距 2px）
 *  - 横向滚动 chip 列表：总览 + 已雇佣研究员 + + 招募/创建
 *  - 选中态：brand-50 底 + brand-200 边 + brand-700 字
 *  - 每个研究员 chip：头像 24×24 + 名称 + 今日收益率 badge
 */
'use client';

import Link from 'next/link';
import { ResearcherAvatar } from './ResearcherAvatar';
import { routes } from '@/lib/constants/routes';
import type { HiredResearcher } from '@/types/researcher-workbench';

/** 收益率展示色 */
function rateColor(value: number | null): string {
  if (value === null) return 'bg-ink-25 text-ink-400';
  if (value > 0) return 'bg-up-50 text-up-600';
  if (value < 0) return 'bg-down-50 text-down-600';
  return 'bg-ink-25 text-ink-400';
}

/** 格式化收益率 */
function fmt(value: number | null): string {
  if (value === null) return '—';
  const pct = (value * 100).toFixed(2);
  return value > 0 ? `+${pct}%` : `${pct}%`;
}

interface Props {
  researchers: HiredResearcher[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
}

export function ResearcherSwitcher({ researchers, activeId, onSelect }: Props) {
  return (
    <div className="flex items-center gap-3 border-b border-dashed border-ink-100 pb-4">
      <span className="hidden sm:inline text-[11px] tracking-[2px] text-ink-400 shrink-0">
        切 换 研 究 员
      </span>
      <div className="flex flex-1 gap-2 overflow-x-auto scrollbar-thin pb-1">
        {/* 总览 */}
        <button
          type="button"
          onClick={() => onSelect(null)}
          className={[
            'inline-flex shrink-0 items-center gap-1.5 rounded-full pl-1.5 pr-3 py-1 transition-colors',
            activeId === null
              ? 'bg-brand-50 border border-brand-200'
              : 'bg-white border border-ink-50 hover:border-ink-100',
          ].join(' ')}
        >
          <span className="grid h-6 w-6 place-items-center rounded-full bg-ink-100 text-[12px] font-bold text-ink-700">
            📊
          </span>
          <b
            className={[
              'text-[12.5px]',
              activeId === null ? 'text-brand-700' : 'text-ink-700',
            ].join(' ')}
          >
            总览
          </b>
        </button>

        {/* 研究员列表 */}
        {researchers.map((r) => {
          const active = r.researcher_id === activeId;
          return (
            <button
              key={r.researcher_id}
              type="button"
              onClick={() => onSelect(r.researcher_id)}
              className={[
                'inline-flex shrink-0 items-center gap-1.5 rounded-full pl-1.5 pr-3 py-1 transition-colors',
                active
                  ? 'bg-brand-50 border border-brand-200'
                  : 'bg-white border border-ink-50 hover:border-ink-100',
              ].join(' ')}
            >
              <ResearcherAvatar name={r.name} size="sm" />
              <span
                className={[
                  'text-[12.5px]',
                  active ? 'font-semibold text-brand-700' : 'text-ink-700',
                ].join(' ')}
              >
                {r.name}
              </span>
              <span
                className={[
                  'rounded px-1.5 py-px text-[10px] font-semibold tnum',
                  rateColor(r.today_yield_rate),
                ].join(' ')}
              >
                {fmt(r.today_yield_rate)}
              </span>
            </button>
          );
        })}

        {/* 招募/创建 */}
        <Link
          href={routes.labTalentMarket}
          className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-ink-100 bg-white px-3 py-1 text-ink-400 hover:border-brand-200 hover:text-brand-600 transition-colors"
        >
          <span className="text-sm leading-none">+</span>
          <span className="text-[12px]">招募/创建</span>
        </Link>
      </div>
    </div>
  );
}
