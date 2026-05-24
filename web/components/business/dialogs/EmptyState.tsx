'use client';

import type { ReactNode } from 'react';

export type EmptyStateType = 'empty' | 'error' | 'no-result' | 'need-vip';

export interface EmptyStateAction {
  label: string;
  onClick?: () => void;
  /** 链接文案颜色：brand=松烟绿（默认）/ gold=神州金 */
  tone?: 'brand' | 'gold';
}

export interface EmptyStateProps {
  type?: EmptyStateType;
  /** 自定义大图标，覆盖默认 emoji */
  icon?: ReactNode;
  /** 自定义标题，覆盖默认文案 */
  title?: ReactNode;
  /** 辅助文本 */
  message?: ReactNode;
  /** 行动链接 */
  action?: EmptyStateAction;
  /** 额外 className */
  className?: string;
  /** 缩小尺寸（用于较小卡片） */
  size?: 'sm' | 'md';
}

interface Preset {
  icon: string;
  title: string;
  message: string;
  actionTone: 'brand' | 'gold';
  actionLabel?: string;
}

const PRESETS: Record<EmptyStateType, Preset> = {
  empty: {
    icon: '📭',
    title: '暂无数据',
    message: '当前数据正在准备中，请稍后查看',
    actionTone: 'brand'
  },
  error: {
    icon: '⚠️',
    title: '加载失败',
    message: '网络异常',
    actionTone: 'brand',
    actionLabel: '点击重试'
  },
  'no-result': {
    icon: '🔍',
    title: '没有找到结果',
    message: '试试别的关键词',
    actionTone: 'brand',
    actionLabel: '清除筛选'
  },
  'need-vip': {
    icon: '🔒',
    title: '需 VIP 解锁',
    message: '此内容仅 VIP 可见',
    actionTone: 'gold',
    actionLabel: '开通 VIP →'
  }
};

export function EmptyState({
  type = 'empty',
  icon,
  title,
  message,
  action,
  className,
  size = 'md'
}: EmptyStateProps) {
  const preset = PRESETS[type];
  const finalIcon = icon ?? preset.icon;
  const finalTitle = title ?? preset.title;
  const finalMessage = message ?? preset.message;
  const finalAction: EmptyStateAction | undefined = action
    ? { tone: preset.actionTone, ...action }
    : preset.actionLabel
      ? { label: preset.actionLabel, tone: preset.actionTone }
      : undefined;

  const padding = size === 'sm' ? 'px-3 py-4' : 'px-[18px] py-6';
  const iconSize = size === 'sm' ? 'text-[28px]' : 'text-[36px]';
  const titleSize = size === 'sm' ? 'text-[13px]' : 'text-[14px]';
  const messageSize = size === 'sm' ? 'text-[11px]' : 'text-[11.5px]';

  const actionToneClass =
    finalAction?.tone === 'gold'
      ? 'cursor-pointer font-semibold text-gold-600 hover:text-gold-700'
      : 'cursor-pointer text-brand-600 hover:text-brand-700';

  return (
    <div
      className={[
        'rounded-xl border border-ink-50 bg-white text-center',
        padding,
        className
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div className={`${iconSize} opacity-35 leading-none`} aria-hidden>
        {finalIcon}
      </div>
      <div className={`font-serif mt-2 font-bold text-ink-900 ${titleSize}`}>{finalTitle}</div>
      {finalMessage || finalAction ? (
        <div className={`mt-1 text-ink-400 ${messageSize}`}>
          {finalMessage}
          {finalAction ? (
            <>
              {finalMessage ? ' · ' : null}
              <button
                type="button"
                onClick={finalAction.onClick}
                className={`border-0 bg-transparent p-0 ${actionToneClass}`}
              >
                {finalAction.label}
              </button>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default EmptyState;
