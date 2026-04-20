'use client';

import { AntdRegistry } from '@ant-design/nextjs-registry';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App as AntdApp, ConfigProvider, theme } from 'antd';
import type { PropsWithChildren } from 'react';
import { useState } from 'react';

export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,            // 30秒内复用缓存，不重复请求
            refetchOnWindowFocus: false,   // 切换窗口不自动重新请求
            retry: 1,                     // 失败最多重试1次
          }
        }
      })
  );

  return (
    <AntdRegistry>
      <ConfigProvider
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            colorPrimary: '#7c3aed',
            borderRadius: 8,
            colorBgLayout: '#f5f7fb',
          },
          components: {
            Menu: {
              itemSelectedBg: '#f3f0ff',
              itemSelectedColor: '#7c3aed',
              subMenuItemBg: 'transparent',
            },
          },
        }}
      >
        <AntdApp>
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        </AntdApp>
      </ConfigProvider>
    </AntdRegistry>
  );
}
