'use client';

import { Button, Tag, Typography } from 'antd';
import { StarFilled } from '@ant-design/icons';

import { NewsFeedItem } from '@/types/news-analysis';

interface NewsItemProps {
  item: NewsFeedItem;
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  return `${month}-${day} ${hour}:${minute}`;
}

export function NewsItem({ item }: NewsItemProps) {
  return (
    <div className="border-b border-slate-100 p-4 transition-colors hover:bg-slate-50">
      <div className="mb-2 flex items-start gap-2">
        {item.is_important && <StarFilled className="mt-1 text-amber-500" />}
        <div className="flex-1">
          <Typography.Text className="text-base font-semibold">{item.title}</Typography.Text>
          <div className="mt-1 text-xs text-slate-500">
            {item.source} · {formatTime(item.publish_time)} · {item.category}
          </div>
        </div>
        <Button size="small">AI 解读</Button>
      </div>

      <Typography.Paragraph className="!mb-2 !text-sm !text-slate-600">
        {item.summary}
      </Typography.Paragraph>

      <div className="flex flex-wrap gap-2">
        {item.stock_relations.map((stock) => (
          <Tag key={`${item.news_id}-${stock.stock_code}`} color="blue">
            {stock.stock_name} {stock.stock_code}
          </Tag>
        ))}
      </div>
    </div>
  );
}
