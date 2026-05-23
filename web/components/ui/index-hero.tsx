'use client';

import type { ReactNode } from 'react';

export interface IndexQuote {
  /** 指数代码（key） */
  code: string;
  /** 指数名（如「上证指数」） */
  name: string;
  /** 当前点位 */
  value: number;
  /** 涨跌额 */
  change: number;
  /** 涨跌幅（百分比，0.74 表示 +0.74%） */
  changePercent: number;
  /** 迷你折线序列（可选） */
  spark?: number[];
}

interface IndexHeroProps {
  /** 顶部情绪/概览 */
  mood?: {
    label?: ReactNode;
    value: ReactNode;
    sub?: ReactNode;
  };
  /** 指数列表（推荐 3~4 条） */
  quotes: IndexQuote[];
}

function dirOf(pct: number): 'up' | 'down' | 'flat' {
  if (pct > 0) return 'up';
  if (pct < 0) return 'down';
  return 'flat';
}

function fmt(n: number) {
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function buildSpark(values: number[]) {
  if (!values || values.length < 2) return '';
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const step = 100 / (values.length - 1);
  return values
    .map((v, i) => `${(i * step).toFixed(1)},${(22 - ((v - min) / range) * 18).toFixed(1)}`)
    .join(' ');
}

/**
 * 指数 Hero ——「重点位置」横幅
 *
 * 桌面：左侧情绪 + 右侧 3-4 个指数横排
 * 移动：折行为 2 列
 */
export function IndexHero({ mood, quotes }: IndexHeroProps) {
  const cols = quotes.length || 4;
  return (
    <div
      className="relative mb-5 overflow-hidden rounded-2xl border border-ink-50 bg-paper-warm p-4 shadow-card sm:p-5 lg:p-6"
    >
      {/* 装饰光晕 */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(200,154,58,.12), transparent 70%)' }}
      />
      <div
        className="relative grid gap-4 sm:gap-6"
        style={{
          gridTemplateColumns: mood
            ? `minmax(0, 1.3fr) repeat(${cols}, minmax(0, 1fr))`
            : `repeat(${cols}, minmax(0, 1fr))`,
        }}
      >
        {mood && (
          <div className="col-span-full sm:col-span-1 sm:border-r sm:border-ink-50/80 sm:pr-4">
            {mood.label && (
              <div className="text-[11px] tracking-[2px] text-ink-400">{mood.label}</div>
            )}
            <div className="mt-1 serif text-2xl font-bold text-brand-700 sm:text-[26px]">
              {mood.value}
            </div>
            {mood.sub && (
              <div className="mt-1.5 text-[12px] leading-relaxed text-ink-600">{mood.sub}</div>
            )}
          </div>
        )}
        {quotes.map((q) => {
          const dir = dirOf(q.changePercent);
          const arrow = dir === 'up' ? '▲' : dir === 'down' ? '▼' : '—';
          const textColor =
            dir === 'up'
              ? 'text-up-600'
              : dir === 'down'
                ? 'text-down-600'
                : 'text-ink-800';
          const strokeColor =
            dir === 'up' ? '#c0362c' : dir === 'down' ? '#1f7f4a' : '#7a7264';
          const sparkPath = buildSpark(q.spark ?? []);
          return (
            <div key={q.code} className="min-w-0">
              <div className="truncate text-[11.5px] tracking-wide text-ink-600">{q.name}</div>
              <div className={['mt-0.5 text-[20px] sm:text-[24px] font-bold leading-tight tnum', textColor].join(' ')}>
                {fmt(q.value)}
              </div>
              <div className={['mt-0.5 text-[11.5px] font-semibold tnum', textColor].join(' ')}>
                {arrow} {q.change >= 0 ? '+' : ''}
                {fmt(q.change)} · {q.changePercent >= 0 ? '+' : ''}
                {q.changePercent.toFixed(2)}%
              </div>
              {sparkPath && (
                <svg
                  className="mt-1 hidden h-[22px] w-full sm:block"
                  viewBox="0 0 100 24"
                  preserveAspectRatio="none"
                >
                  <polyline
                    points={sparkPath}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={1.5}
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
