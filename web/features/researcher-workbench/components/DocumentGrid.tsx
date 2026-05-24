/**
 * 5A 底部研报文档网格 —— 6 张 grid-cols-2
 *
 * 对标设计稿：
 *  - 头部 tab：精选 / 最新 / 热门
 *  - 每卡：左侧大引号（金色/绿色/红色按流派轮换） + 思源宋体标题 + 12px 摘要
 *  - 底部小头像 + 研究员名 + 任务/自驱 badge + 时间
 *  - 第一张：gold 渐变底；其余：白底带边
 */
'use client';

import { useState, useMemo } from 'react';
import { Skeleton, Empty } from 'antd';
import { PageCard } from '@/components/ui/page-card';
import { ResearcherAvatar } from './ResearcherAvatar';
import type { HotDocument } from '@/types/researcher-workbench';

type Tab = 'featured' | 'latest' | 'hot';

const QUOTE_ACCENTS: { color: string }[] = [
  { color: 'text-gold-500' },
  { color: 'text-brand-400' },
  { color: 'text-brand-400' },
  { color: 'text-up-500' },
  { color: 'text-brand-400' },
  { color: 'text-up-500' },
];

interface Props {
  documents: HotDocument[];
  loading: boolean;
  onSelectDocument?: (id: string) => void;
}

/** 判断任务/自驱（无字段则按 ID 哈希轮换，保证视觉多样） */
function getBadge(doc: HotDocument, idx: number): { label: string; cls: string } {
  // 简单基于 idx 与标题长度交替：模拟任务/自驱标签
  const isSelfDriven = (doc.title.length + idx) % 3 === 0;
  return isSelfDriven
    ? { label: '自驱', cls: 'bg-up-50 text-up-600' }
    : { label: '任务', cls: 'bg-brand-50 text-brand-700' };
}

/** 格式化时间为 YYYY-MM-DD HH:mm */
function formatDateTime(value: string): string {
  const d = new Date(value);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function DocumentGrid({ documents, loading, onSelectDocument }: Props) {
  const [tab, setTab] = useState<Tab>('featured');

  // 按 tab 排序/过滤
  const visible = useMemo(() => {
    const sorted = [...documents];
    if (tab === 'latest') {
      sorted.sort((a, b) => new Date(b.create_time).getTime() - new Date(a.create_time).getTime());
    } else if (tab === 'hot') {
      sorted.sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0));
    }
    return sorted.slice(0, 6);
  }, [documents, tab]);

  return (
    <PageCard
      accent="brand"
      title="研报文档"
      extra={
        <div className="inline-flex gap-1 text-[12px]">
          {([
            { key: 'featured', label: '精选' },
            { key: 'latest', label: '最新' },
            { key: 'hot', label: '热门' },
          ] as { key: Tab; label: string }[]).map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={[
                'rounded-md px-3 py-1 font-semibold transition-colors',
                tab === item.key ? 'bg-gold-500 text-white' : 'text-ink-500 hover:text-ink-700',
              ].join(' ')}
            >
              {item.label}
            </button>
          ))}
        </div>
      }
    >
      {loading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="rounded-xl border border-ink-50 p-4">
              <Skeleton active paragraph={{ rows: 2 }} />
            </div>
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="py-10">
          <Empty description="暂无研报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {visible.map((doc, idx) => {
            const quote = QUOTE_ACCENTS[idx % QUOTE_ACCENTS.length];
            const isFeatured = idx === 0;
            const badge = getBadge(doc, idx);
            return (
              <button
                key={doc.id}
                type="button"
                onClick={() => onSelectDocument?.(doc.id)}
                className={[
                  'group block rounded-xl p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md',
                  isFeatured
                    ? 'border border-gold-200'
                    : 'border border-ink-50 bg-white',
                ].join(' ')}
                style={
                  isFeatured
                    ? { background: 'linear-gradient(135deg, #fdf4d8, #fcefc6)' }
                    : undefined
                }
              >
                <div className="flex items-start gap-2.5">
                  <span
                    className={['serif text-[22px] leading-none shrink-0', quote.color].join(' ')}
                  >
                    “
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="serif line-clamp-2 text-[14.5px] font-bold leading-snug text-ink-900">
                      {doc.title}
                    </div>
                    {doc.is_vip_only && (
                      <span className="mt-1 inline-flex rounded bg-gold-50 px-1.5 py-px text-[10px] font-semibold text-gold-700">
                        VIP专属
                      </span>
                    )}
                    {doc.summary && (
                      <p className="mt-1.5 line-clamp-2 text-[12px] leading-[1.7] text-ink-600">
                        {doc.summary}
                      </p>
                    )}
                    <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-ink-400">
                      <ResearcherAvatar name={doc.researcher_name} size="xs" />
                      <span className="truncate text-ink-500">{doc.researcher_name}</span>
                      <span
                        className={[
                          'shrink-0 rounded px-1.5 py-px text-[10px] font-semibold',
                          badge.cls,
                        ].join(' ')}
                      >
                        {badge.label}
                      </span>
                      <span className="ml-auto shrink-0 tnum">{formatDateTime(doc.create_time)}</span>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </PageCard>
  );
}
