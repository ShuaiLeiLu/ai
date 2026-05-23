'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { Route } from 'next';
import { Avatar, Badge, Button, Dropdown, type MenuProps } from 'antd';
import {
  BellOutlined,
  CrownOutlined,
  LoginOutlined,
  LogoutOutlined,
  MenuOutlined,
  RobotOutlined,
  SearchOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons';

import { routes } from '@/lib/constants/routes';
import { useUserSessionStore } from '@/stores/user-session.store';
import { TradingClock } from './trading-clock';

interface TopBarProps {
  onOpenMobileNav: () => void;
  onOpenAi: () => void;
  unreadCount?: number;
}

export function WorkstationTopBar({ onOpenMobileNav, onOpenAi, unreadCount = 0 }: TopBarProps) {
  const router = useRouter();
  const user = useUserSessionStore((s) => s.user);
  const logout = useUserSessionStore((s) => s.logout);

  const avatarMenu: MenuProps['items'] = user
    ? [
        { key: 'profile', icon: <UserOutlined />, label: user.nickname, disabled: true, className: '!cursor-default' },
        { type: 'divider' },
        { key: 'account', icon: <SettingOutlined />, label: '账户中心', onClick: () => router.push(routes.billing) },
        { key: 'plans', icon: <CrownOutlined />, label: '会员套餐', onClick: () => router.push(routes.billing) },
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

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-ink-50 bg-white/85 px-3 backdrop-blur-md sm:h-16 sm:px-6">
      {/* 移动端汉堡按钮 */}
      <Button
        type="text"
        icon={<MenuOutlined />}
        onClick={onOpenMobileNav}
        className="md:!hidden !text-ink-600"
        aria-label="打开导航"
      />

      {/* 日期 + 开盘倒计时 —— 桌面端面包屑区 */}
      <TradingClock />

      <div className="flex-1" />

      {/* 搜索框 —— 桌面端宽，平板端收为图标 */}
      <button
        type="button"
        className="hidden h-9 w-56 items-center gap-2.5 rounded-xl bg-ink-25 px-3 text-[12.5px] text-ink-400 transition hover:bg-ink-50 lg:flex"
      >
        <SearchOutlined className="text-ink-400" />
        <span className="flex-1 truncate text-left">搜索股票、研究员、研报…</span>
        <kbd className="hidden rounded border border-ink-50 bg-white px-1.5 py-0.5 text-[10px] text-ink-400 lg:inline">⌘K</kbd>
      </button>

      <div className="flex items-center gap-1 sm:gap-2">
        {/* 通知 */}
        <Badge dot={unreadCount > 0} offset={[-4, 4]} color="#c0362c">
          <Button type="text" icon={<BellOutlined />} className="!text-ink-500 hover:!text-brand-600" />
        </Badge>

        {/* VIP 标签 —— 桌面端可见 */}
        <Link
          href={routes.billing as Route}
          className="hidden items-center gap-1.5 rounded-full border border-gold-300 bg-gold-warm px-2.5 py-1 text-[11.5px] font-semibold text-gold-600 transition hover:brightness-105 lg:inline-flex"
        >
          <CrownOutlined className="text-[11px]" />
          {user ? user.membership_level : '开通 VIP'}
        </Link>

        {/* 电池余量 */}
        <Link href={routes.billing as Route} className="hidden items-center gap-1 px-2 text-[12.5px] font-semibold text-ink-700 hover:text-brand-600 sm:inline-flex">
          <ThunderboltOutlined className="text-gold-500" />
          <span className="tnum">{user?.battery_balance ?? 0}</span>
        </Link>

        {/* AI 智囊 */}
        <Button
          type="primary"
          onClick={onOpenAi}
          icon={<RobotOutlined />}
          className="!h-9 !rounded-xl !px-2.5 sm:!px-3.5"
        >
          <span className="hidden sm:inline text-[12.5px] font-medium">AI 智囊</span>
        </Button>

        <div className="mx-1 hidden h-4 w-px bg-ink-50 sm:block" />

        {/* 头像 */}
        <Dropdown menu={{ items: avatarMenu }} trigger={['click']} placement="bottomRight">
          <div className="flex cursor-pointer items-center gap-2">
            <span className="hidden text-[12.5px] font-semibold text-ink-700 sm:inline">
              {user?.nickname || '未登录'}
            </span>
            <Avatar
              size={32}
              icon={!user && <UserOutlined />}
              className="!bg-brand-600 !text-white border-2 border-white"
              style={{ boxShadow: '0 0 0 1px rgba(23,20,16,.06)' }}
            >
              {user?.nickname ? user.nickname.slice(0, 1) : null}
            </Avatar>
          </div>
        </Dropdown>
      </div>
    </header>
  );
}
