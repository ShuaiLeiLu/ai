'use client';

/**
 * 模拟交易页面（顶层入口）
 *
 * 设计要点：
 *   - 顶部研究员切换 Segmented（每个研究员有独立模拟盘）
 *   - 4 列资产 Hero（StatCard）
 *   - 持仓表 + 成交记录
 *
 * 数据流：
 *   - useMineResearchers   获取用户的研究员列表
 *   - useTradingAccount    当前研究员账户概况
 *   - useTradingPositions  当前研究员持仓
 *   - useTradingRecords    当前研究员成交记录
 */

import { useMemo, useState } from 'react';
import { Empty, Segmented, Skeleton, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatCard } from '@/components/ui/stat-card';
import { useMineResearchers } from '@/features/researcher-market/hooks';
import { useTradingAccount, useTradingPositions, useTradingRecords } from '@/features/trading/hooks';
import type { PositionItem, TradeRecord } from '@/types/trading';

/** 金额格式化（人民币 + 千分位） */
function money(value: number, sign = false): string {
  const abs = Math.abs(value);
  const formatted = abs.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const prefix = sign ? (value > 0 ? '+' : value < 0 ? '−' : '') : '';
  return `${prefix}¥${formatted}`;
}

/** 涨跌色（红涨绿跌） */
const pnlClass = (v: number) =>
  v > 0 ? 'text-up-600' : v < 0 ? 'text-down-600' : 'text-ink-600';

