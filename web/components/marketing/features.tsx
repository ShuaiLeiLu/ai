import { Col, Row } from 'antd';
import { PageCard } from '@/components/ui/page-card';

export function Features() {
  return (
    <Row gutter={[24, 24]}>
      <Col xs={24} lg={8}>
        <PageCard title="AI 研究员">
          利用 AI 驱动的研究员，自动执行重复性研究任务，并获得可行的见解。
        </PageCard>
      </Col>
      <Col xs={24} lg={8}>
        <PageCard title="全面的数据集成">
          无缝访问来自多个来源的实时和历史市场数据。
        </PageCard>
      </Col>
      <Col xs={24} lg={8}>
        <PageCard title="可定制的工作区">
          创建您自己的个性化工作区，其中包含您需要的工具和数据。
        </PageCard>
      </Col>
    </Row>
  );
}
