/**
 * 盘前速览页面 —— 仿目标站点仪表板布局
 *
 * 布局（左右两列）：
 * ┌─────────────────────┬──────────────┐
 * │ A股热讯（10 条）     │ 盘前热门解读   │
 * ├─────────────────────┤              │
 * │ 市场核心指标（4卡片）│ 市场强弱指标   │
 * ├─────────────────────┼──────────────┤
 * │ 行业板块涨跌 [lazy]  │ 涨跌榜 [lazy] │
 * │                     ├──────────────┤
 * │                     │ 涨停天梯[lazy]│
 * │                     ├──────────────┤
 * │                     │ 异动名单[lazy]│
 * └─────────────────────┴──────────────┘
 *
 * 数据流：各子组件独立通过 React Query hooks 拉取后端真实数据
 * 性能：首屏（HotNews / MarketIndicators / AiDigest / TrendsChart）同步加载；
 *       折叠以下卡片（IndustryBoard / StockRank / LimitUpLadder / Anomalies）
 *       使用 next/dynamic 懒加载，减少首屏 JS 解析量。
 */
'use client';

import { Col, Row, Skeleton } from 'antd';
import dynamic from 'next/dynamic';

// ── 首屏可见卡片：同步 import，立即可用 ────────────────────────────────────
import {
  AiDigestCard,
  HotNewsCard,
  MarketIndicatorsCard,
  TrendsChartCard,
} from '@/features/preopen/components';

// ── 折叠以下卡片：懒加载，不阻塞首屏 JS 解析 ─────────────────────────────
const cardSkeleton = <div className="rounded-xl border border-slate-100 bg-white p-5"><Skeleton active paragraph={{ rows: 5 }} /></div>;

const IndustryBoardCard = dynamic(
  () => import('@/features/preopen/components/IndustryBoardCard').then((m) => ({ default: m.IndustryBoardCard })),
  { loading: () => cardSkeleton }
);

const StockRankCard = dynamic(
  () => import('@/features/preopen/components/StockRankCard').then((m) => ({ default: m.StockRankCard })),
  { loading: () => cardSkeleton }
);

const LimitUpLadderCard = dynamic(
  () => import('@/features/preopen/components/LimitUpLadderCard').then((m) => ({ default: m.LimitUpLadderCard })),
  { loading: () => cardSkeleton }
);

const AnomaliesCard = dynamic(
  () => import('@/features/preopen/components/AnomaliesCard').then((m) => ({ default: m.AnomaliesCard })),
  { loading: () => cardSkeleton }
);

export default function OverviewPage() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {/* 左侧：侧重资讯与宏观指标 */}
        <Col xs={24} lg={12} className="space-y-4">
          <HotNewsCard />
          <MarketIndicatorsCard />
          <IndustryBoardCard />  {/* 懒加载 */}
        </Col>

        {/* 右侧：侧重 AI 分析、趋势与具体榜单 */}
        <Col xs={24} lg={12} className="space-y-4">
          <AiDigestCard />
          <TrendsChartCard />
          <StockRankCard />      {/* 懒加载 */}
          <LimitUpLadderCard />  {/* 懒加载 */}
          <AnomaliesCard />      {/* 懒加载 */}
        </Col>
      </Row>
    </div>
  );
}
