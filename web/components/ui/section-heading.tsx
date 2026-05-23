import type { ReactNode } from 'react';

interface SectionHeadingProps {
  title: ReactNode;
  subtitle?: ReactNode;
  /** 右侧操作区（如时间戳、按钮组） */
  actions?: ReactNode;
  /** 是否使用衬线大标题（用于页面级标题） */
  serif?: boolean;
}

/**
 * 页面级标题行 —— 标题/副标题 + 右侧操作区
 */
export function SectionHeading({ title, subtitle, actions, serif = true }: SectionHeadingProps) {
  return (
    <div className="mb-4 flex flex-col items-start justify-between gap-2 sm:mb-5 sm:flex-row sm:items-end">
      <div className="min-w-0">
        <h1
          className={[
            'text-xl sm:text-[22px] font-bold tracking-[0.01em] text-ink-900',
            serif ? 'serif' : '',
          ].join(' ')}
        >
          {title}
        </h1>
        {subtitle && <div className="mt-1 text-[12.5px] text-ink-400">{subtitle}</div>}
      </div>
      {actions && <div className="flex items-center gap-3 text-xs text-ink-400">{actions}</div>}
    </div>
  );
}
