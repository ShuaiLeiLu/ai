/**
 * AI 智能分析容器 —— 2×2 网格布局，展示 4 张彩色分析卡片
 *
 * 用户点击「AI 解读」按钮后才请求后端生成分析结果。
 * 数据流：useAIPanels(enabled) → 后端 /news-analysis/ai-panels
 */
'use client';

import { useState } from 'react';
import { Alert, Button, Typography } from 'antd';
import { BulbOutlined } from '@ant-design/icons';

import { useAIPanels } from '@/features/news-analysis/hooks';
import type { AIPanelKey } from '@/types/news-analysis';
import { AIPanelCard } from './AIPanelCard';

/** 四张卡片的 key、标题、颜色配置 */
const panelConfig: Array<{
  key: AIPanelKey;
  title: string;
  color: 'blue' | 'orange' | 'red' | 'green';
}> = [
  { key: '24h_digest', title: '市场总结', color: 'blue' },
  { key: 'hotspot_tracking', title: '热点追踪', color: 'orange' },
  { key: 'macro_impact', title: '市场变盘', color: 'red' },
  { key: 'stock_interpretation', title: '行业关注', color: 'green' },
];

export function AIPanels() {
  const [requested, setRequested] = useState(false);
  const { data, isLoading, isFetching, isError, error, refetch } = useAIPanels(requested);
  const loading = isLoading || isFetching;

  const handleRequest = () => {
    if (requested) {
      void refetch();
      return;
    }
    setRequested(true);
  };

  // 按 panel_key 建立查找 Map，方便与配置匹配
  const panelMap = new Map((data ?? []).map((panel) => [panel.panel_key, panel]));

  return (
    <div className="rounded-xl bg-white p-5 shadow-fintech border border-slate-100/50">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-4 w-1 rounded-full bg-brand-500"></div>
          <Typography.Title level={5} className="!mb-0 !text-base !font-bold">
            <BulbOutlined className="mr-1.5 text-amber-500" />
            AI 智能分析
          </Typography.Title>
        </div>
        <Button size="small" type={data ? 'default' : 'primary'} loading={loading} onClick={handleRequest}>
          {data ? '重新生成' : 'AI 解读'}
        </Button>
      </div>

      {!requested && !data && (
        <div className="py-8 text-center text-sm text-slate-400">
          点击「AI 解读」生成智能分析
        </div>
      )}

      {isError && !loading && (
        <Alert
          message="AI 分析生成失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      )}

      {(data || loading) && (
        <div className="grid grid-cols-2 gap-3">
          {panelConfig.map(({ key, title, color }) => {
            const panel = panelMap.get(key);
            return (
              <AIPanelCard
                key={key}
                title={title}
                summary={panel?.summary}
                highlights={panel?.highlights}
                loading={loading}
                color={color}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
