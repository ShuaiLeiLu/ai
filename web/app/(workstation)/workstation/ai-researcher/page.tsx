/**
 * AI研究员工作台 —— 完全对标目标站截图
 *
 * 布局：
 *  - 左侧面板：页面标题 + 总览入口 + 已雇佣研究员列表（彩色头像）+ 底部链接
 *  - 右侧主区域：
 *    - 未选中时 → 首页（标题说明 + 热门文档 + 排行榜）
 *    - 选中时 → 研究员详情（Header + 最新制品横向卡片 + 模拟账户持仓表）
 *
 * 数据流：
 *  - useWorkbenchOverview() 首屏聚合数据：已雇佣研究员、热门文档、公开排行榜
 *  - useTradingPortfolio()  模拟账户轻量快照
 */
'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  Badge,
  Button,
  Empty,
  Segmented,
  Skeleton,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import {
  AppstoreOutlined,
  ClockCircleOutlined,
  EyeOutlined,
  FileTextOutlined,
  MessageOutlined,
  PlusOutlined,
  RightOutlined,
  SettingOutlined,
} from '@ant-design/icons';

import { useWorkbenchOverview } from '@/features/researcher-workbench/hooks';
import { useTradingPortfolio } from '@/features/trading/hooks';
import { routes } from '@/lib/constants/routes';
import { useUserSessionStore } from '@/stores/user-session.store';
import type { HiredResearcher, HotDocument, PublicRankItem, RankSortBy } from '@/types/researcher-workbench';

// ──────────── 常量与工具函数 ────────────

/** 研究员头像映射 —— 根据名称关键词匹配 SVG 头像 */
const AVATAR_MAP: Record<string, string> = {
  '阿平': '/avatars/researcher-aping.svg',
  '阿发': '/avatars/researcher-afa.svg',
  '阿龙': '/avatars/researcher-along.svg',
};

/** 研究员头像背景色映射 */
const AVATAR_BG_MAP: Record<string, string> = {
  '阿平': 'bg-orange-100',
  '阿发': 'bg-purple-100',
  '阿龙': 'bg-blue-100',
};

/** 根据研究员名称获取头像路径 */
function getAvatarSrc(name: string): string {
  for (const [key, src] of Object.entries(AVATAR_MAP)) {
    if (name.includes(key)) return src;
  }
  return '/avatars/researcher-aping.svg';
}

/** 根据研究员名称获取头像背景色 */
function getAvatarBg(name: string): string {
  for (const [key, bg] of Object.entries(AVATAR_BG_MAP)) {
    if (name.includes(key)) return bg;
  }
  return 'bg-slate-100';
}

/** 根据收益正负返回对应的 Tailwind 文字色 */
function yieldColor(value: number) {
  if (value > 0) return 'text-rose-500';
  if (value < 0) return 'text-emerald-600';
  return 'text-slate-500';
}

/** 将小数收益率转为百分比字符串，正数加 + 号 */
function formatPct(value: number) {
  const pct = (value * 100).toFixed(2);
  return value > 0 ? `+${pct}%` : `${pct}%`;
}

/** 格式化资产金额（万） */
function formatWan(value: number) {
  return (value / 10000).toFixed(2) + '万';
}

