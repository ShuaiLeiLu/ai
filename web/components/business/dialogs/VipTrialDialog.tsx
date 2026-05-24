'use client';

import { Modal } from 'antd';
import type { ReactNode } from 'react';

export interface VipTrialPerk {
  icon: ReactNode;
  title: string;
  description?: string;
}

const DEFAULT_PERKS: VipTrialPerk[] = [
  { icon: '⚡', title: '每日签到送 50 算力', description: '3 天累计 150 算力，可发起 7-15 次对话' },
  { icon: '🤖', title: '创建 5 名研究员', description: '从模板或自定义打造你的专属投研团队' },
  { icon: '📄', title: '专属文档完整查看', description: '解锁全部 VIP 研报与题材掘金深度分析' },
  { icon: '📊', title: '模拟交易实时执行', description: '非 VIP 数据隐藏 1 分钟内操作，VIP 实时' },
  { icon: '👑', title: '大师模式接入权限', description: '使用更强 AI 模型进行深度推理' }
];

export interface VipTrialDialogProps {
  open: boolean;
  /** 自定义特权列表；不传则使用默认 5 项 */
  perks?: VipTrialPerk[];
  acceptText?: string;
  purchaseText?: string;
  laterText?: string;
  onAccept: () => void;
  onPurchase: () => void;
  onLater: () => void;
  onClose?: () => void;
}

export function VipTrialDialog({
  open,
  perks = DEFAULT_PERKS,
  acceptText = '立即体验（免费 3 天）',
  purchaseText = '立即购买享 88 折优惠 →',
  laterText = '稍后再说',
  onAccept,
  onPurchase,
  onLater,
  onClose
}: VipTrialDialogProps) {
  return (
    <Modal
      open={open}
      onCancel={onClose ?? onLater}
      footer={null}
      closable={false}
      centered
      maskStyle={{ backgroundColor: 'rgba(23,20,16,0.5)' }}
      width={520}
      styles={{ body: { padding: 0 } }}
      destroyOnHidden
    >
      <div
        className="relative"
        style={{
          background:
            'linear-gradient(180deg, #1d4a34 0%, #143929 38%, #ffffff 38%, #ffffff 100%)'
        }}
      >
        {/* 顶部 */}
        <div className="relative px-7 pb-8 pt-6 text-white">
          <div
            className="pointer-events-none absolute -right-[30px] -top-[30px] h-[180px] w-[180px] rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(200,154,58,.30), transparent 70%)'
            }}
          />
          <div className="relative flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-[14px] bg-gradient-to-br from-gold-500 to-gold-600 text-[22px]">
              🎁
            </div>
            <div>
              <div className="text-[11px] tracking-[2px] text-gold-300">限 时 福 利</div>
              <div className="font-serif text-[22px] font-bold text-white">3 天 VIP 体验卡</div>
            </div>
            {onClose ? (
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭"
                className="ml-auto cursor-pointer border-0 bg-transparent text-[22px] text-white/40 transition hover:text-white/70"
              >
                ×
              </button>
            ) : null}
          </div>
          <div className="relative mt-3.5 text-[12.5px] leading-[1.7] text-white/75">
            解锁全部 AI 研究员能力，体验 72 小时机构级投研工具，无需任何承诺。
          </div>
        </div>

        {/* 特权列表 */}
        <div className="px-7 pb-2 pt-6">
          <div className="mb-3 text-[11.5px] tracking-[2px] text-ink-400">体 验 卡 包 含</div>
          <div className="flex flex-col gap-3">
            {perks.map((perk, idx) => (
              <div key={idx} className="flex items-start gap-3">
                <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-brand-50 text-[15px]">
                  {perk.icon}
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-ink-900">{perk.title}</div>
                  {perk.description ? (
                    <div className="text-[11px] text-ink-400">{perk.description}</div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 按钮 */}
        <div className="px-7 pb-6 pt-4">
          <button
            type="button"
            onClick={onAccept}
            className="w-full rounded-lg bg-brand-600 px-3 py-3 text-[14px] font-semibold text-white transition hover:bg-brand-700"
          >
            {acceptText}
          </button>
          <button
            type="button"
            onClick={onPurchase}
            className="mt-2 w-full rounded-lg bg-gradient-to-br from-gold-500 to-gold-600 px-3 py-2.5 text-[13px] font-semibold text-white shadow-gold transition hover:from-gold-600 hover:to-gold-700"
          >
            {purchaseText}
          </button>
          <button
            type="button"
            onClick={onLater}
            className="mx-auto mt-3 block cursor-pointer border-0 bg-transparent text-[11.5px] text-ink-400 transition hover:text-ink-600"
          >
            {laterText}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default VipTrialDialog;
