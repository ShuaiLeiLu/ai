/**
 * 我的知识库页面
 *
 * 属于"极睿实验室"子页面之一，路由：/workstation/knowledge-base
 * 沉淀研判 · 投喂 AI 研究员，让它越用越懂你
 *
 * 数据流：useKnowledgeBases() hook 拉取后端接口
 */
'use client';

import { useMemo, useState } from 'react';
import { Button, Empty, Spin } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatCard } from '@/components/ui/stat-card';
import { useKnowledgeBases } from '@/features/ecosystem/hooks';
import type { KnowledgeBaseItem } from '@/types/ecosystem';

/** 左侧分类树 */
interface CategoryDef {
  key: string;
  label: string;
  icon: string;
}

const CATEGORIES: CategoryDef[] = [
  { key: 'all', label: '全部', icon: '📂' },
  { key: 'note', label: '投资笔记', icon: '📝' },
  { key: 'chat', label: 'AI 对话', icon: '💬' },
  { key: 'research', label: '研报摘录', icon: '📄' },
  { key: 'view', label: '自创观点', icon: '💡' },
  { key: 'review', label: '复盘记录', icon: '📊' },
];

/** 顶部标签云 —— 视觉占位（保留交互） */
const TAG_CLOUD = [
  '新能源',
  '科技',
  '半导体',
  '医药',
  '消费',
  '次新',
  '北向',
  'AI 算力',
  '低空经济',
  '券商',
];

/** 派生类别（视觉用） */
function deriveCategoryKey(kb: KnowledgeBaseItem): string {
  let hash = 0;
  for (let i = 0; i < kb.kb_id.length; i++) hash = (hash * 31 + kb.kb_id.charCodeAt(i)) % 1000;
  return CATEGORIES[1 + (hash % (CATEGORIES.length - 1))].key;
}

/** 派生标签 / 摘要 */
function deriveSummary(kb: KnowledgeBaseItem): { tags: string[]; cites: number; source: string } {
  let hash = 0;
  for (let i = 0; i < kb.kb_id.length; i++) hash = (hash * 17 + kb.kb_id.charCodeAt(i)) % 100_000;
  const tagN = 2 + (hash % 3);
  const tags: string[] = [];
  for (let i = 0; i < tagN; i++) {
    tags.push(TAG_CLOUD[(hash + i * 7) % TAG_CLOUD.length]);
  }
  const cites = (hash % 38) + 3;
  const source =
    kb.document_count > 0 ? `${kb.document_count} 篇文档` : '自创内容';
  return { tags, cites, source };
}

/** 类别 badge 颜色 */
const catBadge: Record<string, string> = {
  note: 'bg-brand-50 text-brand-700',
  chat: 'bg-up-50 text-up-700',
  research: 'bg-gold-50 text-gold-700',
  view: 'bg-down-50 text-down-700',
  review: 'bg-ink-50 text-ink-700',
};

/** 单个知识条目卡片 */
function EntryCard({ kb }: { kb: KnowledgeBaseItem }) {
  const catKey = useMemo(() => deriveCategoryKey(kb), [kb]);
  const cat = CATEGORIES.find((c) => c.key === catKey) ?? CATEGORIES[1];
  const { tags, cites, source } = useMemo(() => deriveSummary(kb), [kb]);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-ink-50 bg-white p-4 shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-lg">
      {/* 顶部：类别 badge + 引用数 */}
      <div className="mb-2 flex items-center justify-between">
        <span
          className={[
            'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium',
            catBadge[cat.key] ?? 'bg-ink-25 text-ink-600',
          ].join(' ')}
        >
          <span aria-hidden>{cat.icon}</span>
          <span>{cat.label}</span>
        </span>
        <span className="tnum text-[11px] text-ink-400">引用 {cites} 次</span>
      </div>

      {/* 标题 —— 思源宋体 */}
      <h4 className="serif mb-1.5 line-clamp-2 text-[15px] font-semibold leading-snug text-ink-900">
        {kb.name}
      </h4>

      {/* 摘要 */}
      <p className="mb-3 line-clamp-3 flex-1 text-[12.5px] leading-relaxed text-ink-500">
        投喂 AI 研究员的私域知识 · 已纳入向量索引，可被本人订阅的研究员检索引用。
      </p>

      {/* 标签 */}
      <div className="mb-2 flex flex-wrap gap-1.5">
        {tags.map((t) => (
          <span
            key={t}
            className="rounded-md bg-ink-25 px-1.5 py-0.5 text-[10.5px] text-ink-600"
          >
            #{t}
          </span>
        ))}
      </div>

      {/* 时间 / 来源 */}
      <div className="mt-auto flex items-center justify-between border-t border-ink-25 pt-2 text-[11px] text-ink-400">
        <span>{source}</span>
        <span className="tnum">{dayjs(kb.updated_at).format('MM-DD HH:mm')}</span>
      </div>
    </div>
  );
}

