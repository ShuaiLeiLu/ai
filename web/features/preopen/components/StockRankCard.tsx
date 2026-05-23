/**
 * 涨跌榜卡片 —— 涨/跌 两个 Segmented 切换 + 紧凑表格
 *
 * 布局：顶部红/绿切换按钮 + 表格（代码、名称、涨跌幅、最新价、成交额、换手率）
 * 数据流：useStockRankQuery(direction) → 后端 /preopen/stock-rank?direction=up|down
 */
'use client';

import { useState } from 'react';
import { Segmented, Skeleton } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useStockRankQuery } from '@/features/preopen/hooks';
import type { StockRankItem } from '@/types/preopen';

/** 涨跌幅颜色 */
const pctColor = (v: number) => (v > 0 ? 'text-rose-600' : v < 0 ? 'text-green-600' : 'text-slate-600');

/** 金额格式化 */
const fmtAmt = (v: number) => {
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
};

/** 表格头 */
const TH = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <th className={`px-2 py-1.5 text-left text-[11px] font-medium text-slate-400 ${className}`}>{children}</th>
);

/** 内部表格组件 */
function RankTable({ direction }: { direction: 'up' | 'down' }) {
  const { data, isLoading } = useStockRankQuery(direction);

  if (isLoading) return <Skeleton active paragraph={{ rows: 6 }} />;
  if (!data?.length) return <div className="py-6 text-center text-xs text-slate-400">暂无数据</div>;

  return (
    <div className="-mx-2 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[460px] text-[13px]">
        <thead>
          <tr className="border-b border-slate-100">
            <TH>代码</TH>
            <TH>名称</TH>
            <TH className="text-right">涨跌幅</TH>
            <TH className="hidden text-right sm:table-cell">最新价</TH>
            <TH className="hidden text-right md:table-cell">成交额</TH>
            <TH className="hidden text-right md:table-cell">换手率</TH>
          </tr>
        </thead>
        <tbody>
          {data.map((s: StockRankItem) => (
            <tr key={s.symbol} className="border-b border-slate-50 transition-colors hover:bg-slate-50">
              <td className="whitespace-nowrap px-2 py-1.5 text-slate-500">{s.symbol}</td>
              <td className="whitespace-nowrap px-2 py-1.5 font-medium text-slate-800">{s.name}</td>
              <td className={`whitespace-nowrap px-2 py-1.5 text-right font-medium tabular-nums ${pctColor(s.change_pct)}`}>
                {s.change_pct > 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
              </td>
              <td className="hidden whitespace-nowrap px-2 py-1.5 text-right tabular-nums text-slate-600 sm:table-cell">{s.price.toFixed(2)}</td>
              <td className="hidden whitespace-nowrap px-2 py-1.5 text-right text-slate-500 md:table-cell">{fmtAmt(s.amount)}</td>
              <td className="hidden whitespace-nowrap px-2 py-1.5 text-right text-slate-500 md:table-cell">{s.turnover_ratio.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StockRankCard() {
  const [direction, setDirection] = useState<'up' | 'down'>('up'); // 涨/跌方向

  return (
    <PageCard
      title="涨跌榜"
      extra={
        <Segmented
          value={direction}
          onChange={(v) => setDirection(v as 'up' | 'down')}
          options={[
            { label: <span className="text-rose-600">涨</span>, value: 'up' },
            { label: <span className="text-green-600">跌</span>, value: 'down' },
          ]}
          size="small"
        />
      }
    >
      <RankTable direction={direction} />
    </PageCard>
  );
}
