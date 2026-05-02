import { Col, Row, Skeleton } from 'antd';

/**
 * AI研究员页骨架屏 —— JS chunk 加载期间立即展示，消除白屏
 *
 * 布局对齐实际页面：左侧 w-52 面板 + 右侧主区域（研究员卡片 + 热门文档 + 排行榜）
 */
export default function AIResearcherLoading() {
  return (
    <div className="flex flex-col gap-3 md:flex-row" style={{ minHeight: 'calc(100vh - 56px - 40px)' }}>
      {/* 左侧面板骨架 */}
      <div className="w-full shrink-0 rounded-lg border border-slate-100 bg-white p-4 md:w-52">
        <div className="mb-4 h-4 w-24 rounded bg-slate-100" />
        <div className="mb-3 h-9 w-full rounded-md bg-slate-100" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} avatar active paragraph={{ rows: 0 }} />
          ))}
        </div>
      </div>

      {/* 右侧主区域骨架 */}
      <div className="min-w-0 flex-1">
        <Row gutter={[16, 16]}>
          {/* 研究员卡片区 + 热门文档 */}
          <Col xs={24} xl={15} className="space-y-4">
            {/* 研究员卡片 */}
            <div className="rounded-xl border border-slate-100 bg-white p-5">
              <div className="mb-4 h-4 w-20 rounded bg-slate-100" />
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {[1, 2].map((i) => (
                  <div key={i} className="rounded-xl border border-slate-100 p-4">
                    <Skeleton avatar active paragraph={{ rows: 3 }} />
                  </div>
                ))}
              </div>
            </div>

            {/* 热门文档 */}
            <div className="rounded-xl border border-slate-100 bg-white p-5">
              <div className="mb-4 h-4 w-32 rounded bg-slate-100" />
              <div className="flex gap-4 overflow-hidden">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-56 w-64 shrink-0 rounded-xl border border-slate-100 p-4">
                    <Skeleton active paragraph={{ rows: 3 }} title={false} />
                  </div>
                ))}
              </div>
            </div>
          </Col>

          {/* 排行榜 */}
          <Col xs={24} xl={9}>
            <div className="rounded-xl border border-slate-100 bg-white p-5">
              <div className="mb-4 h-4 w-24 rounded bg-slate-100" />
              <Skeleton active paragraph={{ rows: 6 }} />
            </div>
          </Col>
        </Row>
      </div>
    </div>
  );
}
