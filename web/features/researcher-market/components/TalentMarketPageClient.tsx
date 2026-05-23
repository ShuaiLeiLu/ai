/**
 * 人才市场页面
 *
 * 属于"极睿实验室"子页面之一，路由：/workstation/talent-market
 * 展示市场上公开的研究员卡片网格，支持搜索、订阅操作。
 *
 * 数据流：
 *  - useMarketResearchers()  市场研究员列表（支持关键词搜索）
 *  - useHireResearcher()    订阅 mutation
 */
'use client';

import { useMemo, useState } from 'react';
import { Input, Segmented, Spin } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

import { SectionHeading } from '@/components/ui/section-heading';
import { useMarketResearchers, useHireResearcher } from '@/features/researcher-market/hooks';
import type { ResearcherMarketCard } from '@/types/researcher';

/** 顶部排序段控 */
type SortKey = 'hot' | 'pnl' | 'sharpe' | 'latest';

/** 流派筛选选项 */
const STYLE_CHIPS = [
  '全部',
  '价值投资',
  '趋势游资',
  '行业景气',
  '技术分析',
  '量化套利',
  '舆情驱动',
  '海外映射',
];

/** 流派 → 头像色（用作 fallback） */
const styleColor: Record<string, string> = {
  价值投资: '#1d4a34',
  趋势游资: '#c0362c',
  行业景气: '#c89a3a',
  技术分析: '#2e6e51',
  量化套利: '#34302a',
  舆情驱动: '#d8453a',
  海外映射: '#48825f',
};

/** 前 3 名 ribbon 样式 */
const RIBBONS: Array<{
  label: string;
  gradient: string;
  color: string;
}> = [
  { label: 'NO.1', gradient: 'linear-gradient(135deg, #f5e6b3 0%, #c89a3a 100%)', color: '#5a4012' },
  { label: 'NO.2', gradient: 'linear-gradient(135deg, #34302a 0%, #171410 100%)', color: '#f5f3ee' },
  { label: 'NO.3', gradient: 'linear-gradient(135deg, #d7ad55 0%, #9f7a2a 100%)', color: '#3a2a0a' },
];

/** 用 id hash 产出确定性"近 30 日"涨幅（mock 视觉用，不替代后端） */
function deriveVisualMetrics(id: string, base: number) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) % 1_000_000;
  }
  const seed = hash / 1_000_000;
  const pnl30 = +(seed * 38 + base).toFixed(1); // 0 ~ ~40
  const points: number[] = [];
  let y = 50;
  for (let i = 0; i < 11; i++) {
    y += (((hash >> (i % 6)) & 0xff) - 96) / 12;
    if (y < 18) y = 18;
    if (y > 82) y = 82;
    points.push(+y.toFixed(1));
  }
  // 拉低首点，让收益曲线向右上方
  points[0] = Math.min(points[0] + 12, 80);
  return { pnl30, points };
}

/** SVG 收益曲线 */
function PnlSparkline({ points }: { points: number[] }) {
  const width = 240;
  const height = 60;
  const step = width / (points.length - 1);
  const polyline = points
    .map((y, i) => `${(i * step).toFixed(1)},${(height - ((100 - y) / 100) * height).toFixed(1)}`)
    .join(' ');
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="block h-14 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c0362c" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#c0362c" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={`0,${height} ${polyline} ${width},${height}`}
        fill="url(#pnlFill)"
        stroke="none"
      />
      <polyline points={polyline} fill="none" stroke="#c0362c" strokeWidth="1.5" />
    </svg>
  );
}

