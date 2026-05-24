/**
 * AI 智能分析容器 —— 2×2 网格布局，展示 4 张彩色分析卡片
 *
 * 用户点击「AI 解读」按钮后才请求后端生成分析结果。
 * 数据流：useAIPanels(enabled) → 后端 /news-analysis/ai-panels
 */
'use client';

import { useState } from 'react';
import { Alert, Button, Empty, Input, Modal, Skeleton, Tag, Typography, message } from 'antd';
import { BulbOutlined, ThunderboltOutlined } from '@ant-design/icons';

import { useTestChatWithResearcher } from '@/features/researcher-editor/hooks';
import { ResearcherAvatar } from '@/features/researcher-workbench/components/ResearcherAvatar';
import { useHiredResearchers } from '@/features/researcher-workbench/hooks';
import { useAIPanels } from '@/features/news-analysis/hooks';
import type { AIPanelData, AIPanelKey } from '@/types/news-analysis';
import { AIPanelCard } from './AIPanelCard';

/** 四张卡片的 key、标题、描述、图标、颜色配置 */
const panelConfig: Array<{
  key: AIPanelKey;
  title: string;
  description: string;
  icon: string;
  color: 'blue' | 'green' | 'orange' | 'emerald';
}> = [
  { key: '24h_digest', title: '资讯分析', description: '24小时热讯解读', icon: '⚡', color: 'blue' },
  { key: 'hotspot_tracking', title: '热点追踪', description: '市场热门题材挖掘', icon: '🎯', color: 'green' },
  { key: 'macro_impact', title: '宏观影响', description: '深远布局决策', icon: '⚠️', color: 'orange' },
  { key: 'stock_interpretation', title: '个股解读', description: '买卖了然于心', icon: '📊', color: 'emerald' },
];

const followupPrompts: Record<AIPanelKey, string[]> = {
  '24h_digest': ['提炼今日主线', '生成盘前检查清单', '标出风险事件'],
  hotspot_tracking: ['拆热点产业链', '找预期差标的', '判断持续性'],
  macro_impact: ['评估指数影响', '分析汇率利率扰动', '给仓位建议'],
  stock_interpretation: ['筛相关个股', '比较强弱排序', '列跟踪指标'],
};

