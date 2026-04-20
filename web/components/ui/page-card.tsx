import { Card } from 'antd';
import type { PropsWithChildren, ReactNode } from 'react';

interface PageCardProps extends PropsWithChildren {
  title: ReactNode;
  extra?: ReactNode;
}

export function PageCard({ title, extra, children }: PageCardProps) {
  return (
    <Card title={title} extra={extra} className="rounded-2xl border border-slate-200 shadow-panel">
      {children}
    </Card>
  );
}
