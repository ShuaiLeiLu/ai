/**
 * 市场情绪 Hero —— Overview / 首页的「重点位置」横幅
 *
 * 设计目标（对照设计稿）：
 *   - 宣纸暖底 + 金色装饰光晕
 *   - 左侧情绪叙事（思源宋体大字 + 关键数据点）
 *   - 右侧 3-4 个指数横排，含点位 / 涨跌额 / 涨跌幅 / 迷你 spark
 *
 * 数据：后端 MarketIndicator 仅暴露 value/direction/reference，
 *   change 与 changePercent 从 reference 字符串里解析（容错处理）。
 */
'use client';

import { IndexHero, type IndexQuote } from '@/components/ui/index-hero';
import { useMarketIndicatorsQuery } from '@/features/preopen/hooks';
import type { MarketIndicator } from '@/types/preopen';

/** 识别哪些指标是指数（按 label 关键字） */
const INDEX_KEYWORDS = ['上证', '深证', '创业板', '科创', '恒生', '沪深300', '北证', '中证'];

function isIndex(label: string) {
  return INDEX_KEYWORDS.some((k) => label.includes(k));
}

/**
 * 从 reference 文本里解析涨跌幅，如：
 *   "较昨日 +0.74%"  → +0.74
 *   "下跌 -0.39%"    → -0.39
 *   "+24.32 (+0.74%)" → changePercent=+0.74, change=+24.32
 */
function parseRef(ref: string, direction: MarketIndicator['direction']): { change: number; pct: number } {
  if (!ref) return { change: 0, pct: 0 };
  const pctMatch = ref.match(/([+-]?\d+(?:\.\d+)?)\s*%/);
  const numMatch = ref.match(/([+-]?\d+(?:\.\d+)?)(?!\s*%)/);
  let pct = pctMatch ? Number(pctMatch[1]) : 0;
  let change = numMatch && Number(numMatch[1]) !== pct ? Number(numMatch[1]) : 0;
  // direction 兜底
  if (!pct && direction === 'up') pct = 0.5;
  if (!pct && direction === 'down') pct = -0.5;
  return { change, pct };
}

/** 根据 direction 生成 ~ 11 点的伪 spark 序列（视觉用，不参与真实分析） */
function fakeSpark(direction: MarketIndicator['direction'], seed: number): number[] {
  const base = 50;
  const slope = direction === 'up' ? 1.2 : direction === 'down' ? -1.2 : 0;
  const arr: number[] = [];
  for (let i = 0; i < 11; i++) {
    // 用 seed 让不同指数曲线不重叠
    const noise = Math.sin((i + seed) * 1.3) * 2.5;
    arr.push(base + slope * i + noise);
  }
  return arr;
}

export function MarketHero() {
  const { data } = useMarketIndicatorsQuery();
  const indicators = data ?? [];

  // 提取指数（最多 4 条）
  const indices = indicators.filter((i) => isIndex(i.label)).slice(0, 4);
  // 情绪数据点（成交额、北向、涨停、跌停）
  const sentiment = {
    turnover: indicators.find((i) => i.label.includes('成交')),
    northbound: indicators.find((i) => i.label.includes('北向') || i.label.includes('陆股通')),
    limitUp: indicators.find((i) => i.label.includes('涨停') && !i.label.includes('跌停')),
    limitDown: indicators.find((i) => i.label.includes('跌停')),
  };

  // 推断市场情绪文案
  const upCount = sentiment.limitUp?.value ?? 0;
  const downCount = sentiment.limitDown?.value ?? 0;
  const moodValue = upCount > 50
    ? '谨慎乐观'
    : upCount > 20
      ? '震荡偏多'
      : downCount > 30
        ? '风险渐升'
        : '今日速览';

  const quotes: IndexQuote[] = indices.length
    ? indices.map((i, idx) => {
        const { change, pct } = parseRef(i.reference, i.direction);
        return {
          code: `${i.indicator || i.label}-${idx}`,
          name: i.label,
          value: i.value,
          change,
          changePercent: pct,
          spark: fakeSpark(i.direction, idx),
        };
      })
    : [
        // 占位：无数据时仍展示骨架
        { code: 'sh', name: '上证指数', value: 0, change: 0, changePercent: 0 },
        { code: 'sz', name: '深证成指', value: 0, change: 0, changePercent: 0 },
        { code: 'cyb', name: '创业板指', value: 0, change: 0, changePercent: 0 },
        { code: 'hstech', name: '恒生科技', value: 0, change: 0, changePercent: 0 },
      ];

  const moodSub = (
    <>
      {sentiment.turnover && (
        <>
          两市成交{' '}
          <b className="font-semibold text-ink-800">
            {sentiment.turnover.value.toLocaleString('zh-CN')}
            {sentiment.turnover.unit}
          </b>
          {' · '}
        </>
      )}
      {sentiment.northbound && (
        <>
          北向{' '}
          <b
            className={
              sentiment.northbound.direction === 'up'
                ? 'font-semibold text-up-600'
                : sentiment.northbound.direction === 'down'
                  ? 'font-semibold text-down-600'
                  : 'font-semibold text-ink-800'
            }
          >
            {sentiment.northbound.value > 0 ? '+' : ''}
            {sentiment.northbound.value}
            {sentiment.northbound.unit}
          </b>
          {' · '}
        </>
      )}
      {sentiment.limitUp && (
        <>
          涨停 <b className="font-semibold text-up-600">{sentiment.limitUp.value}</b> 家
        </>
      )}
      {sentiment.limitDown && (
        <>
          {' · '}跌停 <b className="font-semibold text-down-600">{sentiment.limitDown.value}</b> 家
        </>
      )}
    </>
  );

  return (
    <IndexHero
      mood={{
        label: '市 场 情 绪',
        value: moodValue,
        sub: moodSub,
      }}
      quotes={quotes}
    />
  );
}