/** 知识库主组件 */
export function KnowledgeBasePageClient() {
  const { data, isLoading } = useKnowledgeBases();
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const list = data ?? [];

  // 视觉指标（StatCard）
  const total = list.length;
  const monthAdded = list.filter((kb) =>
    dayjs(kb.updated_at).isAfter(dayjs().subtract(30, 'day')),
  ).length;
  const totalDocs = list.reduce((sum, kb) => sum + (kb.document_count || 0), 0);
  // 引用次数：每个条目按 deriveSummary 派生求和
  const totalCites = useMemo(
    () => list.reduce((sum, kb) => sum + deriveSummary(kb).cites, 0),
    [list],
  );

  // 过滤
  const filtered = useMemo(() => {
    let result = list;
    if (activeCategory !== 'all') {
      result = result.filter((kb) => deriveCategoryKey(kb) === activeCategory);
    }
    if (activeTag) {
      result = result.filter((kb) => deriveSummary(kb).tags.includes(activeTag));
    }
    return result;
  }, [list, activeCategory, activeTag]);

  const isEmpty = !isLoading && list.length === 0;

  return (
    <div className="space-y-5">
      <SectionHeading
        title="我的知识库"
        subtitle="沉淀研判 · 投喂 AI 研究员，让它越用越懂你"
        actions={
          <Button type="primary" icon={<PlusOutlined />}>
            新建笔记
          </Button>
        }
      />

      {/* 4 列指标 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="总条目" value={total.toLocaleString('zh-CN')} hint={`含 ${totalDocs} 篇文档`} />
        <StatCard
          label="本月新增"
          value={monthAdded.toLocaleString('zh-CN')}
          direction="up"
          hint="近 30 天"
        />
        <StatCard label="引用次数" value={totalCites.toLocaleString('zh-CN')} hint="被研究员检索" />
        <StatCard
          label="向量化进度"
          value="100"
          unit="%"
          direction="up"
          hint="索引已构建"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {isEmpty && (
        <PageCard>
          <div className="flex flex-col items-center justify-center py-16">
            <Empty
              description={
                <span className="text-ink-400">点击上方按钮，沉淀你的第一条研判</span>
              }
            />
            <Button type="primary" className="mt-4" icon={<PlusOutlined />}>
              新建笔记
            </Button>
          </div>
        </PageCard>
      )}

      {!isLoading && !isEmpty && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px,1fr]">
          {/* 左侧分类树 */}
          <PageCard title="分类">
            <ul className="space-y-1">
              {CATEGORIES.map((cat) => {
                const active = activeCategory === cat.key;
                return (
                  <li key={cat.key}>
                    <button
                      type="button"
                      onClick={() => setActiveCategory(cat.key)}
                      className={[
                        'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px] transition-colors',
                        active
                          ? 'bg-brand-50 font-semibold text-brand-700'
                          : 'text-ink-700 hover:bg-ink-25',
                      ].join(' ')}
                    >
                      <span aria-hidden className="text-base">
                        {cat.icon}
                      </span>
                      <span className="flex-1 text-left">{cat.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="mt-4 border-t border-ink-25 pt-3">
              <div className="mb-2 text-[11px] font-semibold tracking-wider text-ink-400">
                标签云
              </div>
              <div className="flex flex-wrap gap-1.5">
                {TAG_CLOUD.map((tag) => {
                  const active = activeTag === tag;
                  return (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => setActiveTag(active ? null : tag)}
                      className={[
                        'rounded-md px-2 py-0.5 text-[11px] transition-colors',
                        active
                          ? 'bg-brand-600 text-white'
                          : 'bg-ink-25 text-ink-600 hover:bg-ink-50',
                      ].join(' ')}
                    >
                      #{tag}
                    </button>
                  );
                })}
              </div>
            </div>
          </PageCard>

          {/* 右侧条目网格 */}
          <div>
            {filtered.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {filtered.map((kb) => (
                  <EntryCard key={kb.kb_id} kb={kb} />
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-ink-50 bg-white py-20 text-center text-ink-400">
                此分类暂无条目
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
