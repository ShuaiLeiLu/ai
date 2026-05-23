'use client';

import Link from 'next/link';
import type { Route } from 'next';
import { usePathname } from 'next/navigation';
import {
  DashboardOutlined,
  LineChartOutlined,
  RobotOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';

import { routes } from '@/lib/constants/routes';

interface TabBarProps {
  onOpenAi: () => void;
}

interface TabDef {
  key: string;
  label: string;
  href?: string;
  icon: React.ReactNode;
  match?: (p: string) => boolean;
  center?: boolean;
  onTap?: () => void;
}

/**
 * 移动端底部 TabBar —— 仅在 < md 显示
 * 中间凸起按钮：呼出 AI 智囊
 */
export function WorkstationTabBar({ onOpenAi }: TabBarProps) {
  const pathname = usePathname();

  const tabs: TabDef[] = [
    {
      key: 'overview',
      label: '速览',
      href: routes.preopen,
      icon: <DashboardOutlined style={{ fontSize: 19 }} />,
      match: (p) => p.startsWith(routes.preopen) || p === routes.workstation,
    },
    {
      key: 'trading',
      label: '交易',
      href: routes.trading,
      icon: <LineChartOutlined style={{ fontSize: 19 }} />,
      match: (p) => p.startsWith(routes.trading),
    },
    { key: 'ai', label: 'AI', icon: <RobotOutlined style={{ fontSize: 22 }} />, center: true, onTap: onOpenAi },
    {
      key: 'researchers',
      label: '研究员',
      href: routes.aiResearcher,
      icon: <TeamOutlined style={{ fontSize: 19 }} />,
      match: (p) => p.startsWith(routes.aiResearcher) || p.startsWith(routes.researcherMarket),
    },
    {
      key: 'me',
      label: '我的',
      href: routes.billing,
      icon: <UserOutlined style={{ fontSize: 19 }} />,
      match: (p) => p.startsWith(routes.billing),
    },
  ];

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-ink-50 bg-white/90 px-1 safe-bottom backdrop-blur-md md:hidden"
      style={{ paddingTop: 6 }}
    >
      {tabs.map((tab) => {
        const active = tab.match?.(pathname) ?? false;
        if (tab.center) {
          return (
            <button
              key={tab.key}
              type="button"
              onClick={tab.onTap}
              className="flex flex-col items-center justify-end gap-0.5 pt-0 text-brand-600"
              aria-label="呼出 AI 智囊"
            >
              <span className="-mt-2 flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-dark text-white shadow-brand">
                {tab.icon}
              </span>
              <span className="text-[10px] font-semibold">{tab.label}</span>
            </button>
          );
        }
        return (
          <Link
            key={tab.key}
            href={(tab.href ?? '#') as Route}
            className={[
              'flex flex-col items-center justify-center gap-0.5 py-1.5 text-[10px]',
              active ? 'text-brand-600 font-semibold' : 'text-ink-400',
            ].join(' ')}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
