/**
 * 24小时热股解析榜
 *
 * 排名列表，前 3 名用红色序号圆点，其余用灰色。
 * 每行显示：排名 + 标题 + 热度分数。
 * 通过 useHotNews() hook 拉取后端数据。
 */
'use client';

import { Alert, Skeleton, Typography } from 'antd';
import { FireOutlined } from '@ant-design/icons';

import { useHotNews } from '@/features/news-analysis/hooks';

export function HotNewsList() {
  const { data, isLoading, isError, error } = useHotNews();

  if (isError) {
    return (
      <div className="rounded-lg bg-white p-4">
        <Alert
          message="热门资讯加载失败"
          description={error instanceof Error ? error.message : '未知错误'}
          type="error"
          showIcon
        />
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <FireOutlined className="text-orange-500" />
        <Typography.Title level={5} className="!mb-0">
          24小时热股解析
        </Typography.Title>
      </div>

      {isLoading && <Skeleton active paragraph={{ rows: 6 }} />}

      {!isLoading && (
        <div className="space-y-1">
          {(data ?? []).map((item) => (
            <div
              key={item.rank}
              className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-slate-50"
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded text-xs font-bold text-white ${
                  item.rank <= 3 ? 'bg-rose-500' : 'bg-slate-300'
                }`}
              >
                {item.rank}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm">{item.title}</span>
              <span className="shrink-0 text-xs text-slate-400">{item.heat_score}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
