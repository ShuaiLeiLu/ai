import type { ReactNode } from 'react';

type Direction = 'up' | 'down' | 'flat';

interface StatCardProps {
  /** 指标名 */
  label: ReactNode;
  /** 主数值 */
  value: ReactNode;
  /** 单位（百分号、亿等），与数值同色但更小 */
  unit?: ReactNode;
  /** 辅助说明 */
  hint?: ReactNode;
  /** 涨跌方向 —— 决定数值颜色 */
  direction?: Direction;
  /** 紧凑模式 —— 用于 4 列网格 */
  compact?: boolean;
  /** 内嵌（无背景与边框）—— 用于已经在卡片中的网格 */
  embedded?: boolean;
}

const dirText: Record<Direction, string> = {
  up: 'text-up-600',
  down: 'text-down-600',
  flat: 'text-ink-800',
};

/**
 * 指标小卡 —— 4/6 列网格中等距展示
 *
 * <StatCard label="两市成交" value="9,847" unit="亿" direction="up" hint="+12.4%" />
 */
export function StatCard({
  label,
  value,
  unit,
  hint,
  direction = 'flat',
  compact = false,
  embedded = false,
}: StatCardProps) {
  const root = embedded
    ? 'bg-ink-25 rounded-lg'
    : 'bg-white border border-ink-50 rounded-xl shadow-card';

  return (
    <div className={[root, compact ? 'px-3 py-2.5' : 'px-4 py-3'].join(' ')}>
      <div className="text-[11px] text-ink-400">{label}</div>
      <div className={['mt-0.5 font-bold leading-tight tnum', compact ? 'text-lg' : 'text-[20px]', dirText[direction]].join(' ')}>
        {value}
        {unit && <span className="ml-0.5 text-sm font-medium">{unit}</span>}
      </div>
      {hint && <div className="mt-1 truncate text-[10.5px] text-ink-400">{hint}</div>}
    </div>
  );
}
