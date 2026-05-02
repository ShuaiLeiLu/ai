import { Col, Row, Skeleton } from 'antd';

/**
 * 盘前速览骨架屏 —— overview/page.tsx JS chunk 加载期间立即展示
 *
 * 列宽严格对齐实际布局 lg={12}/lg={12}
 * 首屏可见区域：左列 HotNews + MarketIndicators，右列 AiDigest + TrendsChart
 * 折叠以下卡片（IndustryBoard / StockRank / LimitUpLadder / Anomalies）不在骨架屏中，
 * 由各卡片内部的 StateWrapper/Skeleton 处理。
 */
export default function OverviewLoading() {
  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        {/* 左列 */}
        <Col xs={24} lg={12} className="space-y-4">
          {/* HotNewsCard 骨架 */}
          <div className="rounded-xl border border-slate-100 bg-white p-5">
            <div className="mb-4 h-4 w-20 rounded bg-slate-100" />
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 py-2">
                <div className="h-3 w-5 rounded bg-slate-100" />
                <div className="h-3 flex-1 rounded bg-slate-100" style={{ width: `${70 + (i % 3) * 10}%` }} />
                <div className="h-3 w-8 rounded bg-slate-100" />
              </div>
            ))}
          </div>

          {/* MarketIndicatorsCard 骨架 —— 4 格统计卡 */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-slate-100 bg-white px-4 py-3">
                <Skeleton active paragraph={{ rows: 2 }} title={false} />
              </div>
            ))}
          </div>
        </Col>

        {/* 右列 */}
        <Col xs={24} lg={12} className="space-y-4">
          {/* AiDigestCard 骨架 */}
          <div className="rounded-xl border border-slate-100 bg-white p-5">
            <Skeleton active title={{ width: 120 }} paragraph={{ rows: 4 }} />
          </div>

          {/* TrendsChartCard 骨架 */}
          <div className="rounded-xl border border-slate-100 bg-white p-5">
            <Skeleton active title={{ width: 100 }} paragraph={{ rows: 5 }} />
          </div>
        </Col>
      </Row>
    </div>
  );
}
