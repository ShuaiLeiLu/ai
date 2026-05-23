'use client';

/**
 * 模拟交易页面（顶层入口）
 *
 * 信息层级：
 *   ① 顶部资产 Hero（StatCard 矩阵）
 *   ② 持仓 PageCard
 *   ③ 成交记录 PageCard
 *
 * 注：旧版直接堆 antd Card / Statistic，视觉与设计令牌脱节。此次升级到统一基元。
 */

import { Empty, Skeleton, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatCard } from '@/components/ui/stat-card';
import { useTradingAccount, useTradingPositions, useTradingRecords } from '@/features/trading/hooks';
import type { PositionItem, TradeRecord } from '@/types/trading';

/** 金额格式化（人民币 + 千分位） */
function money(value: number): string {
  return `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** 涨跌色（红涨绿跌） */
const pnlClass = (v: number) =>
  v > 0 ? 'text-up-600' : v < 0 ? 'text-down-600' : 'text-ink-600';

const positionColumns: ColumnsType<PositionItem> = [
  { title: '股票', dataIndex: 'name', key: 'name', width: 110 },
  { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 90, responsive: ['sm'] },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', align: 'right', width: 80 },
  { title: '成本价', dataIndex: 'cost_price', key: 'cost_price', align: 'right', width: 90, responsive: ['md'] },
  { title: '现价', dataIndex: 'current_price', key: 'current_price', align: 'right', width: 90 },
  {
    title: '盈亏',
    dataIndex: 'pnl',
    key: 'pnl',
    align: 'right',
    width: 110,
    render: (value: number) => (
      <span className={`tabular-nums font-medium ${pnlClass(value)}`}>{money(value)}</span>
    ),
  },
];

const recordColumns: ColumnsType<TradeRecord> = [
  {
    title: '时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 110,
    render: (value: string) => (
      <span className="tabular-nums text-ink-600">{dayjs(value).format('MM-DD HH:mm')}</span>
    ),
  },
  { title: '代码', dataIndex: 'symbol', key: 'symbol', width: 100 },
  {
    title: '方向',
    dataIndex: 'side',
    key: 'side',
    width: 80,
    render: (value: string) =>
      value === 'buy' ? (
        <Tag color="red" className="!m-0">买入</Tag>
      ) : (
        <Tag color="green" className="!m-0">卖出</Tag>
      ),
  },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', align: 'right', width: 90, responsive: ['sm'] },
  {
    title: '价格',
    dataIndex: 'price',
    key: 'price',
    align: 'right',
    width: 90,
    render: (value: number) => <span className="tabular-nums">{value?.toFixed?.(2) ?? value}</span>,
  },
];

export function TradingPageClient() {
  const accountQuery = useTradingAccount();
  const positionsQuery = useTradingPositions();
  const recordsQuery = useTradingRecords();
  const loading = accountQuery.isLoading || positionsQuery.isLoading || recordsQuery.isLoading;
  const hasError = accountQuery.isError || positionsQuery.isError || recordsQuery.isError;

  return (
    <div className="space-y-4 sm:space-y-5">
      <SectionHeading
        title="模拟交易"
        subtitle="模拟账户资产、当前持仓和成交记录 · 用于策略验证与收益追踪"
      />

      {loading ? (
        <PageCard>
          <Skeleton active paragraph={{ rows: 6 }} />
        </PageCard>
      ) : null}

      {!loading && hasError ? (
        <PageCard>
          <Empty description="模拟交易数据加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </PageCard>
      ) : null}

      {!loading && !hasError && accountQuery.data ? (
        <>
          {/* 资产 Hero */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard
              label="总资产"
              value={accountQuery.data.total_asset.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
            />
            <StatCard
              label="可用资金"
              value={accountQuery.data.available_cash.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
            />
            <StatCard
              label="持仓市值"
              value={accountQuery.data.holding_value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
            />
            <StatCard
              label="近日盈亏"
              value={accountQuery.data.daily_pnl.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
              direction={accountQuery.data.daily_pnl >= 0 ? 'up' : 'down'}
              hint={accountQuery.data.daily_pnl >= 0 ? '今日盈利' : '今日亏损'}
            />
          </div>

          {/* 持仓 */}
          <PageCard title="当前持仓" flush>
            <div className="overflow-x-auto">
              <Table
                rowKey="symbol"
                columns={positionColumns}
                dataSource={positionsQuery.data ?? []}
                pagination={false}
                size="middle"
                scroll={{ x: 'max-content' }}
              />
            </div>
          </PageCard>

          {/* 成交记录 */}
          <PageCard title="成交记录" flush>
            <div className="overflow-x-auto">
              <Table
                rowKey="trade_id"
                columns={recordColumns}
                dataSource={recordsQuery.data ?? []}
                pagination={false}
                size="middle"
                scroll={{ x: 'max-content' }}
              />
            </div>
          </PageCard>
        </>
      ) : null}
    </div>
  );
}
