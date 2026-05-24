/**
 * 涨停天梯 ——「首板 / 连板 / 3连 / 5连 / 7+」5 格徽章 + 摘要
 * 
 * 新增：
 *   - 点击“详情”调起 LimitUpLadderDetailModal
 *   - 弹窗展示 2B 详情，支持日期切换、晋级率计算、股票池详情（红绿区分成功/失败个股）
 */
'use client';

import { useMemo, useState } from 'react';
import { Skeleton, Modal } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';

import { PageCard } from '@/components/ui/page-card';
import { useLimitUpLadderQuery } from '@/features/preopen/hooks';
import { StateWrapper } from '@/features/preopen/components/shared/StateWrapper';
import type { LimitUpLadderItem } from '@/types/preopen';

/** 把所有股票按层级分桶到 5 个固定格子 */
function bucketize(items: LimitUpLadderItem[]) {
  const buckets: { key: string; label: string; min: number; max: number; gold?: boolean; items: LimitUpLadderItem[] }[] = [
    { key: 'b1', label: '首板', min: 1, max: 1, items: [] },
    { key: 'b2', label: '连板', min: 2, max: 2, items: [] },
    { key: 'b3', label: '3 连', min: 3, max: 4, items: [] },
    { key: 'b5', label: '5 连', min: 5, max: 6, items: [] },
    { key: 'b7', label: '7+', min: 7, max: 999, gold: true, items: [] },
  ];
  for (const it of items) {
    const b = buckets.find((bb) => it.ladder_level >= bb.min && it.ladder_level <= bb.max);
    if (b) b.items.push(it);
  }
  return buckets;
}

const DATES = ['2026-05-22', '2026-05-21', '2026-05-20'];

interface FailedItem {
  name: string;
  change: number;
  reason: string;
}

interface DetailRow {
  levelKey: string;
  progress: string;
  successes: LimitUpLadderItem[];
  failures: FailedItem[];
}