const positionColumns: ColumnsType<PositionItem> = [
  {
    title: '股票',
    dataIndex: 'name',
    key: 'name',
    width: 130,
    render: (name: string, row) => (
      <div>
        <div className="font-medium text-ink-800">{name}</div>
        <div className="text-[11px] text-ink-400 tabular-nums">{row.symbol}</div>
      </div>
    ),
  },
  {
    title: '数量',
    dataIndex: 'quantity',
    key: 'quantity',
    align: 'right',
    width: 90,
    render: (v: number) => <span className="tabular-nums">{v.toLocaleString('zh-CN')}</span>,
  },
  {
    title: '成本价',
    dataIndex: 'cost_price',
    key: 'cost_price',
    align: 'right',
    width: 100,
    responsive: ['md'],
    render: (v: number) => <span className="tabular-nums text-ink-600">{v.toFixed(2)}</span>,
  },
  {
    title: '现价',
    dataIndex: 'current_price',
    key: 'current_price',
    align: 'right',
    width: 100,
    render: (v: number) => <span className="tabular-nums">{v.toFixed(2)}</span>,
  },
  {
    title: '市值',
    key: 'market_value',
    align: 'right',
    width: 130,
    responsive: ['lg'],
    render: (_, row) => (
      <span className="tabular-nums text-ink-700">
        {(row.current_price * row.quantity).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
    ),
  },
  {
    title: '盈亏',
    dataIndex: 'pnl',
    key: 'pnl',
    align: 'right',
    width: 120,
    render: (value: number) => (
      <span className={`tabular-nums font-medium ${pnlClass(value)}`}>{money(value, true)}</span>
    ),
  },
  {
    title: '盈亏率',
    key: 'pnl_rate',
    align: 'right',
    width: 100,
    render: (_, row) => {
      const rate = row.cost_price ? ((row.current_price - row.cost_price) / row.cost_price) * 100 : 0;
      return (
        <span className={`tabular-nums font-semibold ${pnlClass(rate)}`}>
          {rate > 0 ? '+' : ''}
          {rate.toFixed(2)}%
        </span>
      );
    },
  },
];

const recordColumns: ColumnsType<TradeRecord> = [
  {
    title: '时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 130,
    render: (value: string) => (
      <span className="tabular-nums text-ink-600">{dayjs(value).format('MM-DD HH:mm')}</span>
    ),
  },
  {
    title: '股票',
    dataIndex: 'name',
    key: 'name',
    width: 130,
    render: (name: string, row) => (
      <div>
        <div className="font-medium text-ink-800">{name || row.symbol}</div>
        <div className="text-[11px] text-ink-400 tabular-nums">{row.symbol}</div>
      </div>
    ),
  },
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
  {
    title: '数量',
    dataIndex: 'quantity',
    key: 'quantity',
    align: 'right',
    width: 100,
    responsive: ['sm'],
    render: (v: number) => <span className="tabular-nums">{v.toLocaleString('zh-CN')}</span>,
  },
  {
    title: '价格',
    dataIndex: 'price',
    key: 'price',
    align: 'right',
    width: 100,
    render: (value: number) => <span className="tabular-nums">{value?.toFixed?.(2) ?? value}</span>,
  },
  {
    title: '成交额',
    key: 'amount',
    align: 'right',
    width: 130,
    responsive: ['md'],
    render: (_, row) => (
      <span className="tabular-nums text-ink-700">
        ¥{(row.price * row.quantity).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
    ),
  },
];

export function TradingPageClient() {
  // 研究员列表（用于切换）
  const { data: researchers, isLoading: researchersLoading } = useMineResearchers();
  // 当前选中的研究员；默认取第一个
  const [activeId, setActiveId] = useState<string | undefined>(undefined);

  // 派生：第一个研究员 ID（作为默认值）
  const effectiveId = useMemo(() => {
    if (activeId) return activeId;
    return researchers?.[0]?.id;
  }, [activeId, researchers]);

  const accountQuery = useTradingAccount(effectiveId);
  const positionsQuery = useTradingPositions(effectiveId);
  const recordsQuery = useTradingRecords(effectiveId);

  const loading = accountQuery.isLoading || positionsQuery.isLoading || recordsQuery.isLoading;
  const hasError = accountQuery.isError || positionsQuery.isError || recordsQuery.isError;

  const segOptions = useMemo(
    () =>
      (researchers ?? []).map((r) => ({
        label: (
          <span className="inline-flex items-center gap-2 px-1">
            <span
              className="grid h-6 w-6 place-items-center rounded-md text-[11px] font-bold text-white"
              style={{
                background: r.level?.includes('3')
                  ? 'linear-gradient(135deg, #d8453a, #9c2a23)'
                  : r.level?.includes('2')
                    ? 'linear-gradient(135deg, #c89a3a, #9f7a2a)'
                    : 'linear-gradient(135deg, #2e6e51, #143929)',
              }}
            >
              {r.name?.[0] ?? '?'}
            </span>
            <span>{r.name}</span>
            {r.level && (
              <span className="rounded bg-ink-25 px-1.5 py-px text-[10px] font-semibold text-ink-500">
                {r.level}
              </span>
            )}
          </span>
        ),
        value: r.id,
      })),
    [researchers],
  );

  const activeResearcher = researchers?.find((r) => r.id === effectiveId);

  return (
    <div className="space-y-4 sm:space-y-5">
      <SectionHeading
        title="策略交易"
        subtitle={
          activeResearcher
            ? `${activeResearcher.name} 的模拟盘 · 用于策略验证与收益追踪`
            : '研究员独立模拟盘 · 用于策略验证与收益追踪'
        }
      />

      {/* 研究员切换 */}
      {researchersLoading ? (
        <Skeleton.Input active style={{ width: 320, height: 36 }} />
      ) : segOptions.length > 0 ? (
        <div className="flex items-center gap-3">
          <span className="text-[12px] tracking-[2px] text-ink-400">研 究 员</span>
          <Segmented
            value={effectiveId}
            onChange={(v) => setActiveId(v as string)}
            options={segOptions}
            size="large"
          />
        </div>
      ) : (
        <PageCard>
          <Empty description="还没有研究员 · 先在「我的研究员」创建一个" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </PageCard>
      )}

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

      {!loading && !hasError && accountQuery.data && effectiveId ? (
        <>
          {/* 资产 Hero */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard
              label="总资产"
              value={accountQuery.data.total_asset.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
              direction={accountQuery.data.total_pnl > 0 ? 'up' : accountQuery.data.total_pnl < 0 ? 'down' : 'flat'}
              hint={
                accountQuery.data.total_return !== 0
                  ? `累计收益 ${accountQuery.data.total_return > 0 ? '+' : ''}${(accountQuery.data.total_return * 100).toFixed(2)}%`
                  : `初始 ${accountQuery.data.initial_capital.toLocaleString('zh-CN')}`
              }
            />
            <StatCard
              label="可用资金"
              value={accountQuery.data.available_cash.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
              hint={
                accountQuery.data.total_asset
                  ? `可用占比 ${((accountQuery.data.available_cash / accountQuery.data.total_asset) * 100).toFixed(1)}%`
                  : undefined
              }
            />
            <StatCard
              label="持仓市值"
              value={accountQuery.data.holding_value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              unit="元"
              hint={`持仓 ${positionsQuery.data?.length ?? 0} 只`}
            />
            <StatCard
              label="近日盈亏"
              value={`${accountQuery.data.daily_pnl > 0 ? '+' : ''}${accountQuery.data.daily_pnl.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              unit="元"
              direction={accountQuery.data.daily_pnl > 0 ? 'up' : accountQuery.data.daily_pnl < 0 ? 'down' : 'flat'}
              hint={
                accountQuery.data.total_asset
                  ? `${accountQuery.data.daily_pnl > 0 ? '+' : ''}${((accountQuery.data.daily_pnl / accountQuery.data.total_asset) * 100).toFixed(2)}%`
                  : undefined
              }
            />
          </div>

          {/* 持仓 */}
          <PageCard
            title={`当前持仓（${positionsQuery.data?.length ?? 0}）`}
            extra={<span className="cursor-pointer">持仓分布 →</span>}
            flush
          >
            {(positionsQuery.data?.length ?? 0) === 0 ? (
              <div className="py-10">
                <Empty description="暂无持仓" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            ) : (
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
            )}
          </PageCard>

          {/* 成交记录 */}
          <PageCard
            title={`成交记录（${recordsQuery.data?.length ?? 0}）`}
            extra={<span className="cursor-pointer">查看全部 →</span>}
            flush
          >
            {(recordsQuery.data?.length ?? 0) === 0 ? (
              <div className="py-10">
                <Empty description="暂无成交记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table
                  rowKey={(row) => `${row.created_at}-${row.symbol}-${row.side}`}
                  columns={recordColumns}
                  dataSource={recordsQuery.data ?? []}
                  pagination={false}
                  size="middle"
                  scroll={{ x: 'max-content' }}
                />
              </div>
            )}
          </PageCard>
        </>
      ) : null}
    </div>
  );
}
