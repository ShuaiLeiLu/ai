'use client';

import { Alert, Skeleton } from 'antd';
import React from 'react';

import { PageCard } from '@/components/ui/page-card';

interface StateWrapperProps {
  isLoading: boolean;
  error: Error | null;
  data: unknown;
  nonTradingDayMessage?: string;
  children: React.ReactNode;
  title: string;
}

export function StateWrapper({
  isLoading,
  error,
  data,
  children,
  title,
  nonTradingDayMessage
}: StateWrapperProps) {
  if (isLoading) {
    return (
      <PageCard title={title}>
        <Skeleton active paragraph={{ rows: 4 }} />
      </PageCard>
    );
  }

  if (error) {
    return (
      <PageCard title={title}>
        <Alert message="数据加载失败" description={error.message} type="error" showIcon />
      </PageCard>
    );
  }

  if (nonTradingDayMessage) {
    return (
      <PageCard title={title}>
        <Alert message="非交易日" description={nonTradingDayMessage} type="info" showIcon />
      </PageCard>
    );
  }

  if (!data || (Array.isArray(data) && data.length === 0)) {
    return (
      <PageCard title={title}>
        <Alert message="暂无数据" type="info" showIcon />
      </PageCard>
    );
  }

  return <>{children}</>;
}