/** 格式化资产数字，保留两位小数并加千分位 */
function formatMoney(value: number) {
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** 格式化资产数字，保留整数并加千分位 */
function formatAsset(value: number) {
  return Math.round(value).toLocaleString('zh-CN');
}

/** ISO 时间字符串 → "YYYY-MM-DD" */
function formatDate(value: string) {
  const d = new Date(value);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** 计算时间距离现在多久（如"13小时前"） */
function timeAgo(value: string) {
  const now = Date.now();
  const then = new Date(value).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}小时前`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}天前`;
}

// ──────────── 左侧面板 ────────────

/**
 * 左侧研究员列表面板
 * 对标截图：页面标题 + 辅助说明 → 总览按钮 → 研究员列表（彩色头像） → 底部链接
 */
function SidePanel({
  researchers,
  loading,
  activeId,
  onSelect,
}: {
  researchers: HiredResearcher[];
  loading: boolean;
  activeId: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      {/* 页面标题 */}
      <div className="px-3.5 pb-3 pt-4">
        <div className="text-base font-bold text-slate-800">AI研究员</div>
        <div className="mt-1 text-xs leading-relaxed text-slate-400">
          辅助您投研决策的垂直领域专家
        </div>
      </div>

      {/* 总览入口 */}
      <div className="mb-1 px-2.5">
        <button
          type="button"
          onClick={() => onSelect(null)}
          className={`flex w-full items-center gap-2.5 rounded-md border px-3 py-2.5 text-left text-sm transition-colors ${
            activeId === null
              ? 'border-amber-200 bg-amber-50 text-amber-700 font-medium'
              : 'border-transparent text-slate-600 hover:bg-slate-50'
          }`}
        >
          <AppstoreOutlined className={activeId === null ? 'text-amber-500' : 'text-slate-400'} />
          总览
        </button>
      </div>

      {/* 研究员列表 */}
      <div className="flex-1 overflow-y-auto px-2.5">
        {loading && (
          <div className="space-y-3 p-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} avatar active paragraph={{ rows: 0 }} />
            ))}
          </div>
        )}
        {!loading && researchers.length === 0 && (
          <div className="py-8 text-center text-xs text-slate-400">暂无研究员</div>
        )}
        {!loading &&
          researchers.map((r) => {
            const active = r.researcher_id === activeId;
            return (
              <button
                key={r.researcher_id}
                type="button"
                onClick={() => onSelect(r.researcher_id)}
                className={`mb-1 flex w-full items-center gap-2.5 rounded-md border px-3 py-2.5 text-left transition-colors ${
                  active ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-transparent hover:bg-slate-50'
                }`}
              >
                {/* 彩色机器人头像 */}
                <div className={`h-8 w-8 shrink-0 overflow-hidden rounded-md ${getAvatarBg(r.name)}`}>
                  <Image
                    src={getAvatarSrc(r.name)}
                    alt={r.name}
                    width={32}
                    height={32}
                    className="w-full h-full object-cover"
                  />
                </div>
                <span className={`truncate text-sm ${active ? 'font-semibold' : 'font-medium text-slate-700'}`}>
                  {r.name}
                </span>
              </button>
            );
          })}
      </div>

      {/* 底部链接 */}
      <div className="space-y-2 border-t border-slate-100 px-3.5 py-3">
        <Link
          href={routes.labTalentMarket}
          className="flex items-center gap-1 text-xs text-brand-500 hover:text-brand-600 transition-colors"
        >
          招募研究员 <RightOutlined style={{ fontSize: 10 }} />
        </Link>
        <Link
          href={routes.labCreateResearcher}
          className="flex items-center gap-1 text-xs text-brand-500 hover:text-brand-600 transition-colors"
        >
          创建研究员 <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>
    </div>
  );
}

// ──────────── 首页视图子组件 ────────────