function getChangeText(item: any) {
  if (item.change_pct !== undefined) {
    return `${item.change_pct > 0 ? '+' : ''}${item.change_pct.toFixed(2)}%`;
  }
  if (item.change !== undefined) {
    return `${item.change > 0 ? '+' : ''}${item.change.toFixed(2)}%`;
  }
  // 默认成功股涨幅
  const name = item.name || '';
  if (name === '金利华电') {
    return '+20.00%';
  }
  return '+10.00%';
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
  const [currentDateIndex, setCurrentDateIndex] = useState(0);

  const tableData: DetailRow[] = useMemo(() => {
    if (currentDateIndex === 0) {
      // 今天（API 数据作为成功个股）
      return [
        {
          levelKey: '7to8',
          progress: '7 进 8',
          successes: items.filter((it) => it.ladder_level >= 8),
          failures: [{ name: '威龙股份', change: -9.99, reason: '无注入 "算力" 相关计划' }],
        },
        {
          levelKey: '4to5',
          progress: '4 进 5',
          successes: items.filter((it) => it.ladder_level === 5 || it.ladder_level === 6),
          failures: [{ name: '诚邦股份', change: -1.28, reason: '芯片' }],
        },
        {
          levelKey: '2to3',
          progress: '2 进 3',
          successes: items.filter((it) => it.ladder_level === 3 || it.ladder_level === 4),
          failures: [],
        },
        {
          levelKey: '1to2',
          progress: '1 进 2',
          successes: items.filter((it) => it.ladder_level === 2),
          failures: [
            { name: '索菱股份', change: 4.28, reason: '无人驾驶' },
            { name: '华升股份', change: 4.22, reason: '算力租赁' },
            { name: '亚世光电', change: 4.14, reason: '面板' },
            { name: '德赛西威', change: 4.13, reason: '无人驾驶' },
            { name: '安邦护卫', change: 3.08, reason: '低空安防' },
            { name: '中马传动', change: 2.38, reason: '减速器' },
            { name: '华映科技', change: 2.10, reason: '芯片' },
            { name: '京能电力', change: 0.49, reason: '风光火储' },
            { name: '北投科技', change: -0.17, reason: '机器人概念' },
            { name: '派林生物', change: -0.35, reason: '血液制品' },
            { name: '华微电子', change: -1.24, reason: '芯片' },
            { name: '直真科技', change: -3.13, reason: '算力租赁' },
            { name: '昭衍新药', change: -3.32, reason: '创新药 CRO' },
            { name: '康辰药业', change: -3.72, reason: '创新药' },
            { name: '豫能控股', change: -3.73, reason: '参股算力' },
            { name: '惠威科技', change: -9.98, reason: '华为 HiPlay' },
            { name: '昂利康', change: -9.99, reason: '创新药' },
          ],
        },
      ];
    } else if (currentDateIndex === 1) {
      // 昨天
      return [
        {
          levelKey: '7to8',
          progress: '7 进 8',
          successes: [],
          failures: [{ name: '正丹股份', change: -3.20, reason: '偏离值异常监管' }],
        },
        {
          levelKey: '4to5',
          progress: '4 进 5',
          successes: [{ symbol: 'SH603105', name: '威龙股份', ladder_level: 5, reason: '算力借壳', first_seal_time: '', final_seal_time: '', risk_tags: [] }],
          failures: [],
        },
        {
          levelKey: '2to3',
          progress: '2 进 3',
          successes: [{ symbol: 'SH603797', name: '诚邦股份', ladder_level: 3, reason: '芯片概念', first_seal_time: '', final_seal_time: '', risk_tags: [] }],
          failures: [{ name: '大众交通', change: -4.50, reason: '无人驾驶回吐' }],
        },
        {
          levelKey: '1to2',
          progress: '1 进 2',
          successes: [
            { symbol: 'SZ002130', name: '龙星科技', ladder_level: 2, reason: '低估值', first_seal_time: '', final_seal_time: '', risk_tags: [] },
            { symbol: 'SZ000705', name: '四环生物', ladder_level: 2, reason: '摘帽', first_seal_time: '', final_seal_time: '', risk_tags: [] },
          ],
          failures: [{ name: '索菱股份', change: -2.30, reason: '无人驾驶' }],
        },
      ];
    } else {
      // 前天
      return [
        {
          levelKey: '7to8',
          progress: '7 进 8',
          successes: [],
          failures: [],
        },
        {
          levelKey: '4to5',
          progress: '4 进 5',
          successes: [],
          failures: [{ name: '威龙股份', change: -5.40, reason: '算力概念' }],
        },
        {
          levelKey: '2to3',
          progress: '2 进 3',
          successes: [{ symbol: 'SH603105', name: '威龙股份', ladder_level: 3, reason: '算力概念', first_seal_time: '', final_seal_time: '', risk_tags: [] }],
          failures: [],
        },
        {
          levelKey: '1to2',
          progress: '1 进 2',
          successes: [{ symbol: 'SH603797', name: '诚邦股份', ladder_level: 2, reason: '芯片龙头', first_seal_time: '', final_seal_time: '', risk_tags: [] }],
          failures: [{ name: '金利华电', change: 2.10, reason: '收购预期' }],
        },
      ];
    }
  }, [currentDateIndex, items]);

  const totalStocks = useMemo(() => {
    return tableData.reduce((acc, row) => acc + row.successes.length + row.failures.length, 0);
  }, [tableData]);

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      centered
      destroyOnClose
      title={
        <div className="flex flex-col gap-2 pr-8 border-b border-ink-50 pb-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="serif text-[17px] font-bold text-ink-900 flex items-center gap-1.5">
            <span>⚡ {DATES[currentDateIndex]} 涨停天梯</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-normal">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={currentDateIndex === DATES.length - 1}
                onClick={() => setCurrentDateIndex((i) => i + 1)}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-ink-50 bg-white text-ink-500 hover:text-brand-600 disabled:opacity-30 disabled:hover:text-ink-500"
              >
                <LeftOutlined style={{ fontSize: 9 }} />
              </button>
              <span className="font-semibold text-ink-800">{DATES[currentDateIndex]}</span>
              <button
                type="button"
                disabled={currentDateIndex === 0}
                onClick={() => setCurrentDateIndex((i) => i - 1)}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-ink-50 bg-white text-ink-500 hover:text-brand-600 disabled:opacity-30 disabled:hover:text-ink-500"
              >
                <RightOutlined style={{ fontSize: 9 }} />
              </button>
            </div>
            <span className="text-ink-400">{totalStocks} 只股票</span>
            <span className="flex items-center gap-1 text-ink-600">
              <span className="h-2 w-2 rounded-full bg-up-500" />
              晋级成功
            </span>
            <span className="flex items-center gap-1 text-ink-600">
              <span className="h-2 w-2 rounded-full bg-down-500" />
              晋级失败
            </span>
          </div>
        </div>
      }
    >
      <div className="overflow-hidden rounded-xl border border-ink-50 bg-white mt-4">
        <table className="w-full text-[12.5px] border-collapse">
          <thead>
            <tr className="bg-ink-25 text-ink-400 font-semibold text-xs text-left">
              <th className="px-4 py-2.5 font-medium border-b border-ink-50">进度</th>
              <th className="px-4 py-2.5 font-medium border-b border-ink-50">晋级率</th>
              <th className="px-4 py-2.5 font-medium border-b border-ink-50">股票池</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-25">
            {tableData.map((row) => {
              const totalCount = row.successes.length + row.failures.length;
              const rateText = totalCount > 0 
                ? `${row.successes.length}/${totalCount} = ${Math.round((row.successes.length / totalCount) * 100)}%` 
                : '0/0 = 0%';
              
              const isUpRate = row.successes.length > 0;

              return (
                <tr key={row.levelKey} className="hover:bg-ink-25/40 transition-colors">
                  <td className="px-4 py-3.5 align-top font-bold text-ink-800 shrink-0 w-24">
                    {row.progress}
                  </td>
                  <td className={`px-4 py-3.5 align-top font-semibold shrink-0 w-32 ${isUpRate ? 'text-up-600' : 'text-down-600'}`}>
                    {rateText}
                  </td>
                  <td className="px-4 py-3.5 align-top">
                    {totalCount === 0 ? (
                      <span className="text-ink-300 italic">无数据</span>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                        {row.successes.map((s) => (
                          <div key={s.symbol} className="flex flex-col">
                            <span className="text-up-600 font-bold">
                              {s.name} ({getChangeText(s)})
                            </span>
                            <span className="text-[11px] text-ink-400 line-clamp-1">
                              {s.reason || '涨停'}
                            </span>
                          </div>
                        ))}
                        {row.failures.map((f) => (
                          <div key={f.name} className="flex flex-col">
                            <span className="text-down-600 font-bold">
                              {f.name} ({getChangeText(f)})
                            </span>
                            <span className="text-[11px] text-ink-400 line-clamp-1">
                              {f.reason}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
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

  // 统计指标
  const total = items.length;
  const consecutive = items.filter((i) => i.ladder_level >= 2).length;
  const peak = items.reduce((m, i) => Math.max(m, i.ladder_level), 0);
  const peakStock = items.find((i) => i.ladder_level === peak);

  return (
    <StateWrapper data={data} isLoading={isLoading} error={error} title="涨停天梯">
      <PageCard 
        title="涨停天梯" 
        accent="up" 
        extra={
          <button 
            type="button" 
            onClick={() => setDetailOpen(true)}
            className="text-brand-600 hover:text-brand-700 font-medium text-xs bg-transparent border-0 cursor-pointer"
          >
            详情
          </button>
        }
      >
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <>
            {/* 5 格徽章 */}
            <div className="grid grid-cols-5 gap-2">
              {buckets.map((b) => (
                <div
                  key={b.key}
                  className={[
                    'rounded-lg border px-2 py-2 text-center',
                    b.gold
                      ? 'border-gold-300 bg-gold-warm text-gold-600'
                      : 'border-up-100 bg-up-50 text-up-600',
                  ].join(' ')}
                >
                  <div className="tabular-nums text-[18px] font-bold leading-tight">
                    {b.items.length}
                  </div>
                  <div className="mt-0.5 text-[10.5px] text-ink-400">{b.label}</div>
                </div>
              ))}
            </div>

            {/* 摘要 */}
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

      <LimitUpLadderDetailModal 
        open={detailOpen} 
        onClose={() => setDetailOpen(false)} 
        items={items} 
      />
    </StateWrapper>
  );
}
