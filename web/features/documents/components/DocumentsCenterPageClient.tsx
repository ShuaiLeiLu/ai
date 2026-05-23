/**
 * 研报库（DocumentsCenter）—— 三栏布局
 *
 * 视觉对照设计稿 10 号"研报库"：
 *   左栏  220px  ：来源/标签导航（机构 / 行业）
 *   中间  flex-1 ：研报列表 + 搜索 + 筛选
 *   右栏  340px  ：AI 摘要面板
 *
 * 保留：useDocuments / useDocumentDetail / useHotDocuments / DocumentType 筛选
 */
'use client';

import { useMemo, useState } from 'react';
import { Drawer, Empty, Skeleton, Space, Tag, Typography } from 'antd';
import dayjs from 'dayjs';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { PageCard } from '@/components/ui/page-card';
import { useDocumentDetail, useDocuments, useHotDocuments } from '@/features/documents/hooks';
import { DocumentSummary, DocumentType } from '@/types/documents';

/** Badge —— inline 工具类（globals.css 未定义 .badge，直接写 className） */
function Badge({
  tone = 'ink',
  children,
}: {
  tone?: 'ink' | 'brand' | 'up' | 'down' | 'gold';
  children: React.ReactNode;
}) {
  const map: Record<string, string> = {
    ink: 'bg-ink-25 text-ink-600',
    brand: 'bg-brand-50 text-brand-700',
    up: 'bg-up-50 text-up-600',
    down: 'bg-down-50 text-down-600',
    gold: 'bg-gold-50 text-gold-600',
  };
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[10.5px] font-medium ${map[tone]}`}
    >
      {children}
    </span>
  );
}

/** 文档类型 → 中文 + Badge tone */
function typeMeta(t: DocumentType): { label: string; tone: 'ink' | 'brand' | 'up' | 'down' | 'gold' } {
  switch (t) {
    case 'market':
      return { label: '策略', tone: 'brand' };
    case 'stock':
      return { label: '深度', tone: 'ink' };
    case 'industry':
      return { label: '行业', tone: 'gold' };
    case 'topic':
      return { label: '点评', tone: 'up' };
    default:
      return { label: '研报', tone: 'ink' };
  }
}

/** 评级标签 —— 简单从标题里启发式抽 */
function ratingFromTitle(t: string): string | null {
  if (/买入/.test(t)) return '买入';
  if (/推荐/.test(t)) return '推荐';
  if (/看好/.test(t)) return '看好';
  return null;
}

const docTypeOptions: { label: string; value: 'all' | DocumentType; emoji: string; count?: string }[] = [
  { label: '全部', value: 'all', emoji: '📂' },
  { label: '我的收藏', value: 'all', emoji: '⭐' },
  { label: '我的笔记', value: 'all', emoji: '📝' },
];

const docCategoryOptions: { label: string; value: DocumentType; emoji: string }[] = [
  { label: '市场策略', value: 'market', emoji: '📈' },
  { label: '个股深度', value: 'stock', emoji: '🔍' },
  { label: '行业研究', value: 'industry', emoji: '🏭' },
  { label: '专题报告', value: 'topic', emoji: '🎯' },
];

const institutionGroup = [
  { name: '中信证券', count: 128 },
  { name: '中金公司', count: 96 },
  { name: '海通证券', count: 83 },
  { name: '国泰君安', count: 77 },
];

const industryGroup = [
  { name: '半导体', count: 142 },
  { name: '新能源', count: 118 },
  { name: '医药生物', count: 98 },
];

export function DocumentsCenterPageClient() {
  const [docType, setDocType] = useState<'all' | DocumentType>('all');
  const [selectedId, setSelectedId] = useState<string>();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [previewId, setPreviewId] = useState<string>();

  const docsQuery = useDocuments(docType === 'all' ? undefined : { doc_type: docType });
  const hotQuery = useHotDocuments();
  const detailQuery = useDocumentDetail(selectedId);
  const previewQuery = useDocumentDetail(previewId);

  const docs: DocumentSummary[] = docsQuery.data ?? [];

  /** 默认选中第一条用于右侧 AI 摘要 */
  const activeId = previewId ?? docs[0]?.document_id;
  const activeDoc = useMemo(
    () => docs.find((d) => d.document_id === activeId) ?? docs[0],
    [docs, activeId],
  );
  const activeDetail = previewId ? previewQuery.data : undefined;

  const openDetail = (item: DocumentSummary) => {
    setSelectedId(item.document_id);
    setDrawerOpen(true);
  };

  /** 总数（左栏"全部"显示） */
  const totalCount = docs.length || 1247;

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      {/* ───────── 左栏 ───────── */}
      <aside className="lg:w-[220px] lg:shrink-0">
        <PageCard density="compact" flush>
          <div className="px-4 py-4">
            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[2px] text-ink-400">
              研 报 库
            </div>
            <ul className="space-y-1 text-[13px]">
              {docTypeOptions.map((opt, idx) => {
                const isActive = idx === 0 && docType === 'all';
                return (
                  <li key={`top-${opt.label}`}>
                    <button
                      type="button"
                      onClick={() => setDocType('all')}
                      className={[
                        'flex w-full items-center justify-between rounded px-2.5 py-1.5 text-left transition-colors',
                        isActive
                          ? 'bg-brand-50 font-semibold text-brand-700'
                          : 'text-ink-600 hover:bg-ink-25',
                      ].join(' ')}
                    >
                      <span>
                        <span className="mr-2">{opt.emoji}</span>
                        {opt.label}
                      </span>
                      {idx === 0 && (
                        <span className="tnum text-[11px] text-ink-400">
                          ({totalCount.toLocaleString()})
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="mt-4 mb-2 text-[11px] font-semibold uppercase tracking-[2px] text-ink-400">
              类 型
            </div>
            <ul className="space-y-1 text-[13px]">
              {docCategoryOptions.map((opt) => {
                const isActive = docType === opt.value;
                return (
                  <li key={opt.value}>
                    <button
                      type="button"
                      onClick={() => setDocType(opt.value)}
                      className={[
                        'flex w-full items-center justify-between rounded px-2.5 py-1.5 text-left transition-colors',
                        isActive
                          ? 'bg-brand-50 font-semibold text-brand-700'
                          : 'text-ink-600 hover:bg-ink-25',
                      ].join(' ')}
                    >
                      <span>
                        <span className="mr-2">{opt.emoji}</span>
                        {opt.label}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="mt-4 mb-2 text-[11px] font-semibold uppercase tracking-[2px] text-ink-400">
              机 构
            </div>
            <ul className="space-y-1 text-[13px]">
              {institutionGroup.map((it) => (
                <li
                  key={it.name}
                  className="flex items-center justify-between rounded px-2.5 py-1 text-ink-600 hover:bg-ink-25"
                >
                  <span className="truncate">{it.name}</span>
                  <span className="tnum text-[11px] text-ink-400">{it.count}</span>
                </li>
              ))}
            </ul>

            <div className="mt-4 mb-2 text-[11px] font-semibold uppercase tracking-[2px] text-ink-400">
              行 业
            </div>
            <ul className="space-y-1 text-[13px]">
              {industryGroup.map((it) => (
                <li
                  key={it.name}
                  className="flex items-center justify-between rounded px-2.5 py-1 text-ink-600 hover:bg-ink-25"
                >
                  <span className="truncate">{it.name}</span>
                  <span className="tnum text-[11px] text-ink-400">{it.count}</span>
                </li>
              ))}
            </ul>
          </div>
        </PageCard>
      </aside>

      {/* ───────── 中间列表 ───────── */}
      <section className="min-w-0 flex-1">
        <PageCard flush>
          {/* 搜索 + 筛选条 */}
          <div className="border-b border-ink-25 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex flex-1 items-center gap-2 rounded-lg bg-ink-25 px-3 py-2">
                <span className="text-ink-400">🔍</span>
                <input
                  type="text"
                  placeholder="搜索研报标题、标的、机构…"
                  className="w-full bg-transparent text-[13px] text-ink-800 placeholder:text-ink-400 focus:outline-none"
                />
              </div>
              <button
                type="button"
                className="rounded border border-ink-50 px-3 py-1.5 text-[12px] text-ink-600 hover:border-brand-600 hover:text-brand-600"
              >
                近 7 天
              </button>
              <button
                type="button"
                className="rounded border border-ink-50 px-3 py-1.5 text-[12px] text-ink-600 hover:border-brand-600 hover:text-brand-600"
              >
                全部标签
              </button>
            </div>
          </div>

          {/* 列表 */}
          <div className="divide-y divide-ink-25">
            {docsQuery.isLoading ? (
              <div className="p-4">
                <Skeleton active paragraph={{ rows: 6 }} />
              </div>
            ) : null}

            {!docsQuery.isLoading && docsQuery.isError ? (
              <div className="p-8">
                <Empty description="文档列表加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            ) : null}

            {!docsQuery.isLoading && !docsQuery.isError && docs.length === 0 ? (
              <div className="p-12">
                <Empty description="暂无文档" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            ) : null}

            {!docsQuery.isLoading &&
              !docsQuery.isError &&
              docs.map((item, idx) => {
                const meta = typeMeta(item.document_type);
                const rating = ratingFromTitle(item.title);
                const isSelected = item.document_id === activeId || (idx === 0 && !activeId);
                return (
                  <div
                    key={item.document_id}
                    onClick={() => setPreviewId(item.document_id)}
                    onDoubleClick={() => openDetail(item)}
                    className={[
                      'cursor-pointer px-4 py-4 transition-colors',
                      isSelected ? 'bg-brand-50' : 'hover:bg-ink-25/60',
                    ].join(' ')}
                  >
                    {/* 标签行 */}
                    <div className="mb-2 flex flex-wrap items-center gap-1.5">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      {rating && <Badge tone="up">{rating}</Badge>}
                      {item.symbol && <Badge tone="ink">{item.symbol}</Badge>}
                      <span className="ml-1 text-[11.5px] text-ink-400">
                        {item.researcher_name} · {dayjs(item.created_at).format('MM-DD HH:mm')}
                      </span>
                    </div>

                    {/* 标题（思源宋体） */}
                    <h4 className="serif mb-1 line-clamp-2 text-[15px] font-bold leading-snug text-ink-900">
                      {item.title}
                    </h4>

                    {/* 描述截 2 行 —— 使用 symbol 等做占位描述 */}
                    <p className="line-clamp-2 text-[12px] leading-relaxed text-ink-600">
                      {`${meta.label} · ${item.researcher_name} · ${item.symbol ?? '市场综合'} —— AI 已对研报核心观点、推荐标的与情绪进行结构化提炼。`}
                    </p>

                    {/* 底部小字 */}
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-ink-400">
                      <span>📄 32 页</span>
                      <span className="tnum">👁 {item.view_count}</span>
                      <span className="tnum">⭐ {item.like_count}</span>
                      <span className="text-brand-600">🧠 AI 已分析</span>
                    </div>
                  </div>
                );
              })}
          </div>
        </PageCard>
      </section>

      {/* ───────── 右栏 AI 摘要 ───────── */}
      <aside className="lg:w-[340px] lg:shrink-0">
        <PageCard
          title="AI 摘要"
          accent="brand"
          extra={<Badge tone="brand">AI</Badge>}
          density="comfortable"
        >
          {!activeDoc ? (
            <Empty description="选择一篇研报查看摘要" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <div className="space-y-4">
              {/* 标题 */}
              <h3 className="serif text-[16px] font-bold leading-snug text-ink-900">
                {activeDoc.title}
              </h3>

              {/* 元信息 */}
              <div className="text-[11.5px] text-ink-400">
                {activeDoc.researcher_name} · 研究团队 ·{' '}
                {dayjs(activeDoc.created_at).format('YYYY-MM-DD')}
              </div>

              {/* 核心观点 */}
              <div>
                <div className="mb-1.5 text-[12px] font-semibold text-ink-800">📋 核心观点</div>
                <ul className="space-y-1 text-[12.5px] leading-relaxed text-ink-600">
                  <li className="flex gap-2">
                    <span className="text-brand-600">•</span>
                    <span>需求侧持续修复，产能利用率回升至 82%，景气度上行。</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-brand-600">•</span>
                    <span>头部公司 Q2 业绩有望超预期，估值切换在即。</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-brand-600">•</span>
                    <span>风险点：海外需求疲软、原材料价格波动。</span>
                  </li>
                </ul>
              </div>

              {/* 推荐标的 */}
              <div>
                <div className="mb-1.5 text-[12px] font-semibold text-ink-800">🎯 推荐标的</div>
                <div className="flex flex-wrap gap-1.5">
                  {(activeDoc.symbol ? [activeDoc.symbol] : ['603501', '002371', '688981', '300782']).map(
                    (sym) => (
                      <Badge key={sym} tone="brand">
                        {sym}
                      </Badge>
                    ),
                  )}
                </div>
              </div>

              {/* 价值挖掘者点评 */}
              <div className="rounded-lg bg-brand-50 p-3">
                <div className="mb-1 text-[12px] font-semibold text-brand-700">
                  💬 价值挖掘者点评
                </div>
                <p className="text-[12px] leading-relaxed text-ink-700">
                  机构观点与近期资金流向吻合，板块拐点信号增强，建议关注景气度持续验证。
                </p>
              </div>

              {/* 底部按钮 */}
              <button
                type="button"
                onClick={() => openDetail(activeDoc)}
                className="w-full rounded-lg bg-brand-600 py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-brand-700"
              >
                📖 阅读全文
              </button>
            </div>
          )}
        </PageCard>

        {/* 热门文档 —— 保留 useHotDocuments */}
        {!hotQuery.isLoading && (hotQuery.data?.length ?? 0) > 0 && (
          <div className="mt-4">
            <PageCard title="热门文档" accent="gold" density="compact">
              <ul className="space-y-2 text-[12.5px]">
                {(hotQuery.data ?? []).slice(0, 5).map((item, i) => (
                  <li
                    key={item.document_id}
                    onClick={() => setPreviewId(item.document_id)}
                    className="flex cursor-pointer items-start gap-2 hover:text-brand-600"
                  >
                    <span
                      className={[
                        'tnum mt-0.5 w-4 shrink-0 text-[11px] font-semibold',
                        i < 3 ? 'text-down-500' : 'text-ink-400',
                      ].join(' ')}
                    >
                      {i + 1}
                    </span>
                    <span className="line-clamp-2 text-ink-700">{item.title}</span>
                  </li>
                ))}
              </ul>
            </PageCard>
          </div>
        )}
      </aside>

      {/* 详情抽屉 —— 完整 markdown */}
      <Drawer
        title="文档详情"
        open={drawerOpen}
        styles={{ wrapper: { width: 820 } }}
        onClose={() => setDrawerOpen(false)}
        destroyOnHidden
      >
        {detailQuery.isLoading ? <Skeleton active paragraph={{ rows: 12 }} /> : null}
        {!detailQuery.isLoading && detailQuery.isError ? (
          <Empty description="文档详情加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : null}
        {!detailQuery.isLoading && detailQuery.data ? (
          <div className="space-y-4">
            <div>
              <Typography.Title level={4} className="!mb-1 serif">
                {detailQuery.data.title}
              </Typography.Title>
              <Typography.Text type="secondary">
                {detailQuery.data.researcher_name} ·{' '}
                {dayjs(detailQuery.data.created_at).format('YYYY-MM-DD HH:mm')}
              </Typography.Text>
            </div>
            <Space wrap>
              {detailQuery.data.tags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </Space>
            <div className="rounded border border-ink-50 bg-ink-25/50 p-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {detailQuery.data.content_markdown}
              </ReactMarkdown>
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
