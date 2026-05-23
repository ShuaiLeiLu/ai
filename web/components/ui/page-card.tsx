import type { PropsWithChildren, ReactNode } from 'react';

type Accent = 'brand' | 'gold' | 'up' | 'down';
type Density = 'comfortable' | 'compact';

interface PageCardProps extends PropsWithChildren {
  /** 卡片标题 */
  title?: ReactNode;
  /** 右上角附加内容（链接/按钮等） */
  extra?: ReactNode;
  /** 副标题：标题下方的辅助说明 */
  subtitle?: ReactNode;
  /** 标题前的强调条颜色 */
  accent?: Accent;
  /** 内边距密度 */
  density?: Density;
  /** 卡片主题 —— light（默认白底） / dark（品牌墨绿底，用于焦点卡） */
  tone?: 'light' | 'dark';
  /** 内容贴边（无内边距，自定义布局时用） */
  flush?: boolean;
  /** 底部内容（如查看更多等） */
  footer?: ReactNode;
  className?: string;
}

const accentClass: Record<Accent, string> = {
  brand: 'bg-brand-600',
  gold: 'bg-gold-500',
  up: 'bg-up-500',
  down: 'bg-down-500',
};

/**
 * 通用卡片基元
 *
 * 用法：
 *   <PageCard title="A股热讯" extra={<More />}>...</PageCard>
 *   <PageCard title="AI 早间研判" tone="dark" accent="gold">...</PageCard>
 *   <PageCard title="板块涨跌" density="compact" flush>...</PageCard>
 */
export function PageCard({
  title,
  subtitle,
  extra,
  accent = 'brand',
  density = 'comfortable',
  tone = 'light',
  flush = false,
  footer,
  className,
  children,
}: PageCardProps) {
  const isDark = tone === 'dark';

  const rootClass = [
    'rounded-2xl overflow-hidden',
    isDark
      ? 'bg-brand-dark text-ink-0 border border-brand-700/40'
      : 'bg-white border border-ink-50',
    'shadow-card',
    className ?? '',
  ].join(' ');

  const headerClass = [
    'flex items-center justify-between gap-3',
    density === 'compact' ? 'px-4 py-3' : 'px-5 py-3.5',
    isDark ? 'border-b border-white/10' : 'border-b border-ink-25',
  ].join(' ');

  const bodyClass = flush
    ? ''
    : density === 'compact'
      ? 'px-3 py-2'
      : 'px-5 py-4';

  const footerClass = [
    'border-t',
    isDark ? 'border-white/10' : 'border-ink-25',
    density === 'compact' ? 'px-4 py-2.5' : 'px-5 py-3',
    'text-xs',
    isDark ? 'text-ink-0/60' : 'text-ink-400',
  ].join(' ');

  return (
    <section className={rootClass}>
      {(title || extra) && (
        <header className={headerClass}>
          <div className="min-w-0 flex-1">
            {title && (
              <h3
                className={[
                  'flex items-center text-[14.5px] font-semibold tracking-[0.01em]',
                  isDark ? 'text-white' : 'text-ink-900',
                ].join(' ')}
              >
                <span
                  aria-hidden
                  className={[
                    'mr-2 inline-block h-3.5 w-[3px] rounded-sm',
                    isDark && accent === 'brand' ? 'bg-gold-500' : accentClass[accent],
                  ].join(' ')}
                />
                <span className="truncate">{title}</span>
              </h3>
            )}
            {subtitle && (
              <div
                className={[
                  'mt-0.5 truncate text-[11.5px]',
                  isDark ? 'text-ink-0/55 pl-[14px]' : 'text-ink-400 pl-[14px]',
                ].join(' ')}
              >
                {subtitle}
              </div>
            )}
          </div>
          {extra && (
            <div className={['shrink-0 text-xs', isDark ? 'text-ink-0/60 hover:text-gold-300' : 'text-ink-400 hover:text-brand-600'].join(' ')}>
              {extra}
            </div>
          )}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
      {footer && <div className={footerClass}>{footer}</div>}
    </section>
  );
}
