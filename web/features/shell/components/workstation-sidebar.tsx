'use client';

import Link from 'next/link';
import type { Route } from 'next';
import { usePathname } from 'next/navigation';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';

import { Logo } from '@/components/ui/logo';
import { workstationNavGroups, type NavItem } from '@/features/navigation/config/workstation-nav';
import { routes } from '@/lib/constants/routes';

/**
 * 侧栏导航项
 *
 * 视觉对齐设计稿：
 *   - 左侧 3px 强调条（选中状态）
 *   - hover 时浅墨绿底色
 *   - 右侧 badge 角标
 */
function NavRow({ item, active, collapsed }: { item: NavItem; active: boolean; collapsed: boolean }) {
  // antd icon 组件没有显式 className，但运行时支持 — 用 any 规避 TS 严格模式
  const Icon = item.icon as unknown as React.ComponentType<{ className?: string }>;

  const cls = [
    'group relative flex items-center gap-3 rounded-[10px] py-[9px] text-[13.5px] leading-none transition-colors',
    collapsed ? 'justify-center px-2' : 'pl-4 pr-3',
    active
      ? 'bg-brand-50 text-brand-700 font-semibold'
      : 'text-ink-600 hover:bg-brand-50/60 hover:text-ink-900',
  ].join(' ');

  const inner = (
    <>
      {/* 选中态左侧强调条（贴在 item 内部最左侧，紧靠圆角） */}
      {active && (
        <span
          aria-hidden
          className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-sm bg-brand-600"
        />
      )}
      <Icon
        className={[
          'shrink-0 text-[16px]',
          active ? 'opacity-100' : 'opacity-75 group-hover:opacity-100',
        ].join(' ')}
      />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {item.badge !== undefined && item.badge !== null && (
            <span className="ml-auto rounded-full bg-up-50 px-1.5 py-px text-[10px] font-semibold leading-4 text-up-600">
              {item.badge}
            </span>
          )}
        </>
      )}
    </>
  );

  if (item.href) {
    return (
      <Link href={item.href as Route} className={cls}>
        {inner}
      </Link>
    );
  }
  return <div className={cls}>{inner}</div>;
}

interface SidebarBodyProps {
  collapsed?: boolean;
  showPromo?: boolean;
}

/**
 * 路由匹配：
 *  - 当 pathname 命中 item.href 的前缀时激活
 *  - 特例：pathname === '/workstation' 时，激活默认首页（overview）
 */
function isItemActive(pathname: string, href: string | undefined): boolean {
  if (!href) return false;
  if (pathname === '/workstation' && href === routes.preopen) return true;
  return pathname.startsWith(href);
}

function SidebarBody({ collapsed = false, showPromo = true }: SidebarBodyProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <Link
        href={routes.workstation as Route}
        className={[
          'group flex items-center',
          collapsed ? 'justify-center px-2 py-5' : 'gap-3 px-5 py-5',
        ].join(' ')}
      >
        <Logo size={32} />
        {!collapsed && (
          <div className="min-w-0">
            <div className="serif truncate text-[17px] font-bold tracking-[0.5px] text-ink-900 group-hover:text-brand-600">
              极睿智投
            </div>
            <div className="-mt-0.5 truncate text-[10px] tracking-[2px] text-ink-400">
              JIRUI · AI
            </div>
          </div>
        )}
      </Link>

      {/* Menu 分组 */}
      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {workstationNavGroups.map((group, gi) => (
          <div key={group.key} className={gi === 0 ? '' : 'mt-3'}>
            {!collapsed && (
              <div className="px-3 pb-1.5 pt-3 text-[10px] font-semibold tracking-[2px] text-ink-400">
                {group.title.split('').join(' ')}
              </div>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = isItemActive(pathname, item.href);
                return (
                  <NavRow
                    key={item.key}
                    item={item}
                    active={active}
                    collapsed={collapsed}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* VIP 推广卡 */}
      {showPromo && !collapsed && (
        <div className="px-3 pb-4">
          <Link
            href={routes.billing as Route}
            className="block overflow-hidden rounded-xl border border-gold-300 bg-gold-warm p-3.5 transition hover:brightness-105"
          >
            <div className="text-[10.5px] font-semibold tracking-[1.5px] text-gold-600">
              VIP 专享
            </div>
            <div className="serif mt-1 text-[14px] font-bold leading-tight text-ink-900">
              解锁全部 AI 研究员
            </div>
            <div className="mt-2 inline-flex items-center gap-1 rounded-lg bg-ink-900 px-2.5 py-1 text-[11px] font-semibold text-gold-500">
              立即升级 →
            </div>
          </Link>
        </div>
      )}
    </div>
  );
}

interface WorkstationSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

/**
 * 桌面端侧栏（>= md）
 */
export function WorkstationSidebar({ collapsed, onToggle }: WorkstationSidebarProps) {
  return (
    <aside
      // 顶格全高侧栏：无圆角、无浮起阴影，紧贴左边
      // 背景用 bg-paper（米黄渐变）与主区 ink-0 形成柔和分隔
      className="fixed inset-y-0 left-0 z-20 hidden flex-col border-r border-ink-50 bg-paper transition-[width] duration-200 md:flex"
      style={{ width: collapsed ? 72 : 232 }}
    >
      <SidebarBody collapsed={collapsed} />

      <button
        type="button"
        aria-label={collapsed ? '展开侧栏' : '收起侧栏'}
        onClick={onToggle}
        className="absolute -right-3 top-20 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-ink-50 bg-white text-ink-400 shadow-card transition hover:scale-110 hover:text-brand-600"
      >
        {collapsed ? <RightOutlined style={{ fontSize: 10 }} /> : <LeftOutlined style={{ fontSize: 10 }} />}
      </button>
    </aside>
  );
}

/**
 * 移动端侧栏（在 Drawer 中渲染）
 */
export function WorkstationSidebarMobile() {
  return <SidebarBody collapsed={false} showPromo={false} />;
}
