/**
 * 使用说明页面
 *
 * 路由：/workstation/user-guide
 * 顶部导航栏"使用说明"链接指向此页面。
 * 包含平台各功能模块的使用指南，以卡片 + 步骤列表形式呈现。
 */
import type { Metadata } from 'next';

import { UserGuidePageClient } from '@/features/user-guide/components/UserGuidePageClient';

export const metadata: Metadata = {
  title: '使用说明',
};

export default function UserGuidePage() {
  return <UserGuidePageClient />;
}
