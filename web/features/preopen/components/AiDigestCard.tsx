/**
 * 盘前热门解读（AI）—— 基于涨停池数据生成的 AI 摘要
 *
 * 布局：标题 + 情绪标签 + 要点列表 + 生成时间
 * 数据流：useAiDigestQuery → 后端 /preopen/ai-digest
 */
'use client';

import { Tag, Typography } from 'antd';
import { BulbOutlined } from '@ant-design/icons';

import { PageCard } from '@/components/ui/page-card';
import { useAiDigestQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';

const { Text } = Typography;

/** 情绪 → 颜色映射 */
const sentimentMeta: Record<string, { color: string; label: string }> = {
  bullish: { color: 'red', label: '偏多' },
  bearish: { color: 'green', label: '偏空' },
  neutral: { color: 'default', label: '中性' },
};

export function AiDigestCard() {
  const { data, isLoading, error } = useAiDigestQuery();
  const meta = sentimentMeta[data?.sentiment ?? 'neutral'];

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="盘前热门解读">
      <PageCard
        title={
          <span className="flex items-center gap-1.5">
            <BulbOutlined className="text-amber-500" />
            盘前热门解读
          </span>
        }
      >
        {data && (
          <div className="space-y-3">
            {/* 情绪标签 + 标题 */}
            <div className="flex items-start gap-2">
              <Tag color={meta.color} className="shrink-0">{meta.label}</Tag>
              <Text strong className="text-sm leading-5">{data.headline}</Text>
            </div>

            {/* 要点列表 */}
            <ul className="list-none space-y-1.5 pl-0">
              {data.key_points.map((pt, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[13px] leading-5 text-slate-600">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                  {pt}
                </li>
              ))}
            </ul>

            {/* 生成时间 */}
            <div className="text-[11px] text-slate-400">
              生成时间：{new Date(data.generated_at).toLocaleString('zh-CN')}
            </div>
          </div>
        )}
      </PageCard>
    </StateWrapper>
  );
}
