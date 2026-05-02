/**
 * 资讯分析页面 —— 左右分栏 8:4 布局
 *
 * 左侧（8/12）：资讯一览（Segmented 分类 + “只看重要”开关 + 热门股票标签过滤 + 新闻列表）
 * 右侧（4/12）：AI智能分析彩色卡片 + 股票概要 + 24小时热股榜
 *
 * 数据流：
 *  - FilterControls  控制筛选参数 (category / important_only / stock_code)
 *  - NewsFeed        根据筛选参数拉取新闻流
 *  - AIPanels        2×2 彩色卡片（市场总结/热点追踪/市场变盘/行业关注）
 *  - HotNewsList     24小时热股排行榜
 */
'use client';

import { useState } from 'react';
import { Typography } from 'antd';

import {
  AIPanels,
  FilterControls,
  HotNewsList,
  NewsFeed,
  StockSummaryCard,
} from '@/features/news-analysis/components';
import type { GetNewsFeedParams } from '@/types/news-analysis';

export default function NewsAnalysisPage() {
  // 筛选参数：分类 + 是否只看重要 + 股票代码
  const [filters, setFilters] = useState<GetNewsFeedParams>({
    category: 'all',
    important_only: false,
  });

  /** 局部更新筛选参数（合并更新） */
  const handleFilterChange = (next: Partial<GetNewsFeedParams>) => {
    setFilters((prev) => ({ ...prev, ...next }));
  };

  return (
    <div className="h-[calc(100vh-64px-40px)] overflow-hidden">
      <div className="grid h-full grid-cols-12 gap-6">
        {/* Left: News feed (Scrollable) */}
        <div className="col-span-12 flex h-full flex-col gap-4 lg:col-span-8 overflow-hidden">
          <div className="rounded-xl bg-white p-5 shadow-fintech border border-slate-100/50">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-4 w-1 rounded-full bg-brand-500"></div>
                <Typography.Title level={5} className="!mb-0 !text-base !font-bold">
                  资讯一览
                </Typography.Title>
              </div>
            </div>
            <FilterControls filters={filters} onFilterChange={handleFilterChange} />
          </div>

          <div className="flex-1 rounded-xl bg-white shadow-fintech border border-slate-100/50 overflow-y-auto no-scrollbar">
            <NewsFeed filters={filters} />
          </div>
        </div>

        {/* Right: AI analysis + hot stocks (No internal scroll) */}
        <div className="col-span-12 space-y-5 lg:col-span-4 pb-10">
          <AIPanels />
          <div className="rounded-xl bg-white shadow-fintech border border-slate-100/50 p-1">
             <StockSummaryCard stockCode={filters.stock_code} />
          </div>
          <HotNewsList />
        </div>
      </div>
    </div>
  );
}
