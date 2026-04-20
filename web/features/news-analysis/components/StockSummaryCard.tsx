'use client';

import { Alert, Card, Empty, Statistic, Typography } from 'antd';

import { useNewsSummaryByStock } from '@/features/news-analysis/hooks';

interface StockSummaryCardProps {
  stockCode?: string;
}

export function StockSummaryCard({ stockCode }: StockSummaryCardProps) {
  const { data, isLoading, isError, error } = useNewsSummaryByStock(stockCode ?? '', {
    enabled: Boolean(stockCode)
  });

  if (!stockCode) {
    return (
      <Card title="个股聚合分析">
        <Empty description="选择热门股票后查看聚合解读" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card title="个股聚合分析">
        <Alert
          message="个股解读加载失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      </Card>
    );
  }

  return (
    <Card title={`个股聚合分析 · ${stockCode}`} loading={isLoading}>
      <Typography.Paragraph className="!mb-3 !text-sm !text-slate-700">
        {data?.conclusion || '暂无结论'}
      </Typography.Paragraph>
      <div className="grid grid-cols-3 gap-3">
        <Statistic title="利多" value={data?.sentiment_distribution.bullish ?? 0} />
        <Statistic title="中性" value={data?.sentiment_distribution.neutral ?? 0} />
        <Statistic title="利空" value={data?.sentiment_distribution.bearish ?? 0} />
      </div>
    </Card>
  );
}