function PanelDetailModal({
  panel,
  open,
  onClose,
}: {
  panel: AIPanelData | null;
  open: boolean;
  onClose: () => void;
}) {
  const [messageApi, contextHolder] = message.useMessage();
  const [selectedResearcherId, setSelectedResearcherId] = useState<string>();
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<string>();
  const researchersQuery = useHiredResearchers(open);
  const chatMutation = useTestChatWithResearcher();
  const researchers = researchersQuery.data ?? [];

  if (!panel) return null;

  const prompts = followupPrompts[panel.panel_key];
  const selectedResearcher = researchers.find((item) => item.researcher_id === selectedResearcherId);

  const askResearcher = async () => {
    const researcherId = selectedResearcherId ?? researchers[0]?.researcher_id;
    if (!researcherId) {
      messageApi.warning('暂无 AI 研究员');
      return;
    }
    setSelectedResearcherId(researcherId);
    const content = [
      question.trim() || prompts[0],
      '',
      `分析模块：${panel.title}`,
      `摘要：${panel.summary}`,
      `要点：${panel.highlights.join('；')}`,
      `置信度：${Math.round(panel.confidence * 100)}%`,
    ].join('\n');
    const result = await chatMutation.mutateAsync({
      researcherId,
      payload: { question: content },
    });
    setAnswer(result.answer);
  };

  return (
    <Modal
      title={<span className="serif text-[17px] font-bold">{panel.title}</span>}
      open={open}
      onCancel={onClose}
      width={620}
      footer={[
        <Button key="close" onClick={onClose}>返回资讯列表</Button>,
        <Button key="ask" type="primary" icon={<ThunderboltOutlined />} loading={chatMutation.isPending} onClick={() => void askResearcher()}>
          交给研究员深挖
        </Button>,
      ]}
    >
      {contextHolder}
      <div className="rounded-xl border border-brand-100 bg-brand-50 p-3 text-sm leading-relaxed text-ink-700">
        {panel.summary}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Tag color="blue">置信度 {Math.round(panel.confidence * 100)}%</Tag>
        <Tag color="gold">24小时资讯聚合</Tag>
        <Tag color="green">已生成 {new Date(panel.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</Tag>
      </div>

      <div className="mt-4">
        <div className="mb-2 text-[11px] tracking-[0.2em] text-ink-400">关 键 要 点</div>
        <ul className="space-y-2">
          {panel.highlights.map((item) => (
            <li key={item} className="rounded-lg bg-ink-25 px-3 py-2 text-[13px] leading-relaxed text-ink-700">
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4">
        <div className="mb-2 text-[11px] tracking-[0.2em] text-ink-400">继 续 分 析</div>
        {researchersQuery.isLoading ? (
          <Skeleton active paragraph={{ rows: 2 }} />
        ) : researchers.length === 0 ? (
          <Empty description="暂无 AI 研究员" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {researchers.slice(0, 4).map((researcher) => {
              const selected = (selectedResearcherId ?? researchers[0]?.researcher_id) === researcher.researcher_id;
              return (
                <button
                  key={researcher.researcher_id}
                  type="button"
                  onClick={() => setSelectedResearcherId(researcher.researcher_id)}
                  className={[
                    'flex items-center gap-2 rounded-lg border px-3 py-2 text-left transition-colors',
                    selected ? 'border-brand-200 bg-brand-50' : 'border-ink-50 hover:bg-ink-25',
                  ].join(' ')}
                >
                  <ResearcherAvatar name={researcher.name} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold text-ink-800">{researcher.name}</span>
                    <span className="block truncate text-[11px] text-ink-400">{researcher.tags.slice(0, 2).join(' / ') || researcher.summary}</span>
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <Input.TextArea
          rows={2}
          value={question}
          className="!mt-3 !bg-ink-25"
          placeholder="输入要让研究员继续深挖的问题"
          onChange={(event) => setQuestion(event.target.value)}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {prompts.map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-full border border-ink-50 bg-white px-3 py-1 text-[11.5px] text-ink-600 hover:border-brand-200 hover:text-brand-700"
              onClick={() => setQuestion(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {chatMutation.isError && (
        <Alert
          className="mt-4"
          type="error"
          showIcon
          message="研究员分析失败"
          description={chatMutation.error instanceof Error ? chatMutation.error.message : '请稍后重试'}
        />
      )}

      {answer && selectedResearcher && (
        <div className="mt-4 rounded-xl border border-gold-200 bg-gold-50 p-3 text-sm leading-relaxed text-ink-700">
          <div className="mb-2 text-xs font-semibold text-gold-700">{selectedResearcher.name} 的追问分析</div>
          <div className="whitespace-pre-wrap">{answer}</div>
        </div>
      )}
    </Modal>
  );
}

export function AIPanels() {
  const [requested, setRequested] = useState(false);
  const [selectedPanel, setSelectedPanel] = useState<AIPanelData | null>(null);
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
          {panelConfig.map(({ key, title, description, icon, color }) => {
            const panel = panelMap.get(key);
            return (
              <AIPanelCard
                key={key}
                title={title}
                description={description}
                icon={icon}
                summary={panel?.summary}
                highlights={panel?.highlights}
                loading={loading}
                color={color}
                onClick={panel ? () => setSelectedPanel({
                  ...panel,
                  title: title,
                }) : undefined}
              />
            );
          })}
        </div>
      )}

      <PanelDetailModal
        panel={selectedPanel}
        open={Boolean(selectedPanel)}
        onClose={() => setSelectedPanel(null)}
      />
    </div>
  );
}
