'use client';

import { AntdRegistry } from '@ant-design/nextjs-registry';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App as AntdApp, Button, ConfigProvider, Result, theme } from 'antd';
import { Component, type ErrorInfo, type PropsWithChildren, type ReactNode } from 'react';
import { useState } from 'react';

/* ── React Error Boundary ── */
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class AppErrorBoundary extends Component<PropsWithChildren, ErrorBoundaryState> {
  constructor(props: PropsWithChildren) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[AppErrorBoundary] Uncaught error:', error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
          <Result
            status="error"
            title="页面发生了意外错误"
            subTitle={this.state.error?.message || '请尝试刷新页面'}
            extra={[
              <Button key="reload" type="primary" onClick={() => window.location.reload()}>
                刷新页面
              </Button>,
              <Button key="back" onClick={this.handleReset}>
                尝试恢复
              </Button>,
            ]}
          />
        </div>
      );
    }
    return this.props.children;
  }
}

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
            colorPrimary: '#1d4a34',
            colorInfo: '#1d4a34',
            borderRadius: 16,
            colorBgLayout: '#faf9f6',
            colorBgContainer: '#ffffff',
            colorTextBase: '#212c26',
            colorLink: '#1d4a34',
            fontFamily: "'Outfit', 'Inter', -apple-system, sans-serif",
          },
          components: {
            Layout: {
              bodyBg: '#faf9f6',
              headerBg: 'rgba(255, 255, 255, 0.7)',
              siderBg: 'rgba(255, 255, 255, 0.7)',
            },
            Menu: {
              itemSelectedBg: 'rgba(29, 74, 52, 0.06)',
              itemSelectedColor: '#1d4a34',
              itemHoverBg: 'rgba(29, 74, 52, 0.015)',
              itemActiveBg: 'rgba(29, 74, 52, 0.08)',
              subMenuItemBg: 'transparent',
              itemMarginInline: 8,
              itemBorderRadius: 10,
            },
            Button: {
              controlHeight: 38,
              paddingInline: 16,
              fontWeight: 500,
              defaultBorderColor: 'rgba(29, 74, 52, 0.06)',
              defaultBg: 'rgba(255, 255, 255, 0.8)',
              defaultShadow: 'none',
              primaryShadow: '0 2px 8px rgba(29, 74, 52, 0.12)',
            },
            Card: {
              headerFontSize: 15,
              paddingLG: 20,
              colorBgContainer: '#ffffff',
              colorBorderSecondary: 'rgba(29, 74, 52, 0.04)',
            },
            Input: {
              activeBorderColor: '#1d4a34',
              hoverBorderColor: '#285f44',
              colorBgContainer: 'rgba(255, 255, 255, 0.8)',
              colorBorder: 'rgba(29, 74, 52, 0.06)',
              paddingInline: 12,
              controlHeight: 38,
            },
            Badge: {
              dotSize: 6,
            }
          },
        }}
      >
        <AntdApp>
          <AppErrorBoundary>
            <QueryClientProvider client={queryClient}>
              {children}
            </QueryClientProvider>
          </AppErrorBoundary>
        </AntdApp>
      </ConfigProvider>
    </AntdRegistry>
  );
}
