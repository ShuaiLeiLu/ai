import { Button, Space, Typography } from 'antd';
import Link from 'next/link';
import { routes } from '@/lib/constants/routes';

export function Hero() {
  return (
    <section className="rounded-[32px] border border-slate-200 bg-white/90 px-8 py-24 text-center shadow-panel backdrop-blur">
      <Space direction="vertical" size={20}>
        <Typography.Title level={1} className="!mb-0 !max-w-4xl !text-5xl">
          探索、分析、交易
        </Typography.Title>
        <Typography.Paragraph className="!mb-0 !max-w-3xl !text-lg">
          您的下一代 AI 驱动的投资研究工作站。
        </Typography.Paragraph>
        <Space wrap>
          <Link href={routes.workstation}>
            <Button type="primary" size="large">
              开始使用
            </Button>
          </Link>
          <Link href={routes.login}>
            <Button size="large">了解更多</Button>
          </Link>
        </Space>
      </Space>
    </section>
  );
}
