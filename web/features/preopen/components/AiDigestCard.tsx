/**
 * 盘前热门解读（AI）—— 用户点击后生成 AI 摘要
 *
 * 布局：标题 + 情绪标签 + 要点列表 + 生成时间
 * 数据流：useAiDigestQuery → 后端 /preopen/ai-digest
 */
'use client';

import { Alert, Button, Skeleton, Tag, Typography } from 'antd';
import { BulbOutlined } from '@ant-design/icons';
import { useState } from 'react';

import { PageCard } from '@/components/ui/page-card';
import { useAiDigestQuery } from '@/features/preopen/hooks';

const { Text } = Typography;

/** 情绪 → 颜色映射 */
const sentimentMeta: Record<string, { color: string; label: string }> = {
  bullish: { color: 'red', label: '偏多' },
  bearish: { color: 'green', label: '偏空' },
  neutral: { color: 'default', label: '中性' },
};

export function AiDigestCard() {
  const [requested, setRequested] = useState(false);
  const { data, isLoading, isFetching, error, refetch } = useAiDigestQuery(requested);
  const meta = sentimentMeta[data?.sentiment ?? 'neutral'];
  const loading = isLoading || isFetching;

  const handleRequestDigest = () => {
    if (requested) {
      void refetch();
      return;
    }
    setRequested(true);
  };

  return (
    <PageCard
      title={
        <span className="flex items-center gap-1.5">
          <BulbOutlined className="text-amber-500" />
          盘前热门解读
        </span>
      }
      extra={
        <Button size="small" type={data ? 'default' : 'primary'} loading={loading} onClick={handleRequestDigest}>
          {data ? '重新生成' : 'AI 解读'}
        </Button>
      }
    >
      {!requested && !data && (
        <div className="py-6 text-center text-sm text-slate-400">
          点击后生成盘前 AI 解读
        </div>
      )}

      {loading && <Skeleton active paragraph={{ rows: 4 }} />}

      {error && !loading && (
        <Alert message="AI 解读生成失败" description={error.message} type="error" showIcon />
      )}

      {data && !loading && (
        <div className="space-y-3">
          <div className="flex items-start gap-2">
            <Tag color={meta.color} className="shrink-0">{meta.label}</Tag>
            <Text strong className="text-sm leading-5">{data.headline}</Text>
          </div>

          <DigestList title="市场结构" items={data.key_points} tone="brand" />
          <DigestList title="新闻驱动" items={data.news_drivers ?? []} tone="amber" />
          <div className="grid gap-2 sm:grid-cols-2">
            <DigestList title="机会方向" items={data.opportunity_sectors ?? []} tone="rose" compact />
            <DigestList title="风险方向" items={data.risk_sectors ?? []} tone="green" compact />
          </div>
          <DigestList title="盘中观察" items={data.intraday_watch ?? []} tone="slate" />
          <DigestList title="模拟盘预案" items={data.simulation_plan ?? []} tone="purple" />

          <div className="text-[11px] text-slate-400">
            生成时间：{new Date(data.generated_at).toLocaleString('zh-CN')}
          </div>
        </div>
      )}
    </PageCard>
  );
}

function DigestList({
  title,
  items,
  tone,
  compact = false,
}: {
  title: string;
  items: string[];
  tone: 'brand' | 'amber' | 'rose' | 'green' | 'slate' | 'purple';
  compact?: boolean;
}) {
  if (!items.length) return null;
  const dotClass = {
    brand: 'bg-brand-400',
    amber: 'bg-amber-400',
    rose: 'bg-rose-400',
    green: 'bg-emerald-400',
    slate: 'bg-slate-400',
    purple: 'bg-violet-400',
  }[tone];

  return (
    <div className={compact ? 'rounded-md bg-slate-50 px-2.5 py-2' : ''}>
      <div className="mb-1 text-[11px] font-semibold text-slate-500">{title}</div>
      <ul className="list-none space-y-1.5 pl-0">
        {items.slice(0, compact ? 3 : 5).map((pt, i) => (
          <li key={i} className="flex items-start gap-1.5 text-[13px] leading-5 text-slate-600">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`} />
            <span>{pt}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
