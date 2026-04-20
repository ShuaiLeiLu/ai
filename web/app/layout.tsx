import type { Metadata } from 'next';

import { AppProviders } from '@/components/providers/app-providers';

import './globals.css';

export const metadata: Metadata = {
  title: '赛博投研',
  description: 'AI 原生投研工作台基础架构'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
