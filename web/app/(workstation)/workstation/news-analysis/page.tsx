/**
 * 资讯分析页面 —— 左右分栏 8:4 布局
 *
 * 左侧（8/12）：资讯一览（Segmented 分类 + “只看重要”开关 + 热门股票标签过滤 + 新闻列表）
 * 右侧（4/12）：AI智能分析彩色卡片 + 股票概要 + 24小时热股榜
 *
 * 数据流：
 *  - FilterControls  控制筛选参数 (category / important_only / stock_code)
 *  - NewsFeed        根据筛选参数拉取新闻流
 *  - AIPanels        2×2 彩色卡片（市场总结/热点追踪/市场变盘/行业关注）
 *  - HotNewsList     24小时热股排行榜
 */
'use client';

import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Drawer, Empty, Input, Modal, Skeleton, Tag, Typography, message } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';

import {
  AIPanels,
  FilterControls,
  HotNewsList,
  NewsFeed,
  StockSummaryCard,
} from '@/features/news-analysis/components';
import { useNewsFeed, useHotStocks } from '@/features/news-analysis/hooks';
import { ResearcherAvatar } from '@/features/researcher-workbench/components/ResearcherAvatar';
import { useHiredResearchers } from '@/features/researcher-workbench/hooks';
import { useTestChatWithResearcher } from '@/features/researcher-editor/hooks';
import type { GetNewsFeedParams, NewsFeedItem, NewsStockRelation } from '@/types/news-analysis';
import type { HiredResearcher } from '@/types/researcher-workbench';

const QUICK_PROMPTS = [
  '受益板块',
  '短期影响',
  '推荐标的',
  '风险点',
];

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function researcherSubtitle(researcher: HiredResearcher): string {
  const tags = researcher.tags.slice(0, 2).join(' / ');
  return tags || researcher.summary || '擅长多源资讯与市场结构交叉验证';
}

