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

          <ul className="list-none space-y-1.5 pl-0">
            {data.key_points.map((pt, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[13px] leading-5 text-slate-600">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                {pt}
              </li>
            ))}
          </ul>

          <div className="text-[11px] text-slate-400">
            生成时间：{new Date(data.generated_at).toLocaleString('zh-CN')}
          </div>
        </div>
      )}
    </PageCard>
  );
}
