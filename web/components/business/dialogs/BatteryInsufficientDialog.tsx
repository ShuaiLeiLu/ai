'use client';

import { Modal } from 'antd';

export interface BatteryInsufficientDialogProps {
  open: boolean;
  /** 本次操作所需算力 */
  required: number;
  /** 当前余额 */
  current: number;
  onClose: () => void;
  onTopup: () => void;
  onUpgradeVip: () => void;
  /** 自定义文案 */
  topupText?: string;
  vipText?: string;
  cancelText?: string;
}

export function BatteryInsufficientDialog({
  open,
  required,
  current,
  onClose,
  onTopup,
  onUpgradeVip,
  topupText = '充值',
  vipText = '开通 VIP',
  cancelText = '取消'
}: BatteryInsufficientDialogProps) {
  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      closable={false}
      centered
      maskStyle={{ backgroundColor: 'rgba(23,20,16,0.4)' }}
      width={380}
      styles={{ body: { padding: 0 } }}
      destroyOnHidden
    >
      <div className="bg-white">
        <div className="px-6 py-5 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-gold-50 text-[28px]">
            ⚡
          </div>
          <div className="font-serif mt-3 text-[17px] font-bold text-ink-900">算力不足</div>
          <div className="mt-1.5 text-[12.5px] text-ink-500">
            本次操作需要{' '}
            <b className="text-gold-600 tnum">{required.toLocaleString('zh-CN')} 算力</b>
            ，你当前余额仅{' '}
            <b className="text-up-600 tnum">{current.toLocaleString('zh-CN')} 算力</b>
          </div>

          <div className="mt-3.5 rounded-lg bg-ink-25 p-3 text-left">
            <div className="text-[11px] text-ink-500">三种方式获取算力：</div>
            <div className="mt-1.5 space-y-1 text-[12px] leading-[1.85] text-ink-700">
              <div>
                <span>🎁</span> <b>每日签到</b>{' '}
                <span className="text-ink-500">· 免费 + 50 算力</span>
              </div>
              <div>
                <span>💰</span> <b>充值算力包</b>{' '}
                <span className="text-ink-500">· ¥9.9 起</span>
              </div>
              <div>
                <span>👑</span> <b>升级 VIP</b>{' '}
                <span className="text-ink-500">· 每月赠 4,000 算力</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-2 px-6 pb-4.5 pb-[18px] pt-0">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-ink-50 bg-white px-2 py-2 text-[13px] text-ink-700 transition hover:bg-ink-25"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onTopup}
            className="flex-1 rounded-lg bg-gold-500 px-2 py-2 text-[13px] font-semibold text-white transition hover:bg-gold-600"
          >
            {topupText}
          </button>
          <button
            type="button"
            onClick={onUpgradeVip}
            className="flex-1 rounded-lg bg-brand-600 px-2 py-2 text-[13px] font-semibold text-white transition hover:bg-brand-700"
          >
            {vipText}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default BatteryInsufficientDialog;
