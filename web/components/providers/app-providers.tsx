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
            colorInfo: '#7c3aed',
            borderRadius: 6,
            colorBgLayout: '#f8f9fa',
            colorTextBase: '#1e293b',
            colorLink: '#7c3aed',
            fontFamily: "'Inter', -apple-system, sans-serif",
          },
          components: {
            Layout: {
              bodyBg: '#f8f9fa',
              headerBg: '#ffffff',
              siderBg: '#ffffff',
            },
            Menu: {
              itemSelectedBg: '#f5f3ff',
              itemSelectedColor: '#7c3aed',
              itemHoverBg: '#f8fafc',
              itemActiveBg: '#f5f3ff',
              subMenuItemBg: 'transparent',
              itemMarginInline: 8,
              itemBorderRadius: 4,
            },
            Button: {
              controlHeight: 36,
              paddingInline: 16,
              fontWeight: 500,
              defaultBorderColor: '#e2e8f0',
              defaultShadow: 'none',
              primaryShadow: '0 2px 4px rgba(124, 58, 237, 0.1)',
            },
            Card: {
              headerFontSize: 15,
              paddingLG: 20,
              colorBorderSecondary: 'rgba(15, 23, 42, 0.04)',
            },
            Input: {
              activeBorderColor: '#7c3aed',
              hoverBorderColor: '#a78bfa',
              paddingInline: 12,
              controlHeight: 36,
            },
            Badge: {
              dotSize: 6,
            }
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
