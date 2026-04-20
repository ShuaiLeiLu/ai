/**
 * 异动名单卡片 —— 尾盘异动 / 严重波动 Tabs 切换
 *
 * 布局：Tabs 切换 + 紧凑列表，每行显示名称、代码、涨跌幅、备注
 * 数据流：useAnomaliesQuery → 后端 /preopen/anomalies
 */
'use client';

import { Tabs } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useAnomaliesQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { AnomalyItem, AnomalyOverview } from '@/types/preopen';

/** 涨跌幅颜色 */
const pctCls = (v: number) => (v > 0 ? 'text-rose-600' : v < 0 ? 'text-green-600' : 'text-slate-600');

/** 风险标签映射 */
const tagLabel: Record<string, string> = {
  consecutive_limit_up: '连板',
  abnormal_volatility: '异常波动',
  st_risk: 'ST',
  high_turnover: '高换手',
};

/** 紧凑列表子组件 */
function AnomalyList({ items }: { items: AnomalyItem[] }) {
  if (!items.length) return <div className="py-4 text-center text-xs text-slate-400">暂无数据</div>;

  return (
    <div className="divide-y divide-slate-50">
      {items.map((item) => (
        <div key={item.symbol} className="flex items-center gap-2 py-2 transition-colors hover:bg-slate-50">
          {/* 名称 + 代码 */}
          <span className="font-medium text-sm text-slate-800">{item.name}</span>
          <span className="text-xs text-slate-400">{item.symbol}</span>

          {/* 标签 */}
          <div className="flex flex-1 gap-1">
            {item.risk_tags.map((t) => (
              <span
                key={`${item.symbol}-${t}`}
                className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-600"
              >
                {tagLabel[t] || t}
              </span>
            ))}
          </div>

          {/* 涨跌幅 */}
          <span className={`shrink-0 text-sm font-medium tabular-nums ${pctCls(item.change_pct)}`}>
            {item.change_pct > 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  );
}

export function AnomaliesCard() {
  const { data, isLoading, error } = useAnomaliesQuery();
  const overview: AnomalyOverview | undefined = data;

  const tabItems = [
    {
      key: 'late',
      label: `尾盘异动 (${overview?.tail_session_moves.length ?? 0})`,
      children: <AnomalyList items={overview?.tail_session_moves ?? []} />,
    },
    {
      key: 'severe',
      label: `严重异常 (${overview?.severe_volatility.length ?? 0})`,
      children: <AnomalyList items={overview?.severe_volatility ?? []} />,
    },
  ];

  return (
    <StateWrapper
      data={overview}
      isLoading={isLoading}
      error={error}
      title="异动名单"
      nonTradingDayMessage={overview && !overview.calendar.is_trading_day ? overview.calendar.notice : undefined}
    >
      <PageCard title="异动名单">
        <Tabs defaultActiveKey="late" items={tabItems} size="small" />
      </PageCard>
    </StateWrapper>
  );
}
