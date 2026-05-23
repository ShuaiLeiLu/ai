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
          <span className="truncate">{item.note || `${item.symbol} · 换手 ${item.turnover_ratio.toFixed(1)}%`}</span>
        </div>
      </div>
      <span className="shrink-0 self-start text-[10.5px] text-ink-200 tabular-nums">{relTime(idx)}</span>
    </div>
  );
}

export function AnomaliesCard() {
  const { data, isLoading, error } = useAnomaliesQuery();
  const overview: AnomalyOverview | undefined = data ?? undefined;

  // 合并尾盘异动 + 严重异常，按绝对涨跌幅排序
  const merged = ([
    ...(overview?.tail_session_moves ?? []),
    ...(overview?.severe_volatility ?? []),
  ] as AnomalyItem[]).sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));

  return (
    <StateWrapper
      data={overview}
      isLoading={isLoading}
      error={error}
      title="研究员异动提示"
      nonTradingDayMessage={overview && !overview.calendar.is_trading_day ? overview.calendar.notice : undefined}
    >
      <PageCard title="研究员异动提示" accent="gold" extra={<span className="cursor-pointer">全部</span>} density="compact">
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 5 }} />
        ) : merged.length ? (
          <div className="flex flex-col gap-0.5">
            {merged.slice(0, 6).map((item, i) => (
              <AnomalyRow key={`${item.symbol}-${i}`} item={item} idx={i} />
            ))}
          </div>
        ) : (
          <div className="py-6 text-center text-[12px] text-ink-400">暂无异动信号</div>
        )}
      </PageCard>
    </StateWrapper>
  );
}
