/**
 * 工作台外壳 Shell
 *
 * 包含：
 *  - 左侧边栏（桌面端固定 / 移动端 Drawer 抽屉）
 *  - 顶部导航栏（汉堡菜单 + 产品介绍/工作台/使用说明 + 搜索/通知/VIP/电池/头像下拉）
 *  - 内容区域
 *
 * 响应式：
 *  - md 以下：侧边栏隐藏，通过汉堡菜单打开 Drawer
 *  - md 以上：侧边栏固定，支持折叠
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { Route } from 'next';
import { usePathname, useRouter } from 'next/navigation';
import {
  Avatar,
  Badge,
  Button,
  Drawer,
  Dropdown,
  Layout,
  Menu,
  Space,
  Tooltip,
} from 'antd';
import {
  BellOutlined,
  CloseOutlined,
  CrownOutlined,
  LeftOutlined,
  LoginOutlined,
  LogoutOutlined,
  MenuOutlined,
  RightOutlined,
  SearchOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import type { PropsWithChildren } from 'react';

import { Logo } from '@/components/ui/logo';
import { workstationNav, type NavItem } from '@/features/navigation/config/workstation-nav';
import { routes } from '@/lib/constants/routes';
import { useAppShellStore } from '@/stores/app-shell.store';
import { useUserSessionStore } from '@/stores/user-session.store';

const { Header, Sider, Content } = Layout;

function buildMenuItems(items: NavItem[]): MenuProps['items'] {
  return items.map((item) => {
    if (item.children) {
      return {
        key: item.key,
        icon: <item.icon />,
        label: item.label,
        children: buildMenuItems(item.children),
      };
    }
    return {
      key: item.key,
      icon: <item.icon />,
      label: item.href ? <Link href={item.href as Route}>{item.label}</Link> : item.label,
    };
  });
}

function findSelectedKeys(pathname: string, items: NavItem[]): string[] {
  for (const item of items) {
    if (item.href && pathname.startsWith(item.href)) {
      return [item.key];
    }
    if (item.children) {
      const found = findSelectedKeys(pathname, item.children);
      if (found.length) return found;
    }
  }
  return [];
}

function findOpenKeys(pathname: string, items: NavItem[]): string[] {
  for (const item of items) {
    if (item.children) {
      const found = findSelectedKeys(pathname, item.children);
      if (found.length) return [item.key];
    }
  }
  return [];
}

export function WorkstationShell({ children }: PropsWithChildren) {
  const collapsed = useAppShellStore((s) => s.collapsed);
  const toggleCollapsed = useAppShellStore((s) => s.toggleCollapsed);
  const pathname = usePathname();
  const router = useRouter();

  // 移动端抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 用户会话：首屏保持 SSR/CSR 一致，挂载后再从 localStorage 恢复。
  const accessToken = useUserSessionStore((s) => s.accessToken);
  const user = useUserSessionStore((s) => s.user);
  const hydrated = useUserSessionStore((s) => s.hydrated);
  const logout = useUserSessionStore((s) => s.logout);
  const hydrate = useUserSessionStore((s) => s.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  // 登录态确认后，若无 token，跳登录页
  useEffect(() => {
    if (!hydrated) return;
    if (accessToken) return;
    router.replace(routes.login);
  }, [hydrated, accessToken, router]);

  // 路由切换时自动关闭移动端抽屉
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  const selectedKeys = findSelectedKeys(pathname, workstationNav);
  const defaultOpenKeys = findOpenKeys(pathname, workstationNav);
  const unreadNotificationCount = 0;

  /** 头像下拉菜单 */
  const avatarMenuItems: MenuProps['items'] = user
    ? [
        {
          key: 'profile',
          icon: <UserOutlined />,
          label: user.nickname,
          disabled: true,
          className: '!cursor-default',
        },
        { type: 'divider' },
        {
          key: 'account',
          icon: <SettingOutlined />,
          label: '账户中心',
          onClick: () => router.push(routes.billing),
        },
        {
          key: 'plans',
          icon: <CrownOutlined />,
          label: '会员套餐',
          onClick: () => router.push(routes.billing),
        },
        { type: 'divider' },
        {
          key: 'logout',
          icon: <LogoutOutlined />,
          label: '退出登录',
          danger: true,
          onClick: () => {
            logout();
            router.push(routes.login);
          },
        },
      ]
    : [
        {
          key: 'login',
          icon: <LoginOutlined />,
          label: '登录 / 注册',
          onClick: () => router.push(routes.login),
        },
      ];

  /** 侧边栏菜单内容（桌面端和移动端共用） */
  const sidebarContent = (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5">
        <Logo size={28} />
        <span className="text-base font-bold tracking-tight text-slate-900">极睿智投</span>
      </div>
      {/* Nav */}
      <div className="flex-1 overflow-y-auto">
        <Menu
          mode="inline"
          selectedKeys={selectedKeys}
          defaultOpenKeys={defaultOpenKeys}
          items={buildMenuItems(workstationNav)}
          className="!border-r-0"
        />
      </div>
    </div>
  );

  // 先等待 localStorage 中的 token 恢复，避免子页面在空鉴权状态下抢跑请求。
  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Space direction="vertical" size={8} align="center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-500" />
          <span className="text-sm text-slate-400">正在恢复登录态...</span>
        </Space>
      </div>
    );
  }

  if (!accessToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Space direction="vertical" size={8} align="center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-brand-500" />
          <span className="text-sm text-slate-400">正在跳转登录页...</span>
        </Space>
      </div>
    );
  }

  return (
    <Layout className="min-h-screen">
      {/* ── 桌面端固定侧边栏（md 以上） ── */}
      <Sider
        width={220}
        collapsedWidth={64}
        collapsed={collapsed}
        className="!fixed !left-0 !top-0 !bottom-0 !z-20 !bg-white border-r border-slate-100/60 max-md:!hidden shadow-[1px_0_10px_rgba(15,23,42,0.02)]"
        trigger={null}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-3 px-6 py-5 group cursor-pointer transition-colors">
            <Logo size={28} />
            {!collapsed && (
              <span className="text-base font-bold tracking-tight text-slate-900 group-hover:text-brand-600 transition-colors">极睿智投</span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto px-2">
            <Menu
              mode="inline"
              selectedKeys={selectedKeys}
              defaultOpenKeys={defaultOpenKeys}
              items={buildMenuItems(workstationNav)}
              className="!border-r-0 !bg-transparent custom-side-menu"
            />
          </div>
          {/* 折叠按钮 */}
          <button
            onClick={toggleCollapsed}
            className="absolute -right-3 top-24 z-30 flex h-6 w-6 items-center justify-center rounded-full border border-slate-100 bg-white text-slate-400 shadow-sm hover:text-brand-500 transition-all hover:scale-110 active:scale-95"
          >
            {collapsed ? <RightOutlined style={{ fontSize: 10 }} /> : <LeftOutlined style={{ fontSize: 10 }} />}
          </button>
        </div>
      </Sider>

      {/* ── 移动端 Drawer 侧边栏（md 以下） ── */}
      <Drawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        placement="left"
        closable={false}
        className="md:!hidden"
        styles={{ wrapper: { width: 260 }, body: { padding: 0 } }}
      >
        {sidebarContent}
      </Drawer>

      {/* ── Main ── */}
      <Layout className="transition-all duration-300 md:ml-[var(--sidebar-w)]" style={{ '--sidebar-w': collapsed ? '64px' : '220px' } as React.CSSProperties}>
        {/* 顶部导航 */}
        <Header className="!sticky !top-0 !z-10 flex items-center justify-between border-b border-slate-100/60 !bg-white/80 backdrop-blur-md !px-4 sm:!px-8 !h-16 !leading-[64px]">
          {/* 左侧：移动端汉堡菜单 */}
          <div className="flex flex-1 items-center gap-2">
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerOpen(true)}
              className="md:!hidden !text-slate-600 hover:!bg-slate-50"
            />
          </div>

          {/* 中间导航 —— 小屏隐藏，根据当前路由动态高亮 */}
          <Space size={32} className="hidden lg:flex">
            {[
              { label: '产品介绍', href: '/', match: (p: string) => p === '/' },
              { label: '工作台', href: '/workstation', match: (p: string) => p.startsWith('/workstation') && !p.startsWith(routes.userGuide) },
              { label: '使用说明', href: routes.userGuide, match: (p: string) => p.startsWith(routes.userGuide) },
            ].map((item) => {
              const active = item.match(pathname);
              return (
                <Link
                  key={item.href}
                  href={item.href as Route}
                  className={`relative text-[14px] transition-all duration-200 ${
                    active 
                      ? 'font-semibold text-brand-600 after:absolute after:-bottom-[21px] after:left-0 after:h-[2px] after:w-full after:bg-brand-500' 
                      : 'text-slate-500 hover:text-brand-500'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </Space>

          {/* 右侧工具区 */}
          <div className="flex flex-1 items-center justify-end gap-5">
            {/* 极简搜索按钮 */}
            <Button
              type="text"
              icon={<SearchOutlined />}
              className="!text-slate-400 hover:!text-brand-500"
            />

            <div className="flex items-center gap-4">
              <Badge dot={unreadNotificationCount > 0} offset={[-2, 4]} color="#7c3aed">
                <Button type="text" icon={<BellOutlined />} className="!text-slate-400 hover:!text-brand-500" />
              </Badge>

              {/* VIP - 极简文字版 */}
              <Link href={routes.billing} className="group">
                <div className="flex items-center gap-1.5 transition-colors">
                  <CrownOutlined className="text-amber-500 text-xs" />
                  <span className="text-xs font-semibold text-slate-500 group-hover:text-amber-600">
                    {user ? user.membership_level : '开通VIP'}
                  </span>
                </div>
              </Link>

              {/* 电池 - 极简文字版 */}
              <div className="flex items-center gap-1.5">
                <ThunderboltOutlined className="text-amber-500 text-xs" />
                <span className="text-xs font-bold text-slate-500 tabular-nums">{user?.battery_balance ?? 0}</span>
              </div>
            </div>

            <div className="h-4 w-[1px] bg-slate-200" />

            {/* 用户中心 - 纯净头像 */}
            <Dropdown menu={{ items: avatarMenuItems }} trigger={['click']} placement="bottomRight">
              <div className="flex items-center gap-3 cursor-pointer group">
                <div className="hidden sm:block text-right">
                  <div className="text-[13px] font-semibold text-slate-700 group-hover:text-brand-500 transition-colors">
                    {user?.nickname || '未登录'}
                  </div>
                </div>
                <Avatar
                  size={32}
                  icon={<UserOutlined />}
                  className="bg-slate-100 !text-slate-400 border border-slate-200 group-hover:border-brand-200 transition-all"
                />
              </div>
            </Dropdown>
          </div>
        </Header>

        {/* 页面内容 */}
        <Content className="p-4 sm:p-8 bg-[#f8f9fa] min-h-[calc(100vh-64px)]">{children}</Content>
      </Layout>
    </Layout>
  );
}
