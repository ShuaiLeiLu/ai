/**
 * A股热讯卡片 —— 同花顺7x24快讯 + 财联社快讯
 *
 * 设计目标（对照设计稿）：
 *   序号（前三位红色）+ 类别标签（突发/利好红，研报/公告灰）+ 标题 + 热度
 *   "查看更多 →" 链接跳转资讯分析页
 *
 * 数据流：useHotNewsQuery → 后端 /preopen/hot-news
 */
'use client';

import Link from 'next/link';
import { RightOutlined } from '@ant-design/icons';

import { PageCard } from '@/components/ui/page-card';
import { useHotNewsQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import { routes } from '@/lib/constants/routes';
import type { HotNewsItem } from '@/types/preopen';

type TagCategory = '突发' | '利好' | '利空' | '研报' | '公告' | '海外' | '监管' | '数据';

/** 标签着色：突发/利好红，利空绿，其余灰 */
function tagOf(item: HotNewsItem): { label: TagCategory; cls: string } {
  const t = item.title;
  if (/突发|突|紧急|快讯：/.test(t)) return { label: '突发', cls: 'bg-up-50 text-up-600' };
  if (/研报|券商|评级|目标价|首次覆盖|增持|买入/.test(t)) return { label: '研报', cls: 'bg-ink-25 text-ink-600' };
  if (/公告|拟分红|派现|回购|减持|股东大会/.test(t)) return { label: '公告', cls: 'bg-ink-25 text-ink-600' };
  if (/美股|港股|纳指|英伟达|苹果|海外|欧洲|日经/.test(t)) return { label: '海外', cls: 'bg-ink-25 text-ink-600' };
  if (/证监会|央行|银保监|监管|规范|查处/.test(t)) return { label: '监管', cls: 'bg-ink-25 text-ink-600' };
  if (/CPI|PPI|GDP|LPR|数据|社融|信贷/.test(t)) return { label: '数据', cls: 'bg-ink-25 text-ink-600' };
  if (item.sentiment === 'bullish') return { label: '利好', cls: 'bg-up-50 text-up-600' };
  if (item.sentiment === 'bearish') return { label: '利空', cls: 'bg-down-50 text-down-600' };
  return { label: '突发', cls: 'bg-ink-25 text-ink-600' };
}

/** 格式化热度数字 */
function fmtHeat(v: number) {
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
  return v.toLocaleString('zh-CN');
}

export function HotNewsCard() {
  const { data, isLoading, error } = useHotNewsQuery();

  const extra = (
    <Link href={routes.newsAnalysis} className="text-sm text-ink-400 hover:text-brand-600">
      查看更多 <RightOutlined className="text-xs" />
    </Link>
  );

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="A股热讯 · 实时">
      <PageCard title="A股热讯 · 实时" extra={extra} density="compact">
        <div className="flex flex-col gap-0.5">
          {(data ?? []).slice(0, 10).map((item: HotNewsItem, index: number) => {
            const tag = tagOf(item);
            return (
              <div
                key={item.news_id}
                className="group relative flex items-center gap-2.5 rounded-md px-2 py-2 transition-colors hover:bg-ink-25"
              >
                {/* 序号（前三热色） */}
                <span
                  className={`w-6 shrink-0 text-center text-[13px] font-bold tabular-nums ${
                    index < 3 ? 'text-up-500' : 'text-ink-200'
                  }`}
                >
                  {String(index + 1).padStart(2, '0')}
                </span>

                {/* 类别标签 */}
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${tag.cls}`}
                >
                  {tag.label}
                </span>

                {/* 标题 */}
                <a
                  href={item.jump_target}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="min-w-0 flex-1 truncate text-[13px] leading-5 text-ink-800 transition-colors group-hover:text-brand-600"
                >
                  {item.title}
                </a>

                {/* 热度 */}
                <span
                  className={`shrink-0 text-[11px] font-medium tabular-nums ${
                    index < 3 ? 'text-up-500' : 'text-ink-400'
                  }`}
                >
                  {index < 3 ? '🔥 ' : ''}
                  {fmtHeat(item.heat)}
                </span>
              </div>
            );
          })}
        </div>
      </PageCard>
    </StateWrapper>
  );
}