/** 单个研究员卡片 */
function ResearcherCard({ item, rank }: { item: ResearcherMarketCard; rank: number }) {
  const hire = useHireResearcher();
  const primary = rank < 3;
  const ribbon = primary ? RIBBONS[rank] : null;

  // 取首个 tag 作为流派；找不到时默认
  const style = item.tags[0] ?? '综合';
  const avatarBg = styleColor[style] ?? '#1d4a34';
  const initial = item.name.slice(0, 1);

  const { pnl30, points } = useMemo(
    () => deriveVisualMetrics(item.id, primary ? 22 : 8),
    [item.id, primary],
  );

  // 单次订阅按钮的算力价格（视觉值，由 hire_count 派生）
  const monthlyPower = 200 + ((item.hire_count % 12) + 1) * 50;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-ink-50 bg-white shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-lg">
      {ribbon && (
        <span
          aria-hidden
          className="serif text-[11px] font-bold tracking-[0.08em]"
          style={{
            position: 'absolute',
            top: 0,
            left: 16,
            background: ribbon.gradient,
            color: ribbon.color,
            padding: '4px 10px 5px',
            borderRadius: '0 0 6px 6px',
            boxShadow: '0 2px 6px rgba(23,20,16,0.12)',
          }}
        >
          {ribbon.label}
        </span>
      )}

      <div className="p-5 pt-6">
        {/* 头部：头像 + 名称 + 创建者 */}
        <div className="mb-3 flex items-center gap-3">
          <div
            className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl text-base font-semibold text-white"
            style={{ backgroundColor: avatarBg }}
          >
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <div className="serif truncate text-[15px] font-semibold text-ink-900">{item.name}</div>
            <div className="mt-0.5 truncate text-[11.5px] text-ink-400">
              {style} · {item.level}
            </div>
          </div>
        </div>

        {/* 简介 */}
        <p className="mb-3 line-clamp-2 min-h-[34px] text-[12.5px] leading-relaxed text-ink-500">
          {item.introduction}
        </p>

        {/* 收益曲线 */}
        <div className="mb-3 -mx-1">
          <PnlSparkline points={points} />
        </div>

        {/* 双列数据 */}
        <div className="mb-4 grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-ink-25 px-3 py-2">
            <div className="text-[10.5px] text-ink-400">近 30 日</div>
            <div className="tnum mt-0.5 text-[15px] font-bold text-up-600">+{pnl30}%</div>
          </div>
          <div className="rounded-lg bg-ink-25 px-3 py-2">
            <div className="text-[10.5px] text-ink-400">订阅数</div>
            <div className="tnum mt-0.5 text-[15px] font-bold text-ink-800">
              {item.hire_count.toLocaleString('zh-CN')}
            </div>
          </div>
        </div>

        {/* 订阅按钮 */}
        <button
          type="button"
          disabled={item.is_hired || hire.isPending}
          onClick={() => !item.is_hired && hire.mutate(item.id)}
          className={[
            'flex w-full items-center justify-center gap-1.5 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all',
            item.is_hired
              ? 'cursor-default border border-ink-50 bg-ink-25 text-ink-500'
              : primary
                ? 'bg-brand-600 text-white shadow-brand hover:bg-brand-700'
                : 'border border-ink-50 bg-white text-ink-800 hover:border-brand-600 hover:text-brand-600',
            hire.isPending ? 'opacity-60' : '',
          ].join(' ')}
        >
          {item.is_hired ? (
            <span>已订阅</span>
          ) : (
            <>
              <span aria-hidden>⚡</span>
              <span>订阅 · {monthlyPower} 算力/月</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

/** 人才市场主组件 */
export function TalentMarketPageClient() {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('hot');
  const [style, setStyle] = useState<string>('全部');
  const { data, isLoading } = useMarketResearchers({ q: search || undefined });

  const items = useMemo(() => {
    let list = data?.items ?? [];
    if (style !== '全部') {
      list = list.filter((r) => r.tags.includes(style));
    }
    return list;
  }, [data, style]);

  return (
    <div className="space-y-5">
      <SectionHeading
        title="人才市场"
        subtitle="发现表现优异的 AI 研究员 · 一键订阅纳入工作台"
        actions={
          <Segmented
            size="small"
            value={sort}
            onChange={(v) => setSort(v as SortKey)}
            options={[
              { label: '热门', value: 'hot' },
              { label: '收益榜', value: 'pnl' },
              { label: '夏普榜', value: 'sharpe' },
              { label: '最新', value: 'latest' },
            ]}
          />
        }
      />

      {/* 搜索 + 流派筛选 */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Input
          prefix={<SearchOutlined className="text-ink-300" />}
          placeholder="搜索研究员名称或关键词…"
          className="w-full sm:!w-72"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {STYLE_CHIPS.map((chip) => {
          const active = style === chip;
          return (
            <button
              key={chip}
              type="button"
              onClick={() => setStyle(chip)}
              className={[
                'rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
                active
                  ? 'bg-brand-600 text-white shadow-brand'
                  : 'border border-ink-50 bg-white text-ink-600 hover:border-brand-600 hover:text-brand-600',
              ].join(' ')}
            >
              {chip}
            </button>
          );
        })}
      </div>

      {/* 列表 */}
      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && items.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {items.map((item, idx) => (
            <ResearcherCard key={item.id} item={item} rank={idx} />
          ))}
        </div>
      )}

      {!isLoading && items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-ink-50 bg-white py-24 text-center text-ink-400">
          暂无匹配的研究员
        </div>
      )}
    </div>
  );
}
