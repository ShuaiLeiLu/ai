/**
 * A股热讯卡片 —— 同花顺7x24快讯 + 财联社快讯
 *
 * 布局：紧凑序号列表，左侧序号+标题，右侧热度数字
 * 右上角"查看更多"链接跳转资讯分析页
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

export function HotNewsCard() {
  const { data, isLoading, error } = useHotNewsQuery();

  /** "查看更多" 链接 → 跳转资讯分析页 */
  const extra = (
    <Link href={routes.newsAnalysis} className="text-sm text-brand-500 hover:text-brand-600">
      查看更多 <RightOutlined className="text-xs" />
    </Link>
  );

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="A股热讯">
      <PageCard title="A股热讯" extra={extra}>
        <div className="divide-y divide-slate-50">
          {(data ?? []).slice(0, 10).map((item: HotNewsItem, index: number) => (
            <div
              key={item.news_id}
              className="flex items-center gap-2 px-0 py-[7px] transition-colors hover:bg-slate-50"
            >
              {/* 序号：前3橙红色加粗，其余灰色 */}
              <span
                className={`w-5 shrink-0 text-center text-sm font-bold ${
                  index < 3 ? 'text-rose-500' : 'text-slate-400'
                }`}
              >
                {index + 1}
              </span>

              {/* 标题 —— 紧凑单行截断 */}
              <a
                href={item.jump_target}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-0 flex-1 truncate text-[13px] leading-5 text-slate-700 hover:text-brand-500"
              >
                {item.title}
              </a>

              {/* 热度数字 —— 右对齐 */}
              <span className="shrink-0 text-xs tabular-nums text-slate-400">
                {item.heat}
              </span>
            </div>
          ))}
        </div>
      </PageCard>
    </StateWrapper>
  );
}
