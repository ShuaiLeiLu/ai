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
        <div className="flex flex-col gap-0.5">
          {(data ?? []).slice(0, 10).map((item: HotNewsItem, index: number) => (
            <div
              key={item.news_id}
              className="group relative flex items-center gap-3 rounded-md px-2 py-[9px] transition-all hover:bg-slate-50"
            >
              {/* Hover 时的左侧指示线 */}
              <div className="absolute left-0 top-1/2 h-0 w-[2px] -translate-y-1/2 bg-brand-500 transition-all group-hover:h-3/5" />

              {/* 序号 */}
              <span
                className={`w-6 shrink-0 text-center text-[13px] font-semibold tabular-nums ${
                  index < 3 ? 'text-rose-500' : 'text-slate-400'
                }`}
              >
                {String(index + 1).padStart(2, '0')}
              </span>

              {/* 标题 */}
              <a
                href={item.jump_target}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-0 flex-1 truncate text-[13px] leading-5 text-slate-700 transition-colors group-hover:text-brand-600"
              >
                {item.title}
              </a>

              {/* 热度数字 */}
              <div className="flex shrink-0 items-center gap-1">
                <div className="h-1 w-1 rounded-full bg-rose-400 animate-pulse" />
                <span className="text-[11px] font-medium tabular-nums text-slate-400">
                  {item.heat}
                </span>
              </div>
            </div>
          ))}
        </div>
      </PageCard>
    </StateWrapper>
  );
}
