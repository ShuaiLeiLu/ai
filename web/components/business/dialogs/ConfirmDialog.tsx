'use client';

import { Modal } from 'antd';
import type { ReactNode } from 'react';

export type ConfirmDialogLevel = 'info' | 'warning' | 'danger';

export interface ConfirmDialogStep {
  /**
   * 主标题，可选。当传入 steps 时，每一步会作为列表项渲染在主 message 下方。
   */
  label: string;
  description?: string;
}

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: ReactNode;
  /**
   * 警告级别：
   *  - info     绿色（品牌色）
   *  - warning  金色
   *  - danger   红色（朱砂）
   */
  level?: ConfirmDialogLevel;
  /**
   * 多步骤显示。每一项会渲染为带 emoji 项目符号的提示行。
   */
  steps?: ConfirmDialogStep[] | string[];
  /**
   * 中间区域的大 emoji 图标。默认按 level 推断。
   */
  icon?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const LEVEL_STYLE: Record<
  ConfirmDialogLevel,
  {
    iconBg: string;
    boxBg: string;
    boxText: string;
    confirmBtn: string;
    defaultIcon: string;
  }
> = {
  info: {
    iconBg: 'bg-brand-50',
    boxBg: 'bg-brand-50',
    boxText: 'text-brand-700',
    confirmBtn: 'bg-brand-600 hover:bg-brand-700 text-white',
    defaultIcon: '💡'
  },
  warning: {
    iconBg: 'bg-gold-50',
    boxBg: 'bg-gold-50',
    boxText: 'text-gold-700',
    confirmBtn: 'bg-gold-500 hover:bg-gold-600 text-white',
    defaultIcon: '⚠️'
  },
  danger: {
    iconBg: 'bg-up-50',
    boxBg: 'bg-up-50',
    boxText: 'text-up-700',
    confirmBtn: 'bg-up-500 hover:bg-up-600 text-white',
    defaultIcon: '⚠️'
  }
};

function normalizeSteps(
  steps: ConfirmDialogProps['steps']
): ConfirmDialogStep[] | undefined {
  if (!steps || steps.length === 0) return undefined;
  return steps.map((s) => (typeof s === 'string' ? { label: s } : s));
}

export function ConfirmDialog({
  open,
  title,
  message,
  level = 'info',
  steps,
  icon,
  confirmText = '确认',
  cancelText = '取消',
  loading,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  const style = LEVEL_STYLE[level];
  const normalized = normalizeSteps(steps);

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      footer={null}
      closable={false}
      centered
      maskStyle={{ backgroundColor: 'rgba(23,20,16,0.6)' }}
      width={420}
      styles={{ body: { padding: 0 } }}
      destroyOnHidden
    >
      <div className="bg-white">
        <div className="px-6 py-5 text-center">
          <div
            className={`mx-auto grid h-14 w-14 place-items-center rounded-full text-[28px] ${style.iconBg}`}
          >
            {icon ?? style.defaultIcon}
          </div>
          <div className="font-serif mt-3 text-[18px] font-bold text-ink-900">{title}</div>
          {message ? (
            <div className="mt-2 text-[12.5px] leading-[1.7] text-ink-500">{message}</div>
          ) : null}

          {normalized ? (
            <div
              className={`mt-3 rounded-lg p-3 text-left ${style.boxBg}`}
            >
              <ul className="ml-4 list-disc space-y-1 text-[11.5px] leading-[1.7] text-ink-700">
                {normalized.map((step, idx) => (
                  <li key={idx}>
                    <span className={`font-semibold ${style.boxText}`}>{step.label}</span>
                    {step.description ? (
                      <span className="text-ink-500"> · {step.description}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="flex gap-2.5 px-6 pb-5 pt-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded-lg border border-ink-50 bg-white px-2 py-2 text-[13px] font-medium text-ink-700 transition hover:bg-ink-25 disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 rounded-lg px-2 py-2 text-[13px] font-semibold transition disabled:opacity-50 ${style.confirmBtn}`}
          >
            {loading ? '处理中…' : confirmText}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
