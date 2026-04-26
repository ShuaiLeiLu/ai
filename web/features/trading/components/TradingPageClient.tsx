'use client';

import { Card, Col, Empty, Row, Skeleton, Statistic, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { useTradingAccount, useTradingPositions, useTradingRecords } from '@/features/trading/hooks';
import { PositionItem, TradeRecord } from '@/types/trading';

function money(value: number): string {
  return `¥${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const positionColumns: ColumnsType<PositionItem> = [
  { title: '股票', dataIndex: 'name', key: 'name' },
  { title: '代码', dataIndex: 'symbol', key: 'symbol' },
  { title: '数量', dataIndex: 'quantity', key: 'quantity' },
  { title: '成本价', dataIndex: 'cost_price', key: 'cost_price' },
  { title: '现价', dataIndex: 'current_price', key: 'current_price' },
  {
    title: '盈亏',
    dataIndex: 'pnl',
    key: 'pnl',
    render: (value: number) => <span className={value >= 0 ? 'text-rose-500' : 'text-emerald-600'}>{money(value)}</span>
  }
];

const recordColumns: ColumnsType<TradeRecord> = [
  { title: '时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => dayjs(value).format('MM-DD HH:mm') },
  { title: '代码', dataIndex: 'symbol', key: 'symbol' },
  { title: '方向', dataIndex: 'side', key: 'side', render: (value: string) => (value === 'buy' ? <Tag color="red">买入</Tag> : <Tag color="green">卖出</Tag>) },
  { title: '数量', dataIndex: 'quantity', key: 'quantity' },
  { title: '价格', dataIndex: 'price', key: 'price' }
];

export function TradingPageClient() {
  const accountQuery = useTradingAccount();
  const positionsQuery = useTradingPositions();
  const recordsQuery = useTradingRecords();
  const loading = accountQuery.isLoading || positionsQuery.isLoading || recordsQuery.isLoading;
  const hasError = accountQuery.isError || positionsQuery.isError || recordsQuery.isError;

  return (
    <div className="space-y-4">
      <Card title="模拟交易">
        <Typography.Paragraph type="secondary">
          展示模拟账户资产、当前持仓和成交记录，用于策略验证与收益追踪。
        </Typography.Paragraph>
        {loading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
        {!loading && hasError ? <Empty description="模拟交易数据加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : null}
        {!loading && !hasError && accountQuery.data ? (
          <>
            <Row gutter={[12, 12]} className="mb-4">
              <Col xs={24} md={6}>
                <Card size="small">
                  <Statistic title="总资产" value={accountQuery.data.total_asset} precision={2} suffix="元" />
                </Card>
              </Col>
              <Col xs={24} md={6}>
                <Card size="small">
                  <Statistic title="可用资金" value={accountQuery.data.available_cash} precision={2} suffix="元" />
                </Card>
              </Col>
              <Col xs={24} md={6}>
                <Card size="small">
                  <Statistic title="持仓市值" value={accountQuery.data.holding_value} precision={2} suffix="元" />
                </Card>
              </Col>
              <Col xs={24} md={6}>
                <Card size="small">
                  <Statistic
                    title="近日盈亏"
                    value={accountQuery.data.daily_pnl}
                    precision={2}
                    suffix="元"
                    valueStyle={{ color: accountQuery.data.daily_pnl >= 0 ? '#ef4444' : '#16a34a' }}
                  />
                </Card>
              </Col>
            </Row>

            <Card size="small" title="持仓">
              <Table rowKey="symbol" columns={positionColumns} dataSource={positionsQuery.data ?? []} pagination={false} />
            </Card>

            <Card size="small" title="成交记录" className="mt-4">
              <Table rowKey="trade_id" columns={recordColumns} dataSource={recordsQuery.data ?? []} pagination={false} />
            </Card>
          </>
        ) : null}
      </Card>
    </div>
  );
}
