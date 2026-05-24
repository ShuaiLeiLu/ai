'use client';

import { Modal } from 'antd';
import type { ReactNode } from 'react';

export interface OrderConfirmPayload {
  side: 'buy' | 'sell';
  name: string;
  symbol: string;
  sector?: string;
  /** 委托价格 */
  price: number;
  /** 委托数量（股） */
  quantity: number;
  /** 当前现价（用于对照） */
  marketPrice?: number;
  /** 触发条件描述（例如：市价回落至 ¥195.80） */
  trigger?: string;
  /** 手续费率：例如 0.00025 表示万 2.5 */
  feeRate?: number;
  /** 直接指定手续费金额；如果提供则忽略 feeRate */
  fee?: number;
  /** 委托研究员名称 */
  researcher?: string;
  /** 账户当前可用余额 */
  availableBalance: number;
}

export interface OrderConfirmDialogProps {
  open: boolean;
  order: OrderConfirmPayload;
  confirmText?: string;
  cancelText?: string;
  modifyText?: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onModify?: () => void;
}

function formatMoney(value: number): string {
  if (!Number.isFinite(value)) return '--';
  return `¥ ${value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}

function formatNum(value: number): string {
  if (!Number.isFinite(value)) return '--';
  return value.toLocaleString('zh-CN');
}

interface RowProps {
  label: ReactNode;
  value: ReactNode;
  /** 顶部分隔线样式 */
  divider?: 'none' | 'dashed' | 'solid';
}

function Row({ label, value, divider = 'dashed' }: RowProps) {
  const borderClass =
    divider === 'solid'
      ? 'border-t-2 border-ink-50'
      : divider === 'dashed'
        ? 'border-t border-dashed border-ink-50'
        : '';
  return (
    <div className={`flex items-center justify-between py-2 ${borderClass}`}>
      <span className="text-[13px] text-ink-500">{label}</span>
      <span className="text-[13px] text-ink-800">{value}</span>
    </div>
  );
}

export function OrderConfirmDialog({
  open,
  order,
  confirmText,
  cancelText = '取消',
  modifyText = '修改订单',
  loading,
  onConfirm,
  onCancel,
  onModify
}: OrderConfirmDialogProps) {
  const isBuy = order.side === 'buy';
  const sideLabel = isBuy ? '买入' : '卖出';
  const sideBadgeClass = isBuy
    ? 'bg-up-100 text-up-700'
    : 'bg-down-100 text-down-700';
  const headerBgClass = isBuy
    ? 'bg-gradient-to-r from-up-50 to-transparent border-b border-up-100'
    : 'bg-gradient-to-r from-down-50 to-transparent border-b border-down-100';
  const headerTextClass = isBuy ? 'text-up-700' : 'text-down-700';

  const grossAmount = order.price * order.quantity;
  const fee =
    typeof order.fee === 'number'
      ? order.fee
      : typeof order.feeRate === 'number'
        ? grossAmount * order.feeRate
        : 0;
  const totalCost = isBuy ? grossAmount + fee : 0;
  const proceeds = !isBuy ? grossAmount - fee : 0;
  const afterBalance = isBuy
    ? order.availableBalance - totalCost
    : order.availableBalance + proceeds;

  const feeLabel =
    typeof order.feeRate === 'number'
      ? `手续费（${(order.feeRate * 10000).toFixed(1).replace(/\.0$/, '')} 万）`
      : '手续费';

  const finalConfirmText = confirmText ?? (isBuy ? '✓ 确认下单' : '✓ 确认卖出');

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      footer={null}
      closable={false}
      centered
      maskStyle={{ backgroundColor: 'rgba(23,20,16,0.4)' }}
      width={460}
      styles={{ body: { padding: 0 } }}
      destroyOnHidden
    >
      <div className="bg-white">
        <div className={`flex items-center gap-2.5 px-5 py-4 ${headerBgClass}`}>
          <span
            className={`inline-flex items-center rounded px-2.5 py-1 text-[12px] font-semibold ${sideBadgeClass}`}
          >
            {sideLabel}
          </span>
          <div className="font-serif text-[18px] font-bold leading-tight">
            <span className={headerTextClass}>{order.name}</span>{' '}
            <span className="text-[12px] font-normal text-ink-400">
              {order.symbol}
              {order.sector ? ` · ${order.sector}` : ''}
            </span>
          </div>
        </div>

        <div className="px-5 pt-4">
          <div>
            <Row
              divider="none"
              label="委托价格"
              value={
                <span className="tnum">
                  <b>{formatMoney(order.price)}</b>
                  {typeof order.marketPrice === 'number' ? (
                    <span className="ml-1 text-[11px] text-ink-400">
                      / 现价 {order.marketPrice.toFixed(2)}
                    </span>
                  ) : null}
                </span>
              }
            />
            <Row
              label="委托数量"
              value={
                <span className="tnum">
                  <b>{formatNum(order.quantity)}</b> 股
                </span>
              }
            />
            {order.trigger ? <Row label="触发条件" value={order.trigger} /> : null}
            <Row
              label="预计成交额"
              value={
                <span className="tnum">
                  <b>{formatMoney(grossAmount)}</b>
                </span>
              }
            />
            <Row label={feeLabel} value={<span className="tnum">{formatMoney(fee)}</span>} />
            {order.researcher ? <Row label="委托研究员" value={order.researcher} /> : null}
            <Row
              label="账户可用余额"
              value={<span className="tnum">{formatMoney(order.availableBalance)}</span>}
            />
            <div className="flex items-center justify-between border-t-2 border-ink-50 py-2.5">
              <span className="text-[13px] font-semibold text-ink-900">下单后可用</span>
              <span className="font-serif tnum text-[16px] font-bold text-brand-700">
                {formatMoney(afterBalance)}
              </span>
            </div>
          </div>

          <div className="mt-3 rounded-r-lg border-l-[3px] border-gold-500 bg-gold-50 px-3 py-2.5 text-[12px] text-gold-700">
            ⚠️ 本订单为模拟交易，<b>不会实际成交</b>。仅用于策略验证。
          </div>
        </div>

        <div className="flex gap-2.5 px-5 pb-5 pt-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="flex-1 rounded-lg border border-ink-50 bg-white px-2 py-2 text-[13px] text-ink-700 transition hover:bg-ink-25 disabled:opacity-50"
          >
            {cancelText}
          </button>
          {onModify ? (
            <button
              type="button"
              onClick={onModify}
              disabled={loading}
              className="flex-1 rounded-lg border border-ink-50 bg-white px-2 py-2 text-[13px] text-ink-700 transition hover:bg-ink-25 disabled:opacity-50"
            >
              {modifyText}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex-[2] rounded-lg bg-brand-600 px-2 py-2 text-[13px] font-semibold text-white transition hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? '提交中…' : finalConfirmText}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default OrderConfirmDialog;
