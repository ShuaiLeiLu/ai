/**
 * 研究员异动提示卡片 —— 金色 accent 时间轴样式
 *
 * 设计目标（对照设计稿）：
 *   金色强调条 · 「研究员异动提示」标题
 *   每条：左侧风险等级圆点（高/中/低） + 标题 + 描述 + 时间
 *
 * 数据流：useAnomaliesQuery → 后端 /preopen/anomalies
 *   合并 tail_session_moves 与 severe_volatility 后按 change_pct 绝对值排序
 */
'use client';

import { useState } from 'react';
import { Skeleton } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useAnomaliesQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { AnomalyItem, AnomalyOverview } from '@/types/preopen';

/** 风险标签映射 */
const tagLabel: Record<string, string> = {
  consecutive_limit_up: '连板',
  abnormal_volatility: '异常波动',
  st_risk: 'ST',
  high_turnover: '高换手',
};

/** 风险等级：高/中/低 */
function levelOf(item: AnomalyItem): 'high' | 'mid' | 'low' {
  const a = Math.abs(item.change_pct);
  if (a >= 7 || item.category === 'severe-volatility') return 'high';
  if (a >= 3) return 'mid';
  return 'low';
}

/** 时间占位 —— 后端未提供精确时间戳，按等级生成相对时间 */
function relTime(idx: number): string {
  const minsAgo = 5 + idx * 7;
  const now = new Date();
  const t = new Date(now.getTime() - minsAgo * 60000);
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`;
}

const dotCls: Record<'high' | 'mid' | 'low', string> = {
  high: 'bg-up-500 shadow-[0_0_0_3px_rgba(216,69,58,.15)]',
  mid: 'bg-gold-500 shadow-[0_0_0_3px_rgba(200,154,58,.15)]',
  low: 'bg-ink-200',
};

function AnomalyRow({ item, idx }: { item: AnomalyItem; idx: number }) {
  const lvl = levelOf(item);
  const isUp = item.change_pct > 0;
  return (
    <div className="group flex items-start gap-2.5 rounded-md px-2 py-2 transition-colors hover:bg-ink-25">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dotCls[lvl]}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[13px] font-semibold text-ink-800">{item.name}</span>
          {item.is_new && (
            <span className="rounded bg-up-50 px-1 py-px text-[10px] font-bold text-up-600">NEW</span>
          )}
          <span
            className={`shrink-0 text-[12px] font-semibold tabular-nums ${
              isUp ? 'text-up-600' : 'text-down-600'
            }`}
          >
            {isUp ? '+' : ''}
            {item.change_pct.toFixed(2)}%
          </span>
        </div>
        <div className="mt-0.5 flex items-center gap-1.5 truncate text-[11px] text-ink-400">
          {item.risk_tags.slice(0, 2).map((t) => (
            <span
              key={t}
              className="rounded bg-gold-50 px-1.5 py-0.5 text-[10px] text-gold-600"
            >
              {tagLabel[t] || t}
            </span>
          ))}
          <span className="truncate">
            {item.risk_type ? `${item.risk_type} · ` : ''}
            {item.note || `${item.symbol} · 换手 ${item.turnover_ratio.toFixed(1)}%`}
            {item.risk_window ? ` · ${item.risk_window}` : ''}
          </span>
        </div>
      </div>
      <span className="shrink-0 self-start text-[10.5px] text-ink-200 tabular-nums">{relTime(idx)}</span>
    </div>
  );
}

export function AnomaliesCard() {
  const [tab, setTab] = useState<'monitor' | 'risk'>('monitor');
  const { data, isLoading, error } = useAnomaliesQuery();
  const overview: AnomalyOverview | undefined = data ?? undefined;

  const monitorItems = [...(overview?.tail_session_moves ?? [])].sort(
    (a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct),
  );
  const riskItems = [...(overview?.severe_volatility ?? [])].sort(
    (a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct),
  );
  const visibleItems = tab === 'monitor' ? monitorItems : riskItems;

  return (
    <StateWrapper
      data={overview}
      isLoading={isLoading}
      error={error}
      title="研究员异动提示"
      nonTradingDayMessage={overview && !overview.calendar.is_trading_day ? overview.calendar.notice : undefined}
    >
      <PageCard
        title="异动监控与风险提示"
        accent="gold"
        extra={
          <div className="inline-flex rounded-lg bg-ink-25 p-0.5 text-[11px]">
            {[
              { key: 'monitor' as const, label: `异动监控 ${monitorItems.length}` },
              { key: 'risk' as const, label: `风险提示 ${riskItems.length}` },
            ].map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                className={[
                  'rounded-md px-2 py-1 font-semibold transition-colors',
                  tab === item.key ? 'bg-white text-gold-700 shadow-sm' : 'text-ink-400 hover:text-ink-700',
                ].join(' ')}
              >
                {item.label}
              </button>
            ))}
          </div>
        }
        density="compact"
      >
        <div className="mb-2 rounded-lg bg-gold-50 px-3 py-2 text-[11.5px] leading-relaxed text-gold-700">
          {tab === 'monitor'
            ? '监控尾盘拉升、炸板、高换手等异动，用于观察资金短线攻击方向。'
            : '提示连续异常波动、跌停扩散与交易所监管风险，新入风险项会标记 NEW。'}
        </div>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 5 }} />
        ) : visibleItems.length ? (
          <div className="flex flex-col gap-0.5">
            {visibleItems.slice(0, 6).map((item, i) => (
              <AnomalyRow key={`${item.symbol}-${i}`} item={item} idx={i} />
            ))}
          </div>
        ) : (
          <div className="py-6 text-center text-[12px] text-ink-400">
            {tab === 'monitor' ? '暂无异常波动股票' : '暂无风险提示股票'}
          </div>
        )}
      </PageCard>
    </StateWrapper>
  );
}
