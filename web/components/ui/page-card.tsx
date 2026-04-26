import { Card } from 'antd';
import type { PropsWithChildren, ReactNode } from 'react';

interface PageCardProps extends PropsWithChildren {
  title: ReactNode;
  extra?: ReactNode;
}

export function PageCard({ title, extra, children }: PageCardProps) {
  return (
    <Card
      title={<span className="text-[15px] font-semibold text-slate-800">{title}</span>}
      extra={extra}
      bordered={false}
      className="rounded-xl shadow-fintech border border-slate-100/50"
      styles={{
        header: { borderBottom: '1px solid rgba(15, 23, 42, 0.04)', padding: '0 20px', minHeight: '48px' },
        body: { padding: '16px 20px' }
      }}
    >
      {children}
    </Card>
  );
}