function ResearcherCardsSection({
  researchers,
  loading,
  onSelect,
}: {
  researchers: HiredResearcher[];
  loading: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Typography.Title level={5} className="!mb-1 !text-lg">研究员卡片</Typography.Title>
          <div className="text-sm text-slate-400">快速进入研究员工作区，查看制品、模拟盘和任务状态</div>
        </div>
        <Link href={routes.labTalentMarket} className="flex items-center gap-1 text-sm text-amber-500 hover:text-amber-600">
          扩充团队 <RightOutlined style={{ fontSize: 11 }} />
        </Link>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-slate-100 p-4">
              <Skeleton avatar active paragraph={{ rows: 4 }} />
            </div>
          ))}
        </div>
      ) : researchers.length === 0 ? (
        <div className="py-10">
          <Empty description="暂无研究员" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {researchers.map((r) => (
            <button
              key={r.researcher_id}
              type="button"
              onClick={() => onSelect(r.researcher_id)}
              className="group rounded-xl border border-slate-100 bg-gradient-to-br from-white to-slate-50 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-amber-200 hover:shadow-md"
            >
              <div className="mb-4 flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className={`h-12 w-12 overflow-hidden rounded-xl ${getAvatarBg(r.name)}`}>
                    <Image src={getAvatarSrc(r.name)} alt={r.name} width={48} height={48} className="h-full w-full object-cover" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-slate-800">{r.name}</span>
                      <span className="rounded-full bg-amber-400 px-2 py-0.5 text-xs font-medium text-white">{r.level || 'LV.2'}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-400">
                      <Badge status={r.status === 'active' ? 'processing' : 'default'} />
                      <span>{r.status === 'active' ? '努力工作中' : '空闲'}</span>
                    </div>
                  </div>
                </div>
                <RightOutlined className="mt-2 text-xs text-slate-300 transition-colors group-hover:text-amber-500" />
              </div>

              <div className="line-clamp-2 min-h-10 text-sm leading-relaxed text-slate-500">
                {r.summary || '专注小市值策略跟踪、交易复盘与次日计划。'}
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {((r.tags ?? []).length > 0 ? r.tags : ['模拟盘', '策略跟踪']).slice(0, 3).map((tag) => (
                  <span key={tag} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-500 ring-1 ring-slate-100">
                    {tag}
                  </span>
                ))}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4">
                <div>
                  <div className="text-xs text-slate-400">今日盈亏</div>
                  <div className={`mt-1 text-lg font-black ${yieldColor(r.today_yield)}`}>
                    {r.today_yield > 0 ? '+' : ''}{formatMoney(r.today_yield)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">30日胜率</div>
                  <div className="mt-1 text-lg font-black text-slate-800">
                    {formatPct(r.win_rate_30d)}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HotDocumentsSection({
  documents,
  loading,
}: {
  documents: HotDocument[];
  loading: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Typography.Title level={5} className="!mb-0 !text-lg">24小时内热门文档</Typography.Title>
        <Link href={routes.documents} className="flex items-center gap-1 text-sm text-amber-500 hover:text-amber-600">
          查看全部 <RightOutlined style={{ fontSize: 11 }} />
        </Link>
      </div>
      {loading ? (
        <div className="flex gap-4 overflow-hidden">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-56 w-64 shrink-0 rounded-xl border border-slate-100 p-4">
              <Skeleton active paragraph={{ rows: 3 }} title={false} />
            </div>
          ))}
        </div>
      ) : documents.length === 0 ? (
        <div className="py-10">
          <Empty description="暂无热门文档" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-1">
          {documents.slice(0, 8).map((doc, index) => {
            const accents = [
              'bg-rose-50 text-rose-500',
              'bg-blue-50 text-blue-500',
              'bg-emerald-50 text-emerald-500',
              'bg-amber-50 text-amber-500',
              'bg-violet-50 text-violet-500',
              'bg-cyan-50 text-cyan-500',
            ];
            return (
              <div
                key={doc.id}
                className={`flex h-56 w-64 shrink-0 cursor-pointer flex-col rounded-xl border border-slate-100 p-4 transition-all hover:-translate-y-0.5 hover:shadow-md ${accents[index % accents.length]}`}
              >
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-white/70 text-2xl font-black leading-none">“</div>
                <div className="line-clamp-2 text-base font-bold leading-snug text-slate-800">{doc.title}</div>
                <div className="mt-3 line-clamp-3 flex-1 text-sm leading-relaxed text-slate-500">{doc.summary}</div>
                <div className="mt-3 border-t border-white/70 pt-3 text-sm text-slate-400">
                  <div className="flex items-center justify-between">
                    <span className="truncate">{doc.researcher_name}</span>
                    <span className="flex items-center gap-1"><EyeOutlined />{doc.view_count}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** 排行榜单行 */
function RankRow({ item, sortBy, rank }: { item: PublicRankItem; sortBy: RankSortBy; rank: number }) {
  const yieldRate = sortBy === 'today' ? item.today_yield_rate : item.month_yield_rate;
  const subRate = sortBy === 'today' ? item.month_yield_rate : item.today_yield_rate;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-100 bg-white px-3.5 py-3 transition-colors hover:bg-slate-50">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-100 bg-slate-50 text-sm font-bold text-slate-400">
        {rank}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className={`h-7 w-7 overflow-hidden rounded-full ${getAvatarBg(item.name)}`}>
            <Image src={getAvatarSrc(item.name)} alt={item.name} width={28} height={28} className="h-full w-full object-cover" />
          </div>
          <span className="truncate text-sm font-semibold text-slate-700">{item.name}</span>
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-500">{item.risk_note}</span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-xs">
          <span className={yieldColor(yieldRate)}>今日 {formatPct(yieldRate)}</span>
          <span className={yieldColor(subRate)}>本月 {formatPct(subRate)}</span>
        </div>
      </div>
      <div className="shrink-0 text-right text-sm font-semibold text-slate-500">{formatWan(item.total_asset)}</div>
    </div>
  );
}

/** 模拟交易排名区 */
function RankingSection({
  rankings,
  loading,
  sortBy,
  onSortChange,
}: {
  rankings: PublicRankItem[];
  loading: boolean;
  sortBy: RankSortBy;
  onSortChange: (value: RankSortBy) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <Typography.Title level={5} className="!mb-0 !text-lg">模拟交易排名</Typography.Title>
          <span className="text-sm text-slate-400">公开研究员</span>
        </div>
        <div className="flex items-center gap-2">
          <Segmented
            size="small"
            value={sortBy}
            options={[
              { label: '今日收益率', value: 'today' },
              { label: '本月收益率', value: 'month' },
            ]}
            onChange={(v) => onSortChange(v as RankSortBy)}
          />
        </div>
      </div>
      {loading ? (
        <Skeleton active paragraph={{ rows: 5 }} />
      ) : rankings.length === 0 ? (
        <Empty description="暂无排名数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className={`grid grid-cols-1 gap-3 ${rankings.length > 1 ? 'lg:grid-cols-2' : ''}`}>
          {rankings.map((item, index) => (
            <RankRow key={item.researcher_id} item={item} sortBy={sortBy} rank={index + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────── 研究员详情视图子组件 ────────────

/**
 * 最新制品 —— 横向滚动文档卡片
 * 对标截图：紫色引号图标 + 日期标题 + 内容摘要 + 底部作者/浏览/评论/时间
 */
function LatestDocuments({
  documents,
  loading,
  researcherName,
}: {
  documents: HotDocument[];
  loading: boolean;
  researcherName: string;
}) {
  if (loading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="w-60 shrink-0 rounded-xl border border-slate-200 p-4">
            <Skeleton active paragraph={{ rows: 3 }} />
          </div>
        ))}
      </div>
    );
  }
  if (documents.length === 0) {
    return <div className="py-8 text-center text-sm text-slate-400">暂无最新制品</div>;
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin">
      {documents.slice(0, 8).map((doc, index) => {
        const accents = [
          'bg-rose-50',
          'bg-blue-50',
          'bg-emerald-50',
          'bg-amber-50',
          'bg-violet-50',
          'bg-cyan-50',
        ];
        return (
          <div
            key={doc.id}
            className={`flex h-48 w-52 shrink-0 cursor-pointer flex-col rounded-lg border border-slate-100 p-3.5 transition-all hover:-translate-y-0.5 hover:shadow-md ${accents[index % accents.length]}`}
          >
            <div className="mb-2.5 flex items-start gap-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/80 text-xl font-black leading-none text-brand-500">“</div>
              <div className="line-clamp-2 text-sm font-bold leading-snug text-slate-800">
                {formatDate(doc.create_time)} {doc.title}
              </div>
            </div>
            <div className="line-clamp-3 flex-1 text-xs leading-relaxed text-slate-500">{doc.summary}</div>
            <div className="mt-2.5 border-t border-white/70 pt-2">
              <div className="mb-1.5 flex items-center gap-1.5 text-xs text-brand-500">
                <div className={`h-5 w-5 shrink-0 overflow-hidden rounded ${getAvatarBg(researcherName)}`}>
                  <Image src={getAvatarSrc(researcherName)} alt="" width={20} height={20} />
                </div>
                <span className="truncate">{researcherName}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-2">
                <span className="flex items-center gap-0.5"><EyeOutlined /> {doc.view_count}</span>
                <span className="flex items-center gap-0.5"><MessageOutlined /> {doc.comment_count}</span>
              </span>
                <span>{timeAgo(doc.create_time)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * 模拟账户区块
 * 对标截图：左侧显示总资产/今日盈亏/今日收益率 + 持仓资金/可用资金
 *           右侧显示持仓表格（股票/数量/成本价）
 */
function PortfolioSection({ researcher }: { researcher: HiredResearcher }) {
  const rid = researcher.researcher_id;
  const snapshotQuery = useTradingPortfolio(rid);

  const loading = snapshotQuery.isLoading && !snapshotQuery.data;
  const acct = snapshotQuery.data?.account;
  const positions = snapshotQuery.data?.positions ?? [];

  const todayPnl = acct?.daily_pnl ?? 0;
  const todayStartAsset = acct ? acct.total_asset - todayPnl : 1_000_000;
  const todayPnlPct = todayStartAsset > 0 ? todayPnl / todayStartAsset : 0;

  /** 当前月份 */
  const currentMonth = `${new Date().getMonth() + 1}月`;

  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3.5">
      {/* 标题行 —— 对标截图样式 */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Typography.Title level={5} className="!mb-0 !text-base">模拟账户</Typography.Title>
          <span className="text-xs text-slate-400">当前持仓</span>
          <span className="text-xs text-slate-400">{currentMonth}</span>
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="inline-block h-2 w-2 rounded-full bg-slate-300" />
            实时连接已关闭
          </span>
        </div>
        <Link
          href={routes.tradingDetail(rid)}
          className="text-xs text-brand-500 hover:text-brand-600 flex items-center gap-0.5 transition-colors"
        >
          查看详情 <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>

      {/* 加载态 */}
      {loading && <Skeleton active paragraph={{ rows: 5 }} />}

      {/* 数据态 —— 对标目标站：左侧账户指标 + 中间持仓表 + 右侧成长/致谢卡 */}
      {!loading && acct && (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[180px_minmax(480px,1fr)_200px_200px]">
          {/* ── 左侧：账户概览（紧凑布局） ── */}
          <div className="space-y-3">
            {/* 总资产 */}
            <div>
              <div className="text-xs text-slate-400 mb-0.5">总资产</div>
              <div className="text-2xl font-bold text-slate-800 tracking-tight">
                {formatWan(acct.total_asset)}
              </div>
            </div>

            {/* 今日盈亏 + 今日收益率（折行显示） */}
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="text-xs text-slate-400">今日盈亏</span>
              <span className={`text-base font-bold ${yieldColor(todayPnl)}`}>
                {todayPnl > 0 ? '+' : ''}{formatMoney(todayPnl)}
              </span>
              <span className="text-xs text-slate-400">今日收益率</span>
              <span className={`text-sm font-semibold ${yieldColor(todayPnlPct)}`}>
                {formatPct(todayPnlPct)}
              </span>
            </div>

            {/* 持仓资金 / 可用资金 */}
            <div className="flex gap-2">
              <div className="flex-1 rounded-lg bg-slate-50 px-2.5 py-2">
                <div className="text-xs text-slate-400 mb-0.5">持仓资金</div>
                <div className="text-sm font-bold text-slate-700">{formatWan(acct.holding_value)}</div>
              </div>
              <div className="flex-1 rounded-lg bg-slate-50 px-2.5 py-2">
                <div className="text-xs text-slate-400 mb-0.5">可用资金</div>
                <div className="text-sm font-bold text-brand-600">{formatWan(acct.available_cash)}</div>
              </div>
            </div>
          </div>

          {/* ── 右侧：持仓表格（最多显示5行，超出滚动） ── */}
          <div className="min-w-0">
            <div className="max-h-[190px] overflow-x-auto overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="border-b border-slate-100 text-left text-xs text-slate-400">
                    <th className="px-2 py-2 font-medium">股票</th>
                    <th className="px-2 py-2 font-medium text-right">数量</th>
                    <th className="px-2 py-2 font-medium text-right">成本价</th>
                    <th className="px-2 py-2 font-medium text-right">现价</th>
                    <th className="px-2 py-2 font-medium text-right">盈亏</th>
                    <th className="px-2 py-2 font-medium text-right">盈亏%</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-sm text-slate-400">
                        暂无持仓 — 策略待执行或尚未开盘
                      </td>
                    </tr>
                  ) : positions.map((p) => (
                    <tr key={p.symbol} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                      <td className="px-2 py-2">
                        <div className="font-medium text-slate-800">{p.name}</div>
                        <div className="text-xs text-slate-400">{p.symbol}</div>
                      </td>
                      <td className="px-2 py-2 text-right text-slate-600">{p.quantity}</td>
                      <td className="px-2 py-2 text-right text-slate-600">{p.cost_price.toFixed(2)}</td>
                      <td className="px-2 py-2 text-right text-slate-600">{p.current_price.toFixed(2)}</td>
                      <td className="px-2 py-2 text-right">
                        <div className={`font-semibold ${yieldColor(p.pnl)}`}>
                          {p.pnl > 0 ? '+' : ''}{p.pnl.toFixed(2)}
                        </div>
                      </td>
                      <td className="px-2 py-2 text-right">
                        <div className={`text-xs font-semibold ${yieldColor(p.pnl)}`}>
                          {p.cost_price > 0
                            ? `${((p.current_price - p.cost_price) / p.cost_price * 100).toFixed(2)}%`
                            : '-'}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3">
            <div className="mb-2 flex items-center justify-between text-xs text-cyan-700">
              <span>成长Token余量</span>
              <span className="rounded-full border border-cyan-200 px-1.5">?</span>
            </div>
            <div className="text-2xl font-black text-cyan-600">981.8K</div>
            <div className="mt-1 text-xs text-slate-400">累计接收 78743.2K　已消耗 77761.4K</div>
            <button className="mt-8 w-full rounded-md bg-cyan-100 py-1.5 text-xs font-medium text-cyan-700 transition-colors hover:bg-cyan-200" type="button">
              捐赠
            </button>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3">
            <div className="mb-2 flex items-center justify-between text-xs text-amber-600">
              <span>致谢榜Top5</span>
              <span className="text-xs text-slate-300">今日捐赠</span>
            </div>
            <div className="flex h-[110px] items-center justify-center text-xs text-slate-300">暂无捐赠</div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 工作日志时间线 */
function WorkLogSection() {
  const logs = [
    { time: '2026-04-18 09:31:25', type: '任务执行', content: '今天是新的交易日, 需要全面分析市场情况, 判断大盘走势, 挖掘投资机会并给出具体的建议. 重点关注板块轮动和市场热点' },
    { time: '2026-04-17 15:02:10', type: '定时任务', content: '收盘后复盘涨停梯队与炸板数据, 需要对今日市场情绪进行评分, 并给出明日预期和仓位建议.' },
    { time: '2026-04-17 09:30:00', type: '盘前策略', content: '盘前检查行业强弱, 结合北向资金流向与竞价强度, 确认今日操作策略方向.' },
  ];

  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3">
      <div className="mb-3 flex items-center justify-between">
        <Typography.Title level={5} className="!mb-0 !text-sm text-amber-600">工作日志</Typography.Title>
        <Link href="#" className="flex items-center gap-0.5 text-xs text-amber-500 hover:text-amber-600">
          查看详情 <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>
      <Timeline
        items={logs.map((log) => ({
          dot: <ClockCircleOutlined className="text-brand-500" />,
          children: (
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>{log.time}</span>
                <Tag className="!text-xs !px-1.5 !py-0">{log.type}</Tag>
              </div>
              <div className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-600">{log.content}</div>
            </div>
          ),
        }))}
      />
    </div>
  );
}

function GrowthViewSection({ researcher }: { researcher: HiredResearcher }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3.5">
      <Typography.Title level={5} className="!mb-3 !text-base">24小时成长视图</Typography.Title>
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_260px]">
          <div className="relative min-h-[320px] overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
            <div className="absolute inset-0 bg-[linear-gradient(#e5e7eb_1px,transparent_1px),linear-gradient(90deg,#e5e7eb_1px,transparent_1px)] bg-[size:28px_28px] opacity-40" />
          <div className="absolute left-4 top-4 rounded-lg bg-white px-3.5 py-2.5 text-sm shadow-sm">
            <div className="font-semibold text-slate-700">{researcher.name}</div>
            <div className="mt-1.5 flex gap-2 text-xs text-slate-400">
              <span>研究员</span>
              <span>知识</span>
              <span>洞察</span>
              <span>互动</span>
              <span>制品</span>
              <span>交易</span>
              <span>任务</span>
            </div>
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="rounded-lg border border-blue-300 bg-white px-5 py-2.5 text-sm font-semibold text-blue-500 shadow-sm">
              {researcher.name}
            </div>
          </div>
          <div className="absolute bottom-4 left-4 space-y-1 rounded-lg bg-white p-1 shadow-sm">
            <button className="block h-6 w-6 rounded text-slate-400 hover:bg-slate-50" type="button">+</button>
            <button className="block h-6 w-6 rounded text-slate-400 hover:bg-slate-50" type="button">-</button>
            <button className="block h-6 w-6 rounded text-slate-400 hover:bg-slate-50" type="button">↻</button>
          </div>
          <div className="absolute bottom-4 right-4 flex gap-2 rounded-lg bg-white/90 px-3 py-2 text-xs text-slate-400 shadow-sm">
            <span className="text-blue-500">研究员</span>
            <span className="text-emerald-500">知识</span>
            <span className="text-amber-500">洞察</span>
            <span className="text-rose-500">交易</span>
            <span>任务</span>
          </div>
        </div>
        <WorkLogSection />
      </div>
    </div>
  );
}

/**
 * 研究员详情视图 —— 选中某个研究员后显示
 * 对标截图：Header（彩色头像 + 名称 + 黄色等级标签 + 状态） → 最新制品 → 模拟账户 → 工作日志
 */
function ResearcherDetailView({
  researcher,
  documents,
  docsLoading,
}: {
  researcher: HiredResearcher;
  documents: HotDocument[];
  docsLoading: boolean;
}) {
  const [tab, setTab] = useState<'overview' | 'settings'>('overview');

  return (
    <div className="space-y-3">
      {/* ── Header：研究员信息 ── */}
      <div className="rounded-lg border border-slate-100 bg-white px-3.5 py-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {/* 彩色头像 */}
            <div className={`h-10 w-10 overflow-hidden rounded-lg ${getAvatarBg(researcher.name)}`}>
              <Image
                src={getAvatarSrc(researcher.name)}
                alt={researcher.name}
                width={40}
                height={40}
                className="w-full h-full object-cover"
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold text-slate-800">{researcher.name}</span>
                {/* 黄色等级标签 —— 对标截图 "中国研究员" */}
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-0.5 text-xs font-medium text-white">
                  {researcher.level || '中国研究员'}
                </span>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Badge status={researcher.status === 'active' ? 'processing' : 'default'} />
                <span className="text-xs text-slate-400">
                  {researcher.status === 'active' ? '努力工作中' : '空闲'}
                </span>
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex flex-wrap items-center gap-1.5">
            <Button size="small" icon={<AppstoreOutlined />}>待办列表 0</Button>
            <Button size="small" icon={<FileTextOutlined />}>制品仓库</Button>
            <Button size="small" icon={<ClockCircleOutlined />}>定时任务</Button>
            <Button size="small" type="primary" icon={<PlusOutlined />}>发布任务</Button>
          </div>
        </div>

        {/* Tab 切换 —— 概览 / 设置 */}
        <div className="mt-3">
          <Segmented
            value={tab}
            options={[
              { label: '概览', value: 'overview', icon: <FileTextOutlined /> },
              { label: '设置', value: 'settings', icon: <SettingOutlined /> },
            ]}
            onChange={(v) => setTab(v as typeof tab)}
          />
        </div>
      </div>

      {/* ── Tab 内容 ── */}
      {tab === 'overview' && (
        <>
          {/* 最新制品 —— 横向滚动卡片 */}
          <div className="rounded-lg border border-slate-100 bg-white p-3.5">
            <div className="mb-3 flex items-center justify-between">
              <Typography.Title level={5} className="!mb-0 !text-base">最新制品</Typography.Title>
              <Link href="#" className="flex items-center gap-0.5 text-xs text-brand-500 hover:text-brand-600">
                所有制品 <RightOutlined style={{ fontSize: 10 }} />
              </Link>
            </div>
            <LatestDocuments
              documents={documents}
              loading={docsLoading}
              researcherName={researcher.name}
            />
          </div>

          {/* 模拟账户 */}
          <PortfolioSection researcher={researcher} />

          {/* 24小时成长视图 */}
          <GrowthViewSection researcher={researcher} />
        </>
      )}

      {tab === 'settings' && (
        <div className="rounded-lg border border-slate-100 bg-white p-6 text-center">
          <SettingOutlined className="text-4xl text-slate-300" />
          <div className="mt-3 text-slate-400">研究员配置面板（技能/知识库/提示词编辑）开发中...</div>
        </div>
      )}
    </div>
  );
}

// ──────────── 页面主组件 ────────────

export default function AIResearcherWorkstationPage() {
  const [activeId, setActiveId] = useState<string | null>(null); // 选中的研究员 ID
  const [sortBy, setSortBy] = useState<RankSortBy>('today');
  const hydrated = useUserSessionStore((s) => s.hydrated);
  const accessToken = useUserSessionStore((s) => s.accessToken);
  const workbenchEnabled = hydrated && Boolean(accessToken);
  const overviewQuery = useWorkbenchOverview(sortBy, workbenchEnabled);
  const hiredResearchers = overviewQuery.data?.hired ?? [];
  const hotDocuments = overviewQuery.data?.hot_documents ?? [];
  const publicRankings = overviewQuery.data?.rankings ?? [];
  const activeResearcher = hiredResearchers.find((r) => r.researcher_id === activeId) ?? null;
  const activeDocuments = activeResearcher
    ? hotDocuments.filter((doc) => doc.researcher_name === activeResearcher.name)
    : hotDocuments;
  const selectedDocuments = activeDocuments.length > 0 ? activeDocuments : hotDocuments;

  return (
    <div className="flex flex-col gap-3 md:flex-row" style={{ minHeight: 'calc(100vh - 56px - 40px)' }}>
      {/* ── 左侧面板 ── */}
      <div className="w-full shrink-0 rounded-lg border border-slate-100 bg-white md:w-52">
        {/* 移动端横滑列表 */}
        <div className="md:hidden p-3 space-y-2">
          <div className="text-sm font-bold text-slate-800 mb-1">AI研究员</div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setActiveId(null)}
              className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                activeId === null ? 'bg-amber-50 text-amber-700 font-semibold' : 'bg-slate-50'
              }`}
            >
              <AppstoreOutlined />
              <span className="whitespace-nowrap">总览</span>
            </button>
            {hiredResearchers.map((r) => {
              const active = r.researcher_id === activeId;
              return (
                <button
                  key={r.researcher_id}
                  type="button"
                  onClick={() => setActiveId(r.researcher_id)}
                  className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                    active ? 'bg-brand-50 text-brand-600 font-semibold' : 'bg-slate-50'
                  }`}
                >
                  <div className={`w-7 h-7 rounded overflow-hidden ${getAvatarBg(r.name)}`}>
                    <Image src={getAvatarSrc(r.name)} alt={r.name} width={28} height={28} />
                  </div>
                  <span className="whitespace-nowrap">{r.name}</span>
                </button>
              );
            })}
          </div>
        </div>
        {/* 桌面端竖排面板 */}
        <div className="hidden md:flex md:flex-col md:h-full">
          <SidePanel
            researchers={hiredResearchers}
            loading={overviewQuery.isLoading}
            activeId={activeId}
            onSelect={setActiveId}
          />
        </div>
      </div>

      {/* ── 右侧主区域 ── */}
      <div className="min-w-0 flex-1 space-y-3">
        {activeResearcher ? (
          <ResearcherDetailView
            researcher={activeResearcher}
            documents={selectedDocuments}
            docsLoading={overviewQuery.isLoading}
          />
        ) : (
          <>
            <ResearcherCardsSection
              researchers={hiredResearchers}
              loading={overviewQuery.isLoading}
              onSelect={setActiveId}
            />
            <HotDocumentsSection documents={hotDocuments} loading={overviewQuery.isLoading} />
            <RankingSection
              rankings={publicRankings}
              loading={overviewQuery.isLoading}
              sortBy={sortBy}
              onSortChange={setSortBy}
            />
          </>
        )}
      </div>
    </div>
  );
}
