/**
 * 盘前速览决策驾驶舱布局。
 *
 * /workstation 与 /workstation/overview 共享此组件，避免两处入口布局漂移。
 */
'use client';

import { Skeleton } from 'antd';
import dynamic from 'next/dynamic';

import { SectionHeading } from '@/components/ui/section-heading';
import {
  AiDigestCard,
  HotNewsCard,
  MarketHero,
  MarketIndicatorsCard,
  TrendsChartCard,
} from '@/features/preopen/components';

const cardSkeleton = (
  <div className="rounded-2xl border border-ink-50 bg-white p-5 shadow-card">
    <Skeleton active paragraph={{ rows: 5 }} />
  </div>
);

const IndustryBoardCard = dynamic(
  () => import('@/features/preopen/components/IndustryBoardCard').then((m) => ({ default: m.IndustryBoardCard })),
  { loading: () => cardSkeleton },
);

const StockRankCard = dynamic(
  () => import('@/features/preopen/components/StockRankCard').then((m) => ({ default: m.StockRankCard })),
  { loading: () => cardSkeleton },
);

const LimitUpLadderCard = dynamic(
  () => import('@/features/preopen/components/LimitUpLadderCard').then((m) => ({ default: m.LimitUpLadderCard })),
  { loading: () => cardSkeleton },
);

const AnomaliesCard = dynamic(
  () => import('@/features/preopen/components/AnomaliesCard').then((m) => ({ default: m.AnomaliesCard })),
  { loading: () => cardSkeleton },
);

export function OverviewDashboard() {
  return (
    <div className="mx-auto w-full max-w-[1920px]">
      <SectionHeading
        title="盘前速览 · 今日决策驾驶舱"
        subtitle="您配置的自驱研究员已完成夜间研判，重点线索已上推至首屏"
        actions={
          <span className="flex items-center gap-1.5">
            <span className="pulse-dot" />
            <span>数据实时同步</span>
          </span>
        }
      />

      <MarketHero />

      {/* 三列信息流：让各列独立向下排列，避免短卡被高卡片拖出大面积留白。 */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <AiDigestCard />
          <HotNewsCard />
        </div>

        <div className="space-y-4 xl:col-span-4">
          <IndustryBoardCard />
          <MarketIndicatorsCard />
          <TrendsChartCard />
        </div>

        <div className="space-y-4 lg:col-span-2 xl:col-span-3">
          <LimitUpLadderCard />
          <AnomaliesCard />
          <StockRankCard />
        </div>
      </div>
    </div>
  );
}
