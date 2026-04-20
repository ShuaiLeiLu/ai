/**
 * AI 智能分析容器 —— 2×2 网格布局，展示 4 张彩色分析卡片
 *
 * 通过 useAIPanels() 拉取后端 AI 分析结果，将 panel_key 与配置映射后
 * 传入 AIPanelCard 子组件渲染。
 */
'use client';

import { Alert, Typography } from 'antd';

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
  const { data, isLoading, isError, error } = useAIPanels();

  if (isError) {
    return (
      <Alert
        message="AI 分析加载失败"
        description={error instanceof Error ? error.message : '未知错误'}
        type="error"
        showIcon
      />
    );
  }

  // 按 panel_key 建立查找 Map，方便与配置匹配
  const panelMap = new Map((data ?? []).map((panel) => [panel.panel_key, panel]));

  return (
    <div className="rounded-lg bg-white p-4">
      <Typography.Title level={5} className="!mb-3">
        AI 智能分析
      </Typography.Title>
      <div className="grid grid-cols-2 gap-3">
        {panelConfig.map(({ key, title, color }) => {
          const panel = panelMap.get(key);
          return (
            <AIPanelCard
              key={key}
              title={title}
              summary={panel?.summary}
              highlights={panel?.highlights}
              loading={isLoading}
              color={color}
            />
          );
        })}
      </div>
    </div>
  );
}
