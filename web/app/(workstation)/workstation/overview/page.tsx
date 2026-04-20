/**
 * 盘前速览页面 —— 仿目标站点仪表板布局
 *
 * 布局（左右两列）：
 * ┌─────────────────────┬──────────────┐
 * │ A股热讯（10 条）     │ 盘前热门解读   │
 * ├─────────────────────┤              │
 * │ 市场核心指标（4卡片）│              │
 * ├─────────────────────┼──────────────┤
 * │ 涨跌榜（涨/跌切换）  │ 市场强弱指标   │
 * ├─────────────────────┼──────────────┤
 * │ 行业板块涨跌         │ 异动名单      │
 * ├─────────────────────┤              │
 * │ 涨停天梯             │              │
 * └─────────────────────┴──────────────┘
 *
 * 数据流：各子组件独立通过 React Query hooks 拉取后端真实数据
 */
'use client';

import { Col, Row } from 'antd';
import {
  AiDigestCard,
  AnomaliesCard,
  HotNewsCard,
  IndustryBoardCard,
  LimitUpLadderCard,
  MarketIndicatorsCard,
  StockRankCard,
  TrendsChartCard,
} from '@/features/preopen/components';

export default function OverviewPage() {
  return (
    <div className="space-y-3">
      <Row gutter={[12, 12]}>
        {/* 左列：新闻 + 指标 + 涨跌榜 + 行业 + 天梯 */}
        <Col xs={24} lg={15} className="space-y-3">
          <HotNewsCard />
          <MarketIndicatorsCard />
          <StockRankCard />
          <IndustryBoardCard />
          <LimitUpLadderCard />
        </Col>

        {/* 右列：AI解读 + 趋势图 + 异动 */}
        <Col xs={24} lg={9} className="space-y-3">
          <AiDigestCard />
          <TrendsChartCard />
          <AnomaliesCard />
        </Col>
      </Row>
    </div>
  );
}
