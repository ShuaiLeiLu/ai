/**
 * 工作台首页 —— 复用盘前速览仪表板布局
 *
 * 布局与 overview/page.tsx 完全一致
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

export default function WorkstationHomePage() {
  return (
    <div className="space-y-3">
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={15} className="space-y-3">
          <HotNewsCard />
          <MarketIndicatorsCard />
          <StockRankCard />
          <IndustryBoardCard />
          <LimitUpLadderCard />
        </Col>
        <Col xs={24} lg={9} className="space-y-3">
          <AiDigestCard />
          <TrendsChartCard />
          <AnomaliesCard />
        </Col>
      </Row>
    </div>
  );
}
