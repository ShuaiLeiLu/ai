/**
 * 资讯筛选控件
 *
 * 包含三部分：
 *  1. Segmented 分类切换（全部/精选/公告/研报）
 *  2. Switch “只看重要” 开关
 *  3. 热门股票标签（点击进行股票维度过滤）
 */
'use client';

import { Segmented, Switch, Tag } from 'antd';

import { useHotStocks } from '@/features/news-analysis/hooks';
import type { GetNewsFeedParams, NewsCategory } from '@/types/news-analysis';

interface FilterControlsProps {
  filters: GetNewsFeedParams;
  onFilterChange: (next: Partial<GetNewsFeedParams>) => void;
}

/** 分类 Tab 选项 */
const categoryOptions: Array<{ label: string; value: NewsCategory }> = [
  { label: '全部', value: 'all' },
  { label: '精选', value: 'flash' },
  { label: '公告', value: 'announcement' },
  { label: '研报', value: 'report' },
];

export function FilterControls({ filters, onFilterChange }: FilterControlsProps) {
  const { data: hotStocks, isLoading } = useHotStocks();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented
          value={filters.category ?? 'all'}
          options={categoryOptions}
          onChange={(value) => onFilterChange({ category: value as NewsCategory })}
        />
        <Switch
          checked={Boolean(filters.important_only)}
          onChange={(checked) => onFilterChange({ important_only: checked })}
          checkedChildren="只看重要"
          unCheckedChildren="全部"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Tag
          color={!filters.stock_code ? 'purple' : 'default'}
          className="cursor-pointer"
          onClick={() => onFilterChange({ stock_code: undefined })}
        >
          全部
        </Tag>
        {!isLoading &&
          hotStocks?.map((stock) => (
            <Tag
              key={stock.stock_code}
              color={filters.stock_code === stock.stock_code ? 'purple' : 'default'}
              className="cursor-pointer"
              onClick={() => onFilterChange({ stock_code: stock.stock_code })}
            >
              {stock.stock_name} {stock.heat}
            </Tag>
          ))}
      </div>
    </div>
  );
}
