/**
 * 工作台外壳 —— 编排层
 *
 * 子组件：
 *   - WorkstationSidebar         桌面端侧栏（>= md）
 *   - WorkstationSidebarMobile   移动端侧栏（Drawer 内容）
 *   - WorkstationTopBar          顶部导航
 *   - WorkstationTabBar          移动端底部 TabBar
 *   - AiDrawer                   右侧 AI 智囊抽屉
 *
 * 响应式断点：
 *   < md (768px)  —— 侧栏隐藏（Drawer），底部 TabBar，内容全宽
 *   >= md         —— 固定侧栏 + 顶栏，无 TabBar
 *
 * 鉴权：等待 token 恢复完成后再渲染子页面，避免空鉴权抢跑。
 */
'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Drawer, Layout, Space } from 'antd';
import type { PropsWithChildren } from 'react';

import { routes } from '@/lib/constants/routes';
import { useAppShellStore } from '@/stores/app-shell.store';
import { useUserSessionStore } from '@/stores/user-session.store';

import { AiDrawer } from './ai-drawer';
import {
  WorkstationSidebar,
  WorkstationSidebarMobile,
} from './workstation-sidebar';
import { WorkstationTabBar } from './workstation-tabbar';
import { WorkstationTopBar } from './workstation-topbar';

export function WorkstationShell({ children }: PropsWithChildren) {
  const router = useRouter();
  const pathname = usePathname();
  const collapsed = useAppShellStore((s) => s.collapsed);
  const toggleCollapsed = useAppShellStore((s) => s.toggleCollapsed);

  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);

  const accessToken = useUserSessionStore((s) => s.accessToken);
  const hydrated = useUserSessionStore((s) => s.hydrated);
  const hydrate = useUserSessionStore((s) => s.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!hydrated) return;
    if (accessToken) return;
    router.replace(routes.login);
  }, [hydrated, accessToken, router]);

  // 路由切换时关闭移动端 Drawer
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  if (!hydrated || !accessToken) {
    return <ShellLoading message={hydrated ? '正在跳转登录页...' : '正在恢复登录态...'} />;
  }

  // 桌面端：侧栏 fixed 顶格（无浮起、无圆角），主区通过左 padding 让位
  // 232 = sidebar width 展开 / 72 = 折叠
  const mainPaddingClass = collapsed ? 'md:pl-[72px]' : 'md:pl-[232px]';

  return (
    <Layout className="!min-h-screen !bg-ink-0">
      <WorkstationSidebar collapsed={collapsed} onToggle={toggleCollapsed} />

      <Drawer
        open={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        placement="left"
        closable={false}
        className="md:!hidden"
        styles={{ body: { padding: 0 } }}
      >
        <WorkstationSidebarMobile />
      </Drawer>

      <div
        className={['flex min-h-screen flex-col bg-ink-0 transition-[padding] duration-200', mainPaddingClass].join(' ')}
      >
        <WorkstationTopBar
          onOpenMobileNav={() => setMobileNavOpen(true)}
          onOpenAi={() => setAiOpen(true)}
        />
        <main className="flex-1 px-4 pb-24 pt-4 sm:px-6 sm:pb-10 sm:pt-6 lg:px-8">{children}</main>
      </div>

      <WorkstationTabBar onOpenAi={() => setAiOpen(true)} />
      <AiDrawer open={aiOpen} onClose={() => setAiOpen(false)} />
    </Layout>
  );
}

function ShellLoading({ message }: { message: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-0">
      <Space orientation="vertical" size={8} align="center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-ink-50 border-t-brand-600" />
        <span className="text-sm text-ink-400">{message}</span>
      </Space>
    </div>
  );
}
