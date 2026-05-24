'use client';

import { Alert, Empty, Skeleton } from 'antd';

import { useNewsFeed } from '@/features/news-analysis/hooks';
import { GetNewsFeedParams } from '@/types/news-analysis';
import type { NewsFeedItem } from '@/types/news-analysis';
import { NewsItem } from './NewsItem';

interface NewsFeedProps {
  filters: GetNewsFeedParams;
  onAnalyzeNews?: (item: NewsFeedItem) => void;
  onSelectStock?: (stock: NewsFeedItem['stock_relations'][number]) => void;
}

export function NewsFeed({ filters, onAnalyzeNews, onSelectStock }: NewsFeedProps) {
  const { data: feed, isLoading, isError, error } = useNewsFeed(filters);

  if (isLoading) {
    return (
      <div className="space-y-0 divide-y divide-slate-100">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="p-4">
            {/* 标题行：星标 + 标题 + 按钮 */}
            <div className="mb-2 flex items-start gap-2">
              <div className="h-4 w-4 mt-1 rounded bg-slate-100 animate-pulse shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-5 w-4/5 rounded bg-slate-100 animate-pulse" />
                <div className="h-3 w-48 rounded bg-slate-50 animate-pulse" />
              </div>
              <div className="h-6 w-16 rounded bg-slate-50 animate-pulse shrink-0" />
            </div>
            {/* 摘要 */}
            <div className="mb-2 space-y-1">
              <div className="h-3.5 w-full rounded bg-slate-50 animate-pulse" />
              <div className="h-3.5 w-3/4 rounded bg-slate-50 animate-pulse" />
            </div>
            {/* 标签 */}
            <div className="flex gap-2">
              <div className="h-5 w-20 rounded bg-blue-50 animate-pulse" />
              <div className="h-5 w-16 rounded bg-blue-50 animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Alert
        className="m-4"
        message="资讯加载失败"
        description={error instanceof Error ? error.message : '未知错误'}
        type="error"
        showIcon
      />
    );
  }

  if (!feed || feed.length === 0) {
    return <Empty className="py-10" description="暂无相关资讯" />;
  }

  return (
    <div className="h-full overflow-y-auto">
      {feed.map((item) => (
        <NewsItem
          key={item.news_id}
          item={item}
          onAnalyze={onAnalyzeNews}
          onSelectStock={onSelectStock}
        />
      ))}
    </div>
  );
}