function NewsAnalysisModal({
  news,
  open,
  onClose,
}: {
  news: NewsFeedItem | null;
  open: boolean;
  onClose: () => void;
}) {
  const [messageApi, contextHolder] = message.useMessage();
  const [selectedResearcherId, setSelectedResearcherId] = useState<string>();
  const [prompt, setPrompt] = useState('帮我分析下这篇文章的影响');
  const [answer, setAnswer] = useState<string>();
  const researchersQuery = useHiredResearchers(open);
  const chatMutation = useTestChatWithResearcher();
  const researchers = researchersQuery.data ?? [];

  useEffect(() => {
    if (!open) return;
    setPrompt('帮我分析下这篇文章的影响');
    setAnswer(undefined);
  }, [open, news?.news_id]);

  useEffect(() => {
    if (!open || selectedResearcherId || researchers.length === 0) return;
    setSelectedResearcherId(researchers[0].researcher_id);
  }, [open, researchers, selectedResearcherId]);

  const selectedResearcher = researchers.find((item) => item.researcher_id === selectedResearcherId);

  const startAnalysis = async () => {
    if (!news || !selectedResearcherId) {
      messageApi.warning('请选择 AI 研究员');
      return;
    }
    const content = [
      prompt.trim() || '帮我分析下这篇文章的影响',
      '',
      `资讯标题：${news.title}`,
      `资讯摘要：${news.summary}`,
      `资讯正文：${news.content || news.summary}`,
    ].join('\n');
    const result = await chatMutation.mutateAsync({
      researcherId: selectedResearcherId,
      payload: { question: content },
    });
    setAnswer(result.answer);
  };

  return (
    <Modal
      title={<span className="serif text-[17px] font-bold"><ThunderboltOutlined className="mr-1 text-gold-500" />AI 解读这条资讯</span>}
      open={open}
      width={560}
      onCancel={onClose}
      footer={[
        <span key="cost" className="mr-auto text-xs text-ink-400">本次消耗 <b className="text-gold-600">10 算力</b></span>,
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="submit" type="primary" icon={<ThunderboltOutlined />} loading={chatMutation.isPending} onClick={() => void startAnalysis()}>
          开始解读
        </Button>,
      ]}
    >
      {contextHolder}
      {news && (
        <div className="mb-4 rounded-lg bg-ink-25 px-3 py-2 text-xs leading-relaxed text-ink-700">
          <b className="text-up-600">[{news.category}]</b> {news.title}
        </div>
      )}

      <div className="mb-4 text-[11px] tracking-[0.2em] text-ink-400">选 择 研 究 员</div>
      {researchersQuery.isLoading && <Skeleton active paragraph={{ rows: 3 }} />}
      {!researchersQuery.isLoading && researchers.length === 0 && (
        <Empty description="暂无 AI 研究员" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      {!researchersQuery.isLoading && researchers.length > 0 && (
        <div className="space-y-2">
          {researchers.slice(0, 4).map((researcher, index) => {
            const selected = researcher.researcher_id === selectedResearcherId;
            return (
              <button
                key={researcher.researcher_id}
                type="button"
                className={[
                  'flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors',
                  selected ? 'border-brand-200 bg-brand-50' : 'border-ink-50 hover:bg-ink-25',
                ].join(' ')}
                onClick={() => setSelectedResearcherId(researcher.researcher_id)}
              >
                <span className={['h-3 w-3 rounded-full border', selected ? 'border-brand-600 bg-brand-600' : 'border-ink-200'].join(' ')} />
                <ResearcherAvatar name={researcher.name} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-ink-900">{researcher.name}</span>
                  <span className="block truncate text-[11px] text-ink-400">{researcherSubtitle(researcher)}</span>
                </span>
                {index === 0 && <Tag color="green">推荐</Tag>}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-4">
        <div className="mb-2 text-[11px] tracking-[0.2em] text-ink-400">分 析 内 容</div>
        <Input.TextArea
          rows={3}
          value={prompt}
          className="!bg-ink-25"
          onChange={(event) => setPrompt(event.target.value)}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {QUICK_PROMPTS.map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-full border border-ink-50 bg-white px-3 py-1 text-[11.5px] text-ink-600 hover:border-brand-200 hover:text-brand-700"
              onClick={() => setPrompt(`帮我分析这篇资讯的${item}`)}
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
          message="AI 解读失败"
          description={chatMutation.error instanceof Error ? chatMutation.error.message : '请稍后重试'}
        />
      )}

      {answer && selectedResearcher && (
        <div className="mt-4 rounded-xl border border-gold-200 bg-gold-50 p-3 text-sm leading-relaxed text-ink-700">
          <div className="mb-2 text-xs font-semibold text-gold-700">{selectedResearcher.name} 的解读</div>
          <div className="whitespace-pre-wrap">{answer}</div>
        </div>
      )}
    </Modal>
  );
}

function MentionedStocksPanel({
  selectedStockCode,
  onSelectStock,
}: {
  selectedStockCode?: string;
  onSelectStock: (stock: NewsStockRelation) => void;
}) {
  const { data: hotStocks, isLoading } = useHotStocks();

  return (
    <div className="rounded-xl border border-slate-100/50 bg-white p-4 shadow-fintech">
      <div className="mb-3 flex items-center gap-2">
        <div className="h-4 w-1 rounded-full bg-brand-500" />
        <Typography.Title level={5} className="!mb-0 !text-base !font-bold">
          最新收盘日至今提及标的
        </Typography.Title>
      </div>
      {isLoading && <Skeleton active paragraph={{ rows: 2 }} />}
      {!isLoading && (!hotStocks || hotStocks.length === 0) && (
        <Empty description="暂无资讯提及个股" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      {!isLoading && hotStocks && hotStocks.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {hotStocks.map((stock) => (
            <button
              key={stock.stock_code}
              type="button"
              className={[
                'rounded-md border px-3 py-1.5 text-xs transition-colors',
                selectedStockCode === stock.stock_code
                  ? 'border-brand-300 bg-brand-50 text-brand-700'
                  : 'border-ink-50 bg-white text-ink-600 hover:border-brand-200 hover:text-brand-700',
              ].join(' ')}
              onClick={() => onSelectStock({ stock_code: stock.stock_code, stock_name: stock.stock_name })}
            >
              {stock.stock_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RelatedStockDrawer({
  stock,
  open,
  onClose,
  onAnalyzeNews,
}: {
  stock: NewsStockRelation | null;
  open: boolean;
  onClose: () => void;
  onAnalyzeNews: (news: NewsFeedItem) => void;
}) {
  const { data: relatedNews, isLoading } = useNewsFeed({
    category: 'all',
    stock_code: stock?.stock_code,
  });
  const visibleNews = stock ? relatedNews ?? [] : [];

  return (
    <Drawer
      title={
        <div>
          <div className="serif text-[17px] font-bold text-ink-900">{stock?.stock_name ?? '相关标的'}</div>
          <div className="mt-0.5 text-xs text-ink-400">{stock?.stock_code} · 相关资讯</div>
        </div>
      }
      open={open}
      width={420}
      onClose={onClose}
      extra={<Button type="text" onClick={onClose}>收起</Button>}
    >
      {isLoading && <Skeleton active paragraph={{ rows: 8 }} />}
      {!isLoading && visibleNews.length === 0 && (
        <Empty description="暂无相关资讯" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      {!isLoading && visibleNews.length > 0 && (
        <div className="space-y-1">
          <div className="px-1 pb-2 text-[11px] tracking-[0.2em] text-ink-400">
            相 关 资 讯 · {visibleNews.length} 条
          </div>
          {visibleNews.map((item) => (
            <div key={item.news_id} className="border-b border-dashed border-ink-50 px-1 py-3">
              <div className="flex items-center gap-2 text-[11px] text-ink-400">
                <Tag color={item.is_important ? 'red' : 'default'} className="!mr-0">{item.category}</Tag>
                <span>{formatTime(item.publish_time)}</span>
              </div>
              <div className="mt-1.5 text-sm font-semibold leading-relaxed text-ink-900">{item.title}</div>
              <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-500">{item.summary}</div>
              <Button
                size="small"
                className="mt-2"
                icon={<ThunderboltOutlined />}
                onClick={() => onAnalyzeNews(item)}
              >
                让 AI 分析
              </Button>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  );
}

export default function NewsAnalysisPage() {
  // 筛选参数：分类 + 是否只看重要 + 股票代码
  const [filters, setFilters] = useState<GetNewsFeedParams>({
    category: 'all',
    important_only: false,
  });
  const [analysisNews, setAnalysisNews] = useState<NewsFeedItem | null>(null);
  const [selectedStock, setSelectedStock] = useState<NewsStockRelation | null>(null);

  /** 局部更新筛选参数（合并更新） */
  const handleFilterChange = (next: Partial<GetNewsFeedParams>) => {
    setFilters((prev) => ({ ...prev, ...next }));
  };

  const selectedStockCode = useMemo(() => selectedStock?.stock_code ?? filters.stock_code, [filters.stock_code, selectedStock]);

  const selectStock = (stock: NewsStockRelation) => {
    setSelectedStock(stock);
    setFilters((prev) => ({ ...prev, stock_code: stock.stock_code }));
  };

  return (
    // 移动端：自然流式高度（避免与底部 TabBar 重叠）
    // 桌面端：固定视口高度，左侧列表内滚动
    <div className="lg:h-[calc(100vh-64px-40px)] lg:overflow-hidden">
      <div className="grid grid-cols-12 gap-4 lg:h-full lg:gap-6">
        {/* Left: News feed (桌面端内滚动 / 移动端自然流) */}
        <div className="col-span-12 flex flex-col gap-4 lg:col-span-8 lg:h-full lg:overflow-hidden">
          <div className="rounded-xl bg-white p-4 sm:p-5 shadow-fintech border border-slate-100/50">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-4 w-1 rounded-full bg-brand-500"></div>
                <Typography.Title level={5} className="!mb-0 !text-base !font-bold">
                  资讯一览
                </Typography.Title>
              </div>
            </div>
            <FilterControls filters={filters} onFilterChange={handleFilterChange} />
          </div>

          <div className="rounded-xl bg-white shadow-fintech border border-slate-100/50 lg:flex-1 lg:overflow-y-auto no-scrollbar">
            <NewsFeed
              filters={filters}
              onAnalyzeNews={setAnalysisNews}
              onSelectStock={selectStock}
            />
          </div>
        </div>

        {/* Right: AI analysis + hot stocks */}
        <div className="col-span-12 space-y-4 lg:col-span-4 lg:space-y-5 lg:pb-10 lg:overflow-y-auto no-scrollbar">
          <AIPanels />
          <MentionedStocksPanel selectedStockCode={selectedStockCode} onSelectStock={selectStock} />
          <div className="rounded-xl bg-white shadow-fintech border border-slate-100/50 p-1">
            <StockSummaryCard stockCode={filters.stock_code} />
          </div>
          <HotNewsList />
        </div>
      </div>

      <NewsAnalysisModal
        news={analysisNews}
        open={Boolean(analysisNews)}
        onClose={() => setAnalysisNews(null)}
      />

      <RelatedStockDrawer
        stock={selectedStock}
        open={Boolean(selectedStock)}
        onClose={() => setSelectedStock(null)}
        onAnalyzeNews={setAnalysisNews}
      />
    </div>
  );
}
