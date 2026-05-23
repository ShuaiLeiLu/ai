/**
 * MCP 市场页面
 *
 * 属于"极睿实验室"子页面之一，路由：/workstation/mcp-market
 * 接入外部工具与数据 · 已启用 X / 可用 N
 *
 * 数据流：useMcpServers() hook 拉取后端接口
 */
'use client';

import { useMemo, useState } from 'react';
import { Input, Segmented, Spin } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

import { SectionHeading } from '@/components/ui/section-heading';
import { useMcpServers } from '@/features/ecosystem/hooks';
import type { McpServerItem } from '@/types/ecosystem';

type McpFilter = 'all' | 'connected' | 'disconnected';

/** 提供商 → 品牌色 / 缩写 / icon 文本 */
interface BrandStyle {
  bg: string;
  fg: string;
  abbr: string;
}

const BRAND_MAP: Array<{ test: RegExp; brand: BrandStyle }> = [
  { test: /同花顺|ths|10jqka/i, brand: { bg: '#c0362c', fg: '#ffffff', abbr: '同' } },
  { test: /雪球|xueqiu|snowball/i, brand: { bg: '#1d4a34', fg: '#ffffff', abbr: '雪' } },
  { test: /wind|万得/i, brand: { bg: '#c89a3a', fg: '#ffffff', abbr: 'W' } },
  { test: /akshare|ak-?share/i, brand: { bg: '#5d564b', fg: '#ffffff', abbr: 'AK' } },
  { test: /东方财富|eastmoney/i, brand: { bg: '#3f9a67', fg: '#ffffff', abbr: '东' } },
  { test: /财联社|cls/i, brand: { bg: '#d8453a', fg: '#ffffff', abbr: '财' } },
  { test: /自建|私有|custom|self/i, brand: { bg: '#4a443a', fg: '#ffffff', abbr: '私' } },
];

function pickBrand(name: string): BrandStyle {
  for (const { test, brand } of BRAND_MAP) {
    if (test.test(name)) return brand;
  }
  // fallback —— 用名称首字
  return { bg: '#1d4a34', fg: '#ffffff', abbr: name.slice(0, 1) || 'M' };
}

/** 派生数据源类型：免费 / VIP / 自建 */
function deriveTier(item: McpServerItem): 'free' | 'vip' | 'custom' {
  if (/wind|level2|vip/i.test(item.name)) return 'vip';
  if (/自建|私有|custom|self/i.test(item.name)) return 'custom';
  return 'free';
}

/** 根据 category 派生标签 chips */
function deriveCapabilities(item: McpServerItem): string[] {
  const cat = (item.category || '').toLowerCase();
  if (cat.includes('market') || cat.includes('行情')) return ['实时行情', 'K 线', '盘口'];
  if (cat.includes('news') || cat.includes('公告')) return ['公告', '新闻', '订阅'];
  if (cat.includes('finance') || cat.includes('财报')) return ['财报', '指标', '估值'];
  return ['通用', '接口'];
}

