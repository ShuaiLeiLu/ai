import type { Metadata } from 'next';
import { Inter, Noto_Serif_SC } from 'next/font/google';

import { AppProviders } from '@/components/providers/app-providers';

import './globals.css';

/**
 * 全局字体加载
 *
 *  - Inter：现代等宽，数字/正文体验
 *  - 思源宋体（Noto Serif SC）：中文衬线，用于大标题与重点叙事
 *
 * 通过 CSS 变量暴露给 Tailwind / globals.css 使用，避免 FOUT。
 */
const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const notoSerifSC = Noto_Serif_SC({
  subsets: ['latin'],
  weight: ['500', '700'],
  variable: '--font-serif-sc',
  display: 'swap',
  preload: false,
});

export const metadata: Metadata = {
  title: '极睿智投',
  description: 'AI 原生投研工作台基础架构',
  icons: {
    icon: '/logo.svg',
    apple: '/logo.svg',
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" className={`${inter.variable} ${notoSerifSC.variable}`}>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
