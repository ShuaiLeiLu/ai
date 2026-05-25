/**
 * 涨停天梯 —— 「首板 / 连板 / 3连 / 5连 / 7+」5 格徽章 + 实时明细。
 */
'use client';

import { useMemo, useState } from 'react';
import { Modal, Skeleton } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { useLimitUpLadderQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { LimitUpLadderItem } from '@/types/preopen';

type Bucket = {
  key: string;
  label: string;
  min: number;
  max: number;
  gold?: boolean;
  items: LimitUpLadderItem[];
};

function bucketize(items: LimitUpLadderItem[]): Bucket[] {
  const buckets: Bucket[] = [
    { key: 'b1', label: '首板', min: 1, max: 1, items: [] },
    { key: 'b2', label: '连板', min: 2, max: 2, items: [] },
    { key: 'b3', label: '3 连', min: 3, max: 4, items: [] },
    { key: 'b5', label: '5 连', min: 5, max: 6, items: [] },
    { key: 'b7', label: '7+', min: 7, max: 999, gold: true, items: [] },
  ];

  for (const item of items) {
    const bucket = buckets.find((b) => item.ladder_level >= b.min && item.ladder_level <= b.max);
    if (bucket) bucket.items.push(item);
  }
  return buckets;
}

function getTradeDate(items: LimitUpLadderItem[]) {
  return items.find((item) => item.trade_date)?.trade_date ?? getShanghaiToday();
}

function getShanghaiToday() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const dateParts = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${dateParts.year}-${dateParts.month}-${dateParts.day}`;
}

function formatChangePct(item: LimitUpLadderItem) {
  if (typeof item.change_pct !== 'number') return '涨停';
  const sign = item.change_pct > 0 ? '+' : '';
  return `${sign}${item.change_pct.toFixed(2)}%`;
}

function tierLabel(bucket: Bucket) {
  if (bucket.min === bucket.max) return `${bucket.min} 板`;
  if (bucket.max >= 999) return `${bucket.min} 板以上`;
  return `${bucket.min}-${bucket.max} 板`;
}

function LimitUpLadderDetailModal({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: LimitUpLadderItem[];
}) {
  const buckets = useMemo(() => bucketize(items).filter((bucket) => bucket.items.length > 0), [items]);
  const tradeDate = getTradeDate(items);

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={800} centered destroyOnClose>
      <div className="flex flex-col gap-2 border-b border-ink-50 pb-3 pr-8 sm:flex-row sm:items-center sm:justify-between">
        <div className="serif flex items-center gap-1.5 text-[17px] font-bold text-ink-900">
          <span>{tradeDate} 涨停天梯</span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs font-normal text-ink-500">
          <span>{items.length} 只股票</span>
          <span>实时涨停池</span>
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-ink-50 bg-white">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="bg-ink-25 text-left text-xs font-semibold text-ink-400">
              <th className="border-b border-ink-50 px-4 py-2.5 font-medium">梯队</th>
              <th className="border-b border-ink-50 px-4 py-2.5 font-medium">数量</th>
              <th className="border-b border-ink-50 px-4 py-2.5 font-medium">股票池</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-25">
            {buckets.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-ink-300">
                  暂无涨停天梯数据
                </td>
              </tr>
            ) : (
              buckets.map((bucket) => (
                <tr key={bucket.key} className="transition-colors hover:bg-ink-25/40">
                  <td className="w-24 px-4 py-3.5 align-top font-bold text-ink-800">{tierLabel(bucket)}</td>
                  <td className="w-24 px-4 py-3.5 align-top font-semibold text-up-600">{bucket.items.length} 只</td>
                  <td className="px-4 py-3.5 align-top">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                      {bucket.items.map((item) => (
                        <div key={item.symbol} className="flex flex-col">
                          <span className="font-bold text-up-600">
                            {item.name} ({formatChangePct(item)})
                          </span>
                          <span className="line-clamp-1 text-[11px] text-ink-400">
                            {item.reason || '涨停'}
                            {item.first_seal_time ? ` · 首封 ${item.first_seal_time}` : ''}
                          </span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}

export function LimitUpLadderCard() {
  const [detailOpen, setDetailOpen] = useState(false);
  const { data, isLoading, error } = useLimitUpLadderQuery();
  const items = data ?? [];
  const buckets = useMemo(() => bucketize(items), [items]);

  const total = items.length;
  const consecutive = items.filter((item) => item.ladder_level >= 2).length;
  const peak = items.reduce((max, item) => Math.max(max, item.ladder_level), 0);
  const peakStock = items.find((item) => item.ladder_level === peak);

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="涨停天梯">
      <PageCard
        title="涨停天梯"
        accent="up"
        extra={
          <button
            type="button"
            onClick={() => setDetailOpen(true)}
            className="cursor-pointer border-0 bg-transparent text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            详情
          </button>
        }
      >
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <>
            <div className="grid grid-cols-5 gap-2">
              {buckets.map((bucket) => (
                <div
                  key={bucket.key}
                  className={[
                    'rounded-lg border px-2 py-2 text-center',
                    bucket.gold
                      ? 'border-gold-300 bg-gold-warm text-gold-600'
                      : 'border-up-100 bg-up-50 text-up-600',
                  ].join(' ')}
                >
                  <div className="tabular-nums text-[18px] font-bold leading-tight">{bucket.items.length}</div>
                  <div className="mt-0.5 text-[10.5px] text-ink-400">{bucket.label}</div>
                </div>
              ))}
            </div>

            <div className="mt-3.5 border-t border-dashed border-ink-50 pt-3 text-[12px] leading-[1.7] text-ink-600">
              今日涨停 <b className="text-up-600">{total} 家</b>，连板 <b>{consecutive} 家</b>。
              {peakStock ? (
                <>
                  <br />
                  最高度：<b>{peakStock.name} {peak} 板</b>
                </>
              ) : null}
            </div>
          </>
        )}
      </PageCard>

      <LimitUpLadderDetailModal open={detailOpen} onClose={() => setDetailOpen(false)} items={items} />
    </StateWrapper>
  );
}