/** 单个 MCP 卡 */
function McpCard({ item }: { item: McpServerItem }) {
  const brand = useMemo(() => pickBrand(item.name), [item.name]);
  const tier = useMemo(() => deriveTier(item), [item]);
  const caps = useMemo(() => deriveCapabilities(item), [item]);

  let statusText: string;
  let statusCls: string;
  if (item.connected) {
    statusText = '已启用';
    statusCls = 'text-down-600';
  } else if (tier === 'vip') {
    statusText = 'VIP 套餐';
    statusCls = 'text-gold-600';
  } else if (tier === 'custom') {
    statusText = '未配置';
    statusCls = 'text-ink-400';
  } else {
    statusText = '未启用';
    statusCls = 'text-ink-400';
  }

  // 描述派生
  const description =
    item.category === 'market-data'
      ? '提供实时行情数据、K 线、Level2 等市场数据接入能力'
      : item.category === 'news'
        ? '提供公告全文检索、关键词订阅等信息检索能力'
        : `${item.category} · 标准 MCP 数据源接入`;

  // 行动按钮
  let actionEl: React.ReactNode;
  if (item.connected) {
    actionEl = (
      <button
        type="button"
        className="w-full rounded-lg border border-ink-50 bg-ink-25 px-3 py-2 text-[12.5px] font-medium text-ink-600"
      >
        已启用 · 管理
      </button>
    );
  } else if (tier === 'vip') {
    actionEl = (
      <button
        type="button"
        className="w-full rounded-lg bg-gradient-to-r from-gold-400 to-gold-600 px-3 py-2 text-[12.5px] font-medium text-white shadow-gold hover:from-gold-500 hover:to-gold-700"
      >
        升级解锁
      </button>
    );
  } else if (tier === 'custom') {
    actionEl = (
      <button
        type="button"
        className="w-full rounded-lg border border-ink-50 bg-white px-3 py-2 text-[12.5px] font-medium text-ink-700 hover:border-brand-600 hover:text-brand-600"
      >
        配置
      </button>
    );
  } else {
    actionEl = (
      <button
        type="button"
        className="w-full rounded-lg bg-brand-600 px-3 py-2 text-[12.5px] font-medium text-white shadow-brand hover:bg-brand-700"
      >
        + 接入
      </button>
    );
  }

  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-ink-50 bg-white shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-lg">
      <div className="flex flex-1 flex-col p-5">
        {/* 头部 */}
        <div className="mb-3 flex items-center gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-[14px] font-bold"
            style={{ backgroundColor: brand.bg, color: brand.fg }}
          >
            {brand.abbr}
          </div>
          <div className="min-w-0 flex-1">
            <div className="serif truncate text-[14.5px] font-semibold text-ink-900">{item.name}</div>
            <div className={['mt-0.5 text-[11.5px] font-medium', statusCls].join(' ')}>{statusText}</div>
          </div>
        </div>

        {/* 描述 */}
        <p className="mb-3 line-clamp-2 min-h-[32px] text-[12px] leading-relaxed text-ink-500">
          {description}
        </p>

        {/* 能力 chips */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          {caps.map((cap) => (
            <span
              key={cap}
              className="rounded-md bg-ink-25 px-2 py-0.5 text-[10.5px] font-medium text-ink-600"
            >
              {cap}
            </span>
          ))}
        </div>

        {/* 操作 */}
        <div className="mt-auto">{actionEl}</div>
      </div>
    </div>
  );
}

/** MCP 市场主组件 */
export function McpMarketPageClient() {
  const [filter, setFilter] = useState<McpFilter>('all');
  const [search, setSearch] = useState('');
  const { data, isLoading } = useMcpServers();

  const list = data ?? [];
  const enabledCount = list.filter((s) => s.connected).length;

  const filtered = useMemo(() => {
    return list
      .filter((item) => {
        if (filter === 'connected') return item.connected;
        if (filter === 'disconnected') return !item.connected;
        return true;
      })
      .filter((item) =>
        search ? item.name.includes(search) || item.category.includes(search) : true,
      );
  }, [list, filter, search]);

  return (
    <div className="space-y-5">
      <SectionHeading
        title="MCP 市场"
        subtitle={`接入外部工具与数据 · 已启用 ${enabledCount} / 可用 ${list.length}`}
        actions={
          <Segmented
            size="small"
            value={filter}
            onChange={(v) => setFilter(v as McpFilter)}
            options={[
              { label: '全部', value: 'all' },
              { label: `已启用 ${enabledCount}`, value: 'connected' },
              { label: `未启用 ${list.length - enabledCount}`, value: 'disconnected' },
            ]}
          />
        }
      />

      <Input
        prefix={<SearchOutlined className="text-ink-300" />}
        placeholder="搜索 MCP 服务器…"
        className="w-full sm:!w-72"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
      />

      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((it) => (
            <McpCard key={it.server_id} item={it} />
          ))}
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-ink-50 bg-white py-24 text-center text-ink-400">
          暂无匹配的 MCP 服务
        </div>
      )}
    </div>
  );
}
