/**
 * 技能市场页面
 *
 * 属于"极睿实验室"子页面之一，路由：/workstation/skill-market
 * 为研究员装配专业技能 · 共 N 个模块
 *
 * 数据流：useSkills() hook 拉取后端接口，支持 installed 参数筛选
 */
'use client';

import { useMemo, useState } from 'react';
import { Input, Spin } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

import { SectionHeading } from '@/components/ui/section-heading';
import { useSkills } from '@/features/ecosystem/hooks';
import type { SkillItem } from '@/types/ecosystem';

/** 分类定义 —— icon + 主题色 */
interface Category {
  key: string;
  label: string;
  icon: string;
  /** 图标背景 token */
  tone: 'brand' | 'up' | 'down' | 'gold' | 'ink';
}

const CATEGORIES: Category[] = [
  { key: 'valuation', label: '估值', icon: '📊', tone: 'brand' },
  { key: 'technical', label: '技术', icon: '📈', tone: 'up' },
  { key: 'sentiment', label: '舆情', icon: '📰', tone: 'down' },
  { key: 'finance', label: '财报', icon: '💼', tone: 'gold' },
  { key: 'event', label: '事件', icon: '🎯', tone: 'brand' },
  { key: 'capital', label: '资金面', icon: '💰', tone: 'gold' },
  { key: 'shortterm', label: '短线', icon: '⚡', tone: 'up' },
];

const toneBg: Record<Category['tone'], string> = {
  brand: 'bg-brand-50 text-brand-600',
  up: 'bg-up-50 text-up-600',
  down: 'bg-down-50 text-down-600',
  gold: 'bg-gold-50 text-gold-600',
  ink: 'bg-ink-25 text-ink-600',
};

/** 根据 skill_id / name 派生一个稳定的分类索引（视觉用） */
function deriveCategory(skill: SkillItem): Category {
  const key = skill.skill_id || skill.name;
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) % 1_000_000;
  return CATEGORIES[hash % CATEGORIES.length];
}

/** 评分 / 热度徽章颜色 */
function deriveBadge(skill: SkillItem): { label: string; cls: string } {
  // 简单派生：installed 或 id hash 偶数 → 热门
  let hash = 0;
  for (let i = 0; i < skill.skill_id.length; i++) {
    hash = (hash * 17 + skill.skill_id.charCodeAt(i)) % 1000;
  }
  if (skill.installed || hash % 5 === 0) {
    return { label: '🔥 热门', cls: 'bg-gold-50 text-gold-600 border-gold-200' };
  }
  const rating = (4.5 + (hash % 5) / 10).toFixed(1);
  return { label: `⭐ ${rating}`, cls: 'bg-up-50 text-up-600 border-up-100' };
}

/** 派生使用统计（视觉值） */
function deriveUsage(skill: SkillItem): string {
  let hash = 0;
  for (let i = 0; i < skill.skill_id.length; i++) {
    hash = (hash * 31 + skill.skill_id.charCodeAt(i)) % 100_000;
  }
  const usage = 1200 + (hash % 8800);
  return usage.toLocaleString('zh-CN');
}

/** 单个技能卡 */
function SkillCard({ item }: { item: SkillItem }) {
  const cat = useMemo(() => deriveCategory(item), [item]);
  const badge = useMemo(() => deriveBadge(item), [item]);
  const usage = useMemo(() => deriveUsage(item), [item]);

  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-ink-50 bg-white shadow-card transition-all hover:-translate-y-0.5 hover:shadow-card-lg">
      <div className="flex flex-1 flex-col p-5">
        {/* 头部 */}
        <div className="mb-3 flex items-start gap-3">
          <div
            className={['flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-xl', toneBg[cat.tone]].join(' ')}
          >
            {cat.icon}
          </div>
          <div className="min-w-0 flex-1">
            <div className="serif truncate text-[15px] font-semibold text-ink-900">{item.name}</div>
            <div className="mt-0.5 text-[11.5px] text-ink-400">{cat.label}</div>
          </div>
          <span
            className={['shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium', badge.cls].join(' ')}
          >
            {badge.label}
          </span>
        </div>

        {/* 描述 */}
        <p className="line-clamp-2 min-h-[36px] text-[12.5px] leading-relaxed text-ink-500">
          {item.description}
        </p>
      </div>

      {/* 底部 */}
      <div className="flex items-center justify-between border-t border-ink-25 px-5 py-3">
        <span className="text-[11.5px] text-ink-400">
          {usage} 次调用
        </span>
        {item.installed ? (
          <button
            type="button"
            className="rounded-lg border border-ink-50 bg-ink-25 px-3 py-1.5 text-[12px] font-medium text-ink-600"
          >
            ✓ 已启用
          </button>
        ) : (
          <button
            type="button"
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-[12px] font-medium text-white shadow-brand hover:bg-brand-700"
          >
            + 装配
          </button>
        )}
      </div>
    </div>
  );
}

/** 技能市场主组件 */
export function SkillMarketPageClient() {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  // 保留 installed 筛选状态（供 hook 调用）
  const [installedFilter] = useState<boolean | undefined>(undefined);

  const { data, isLoading } = useSkills(installedFilter);

  const filtered = useMemo(() => {
    let list = data ?? [];
    if (search) {
      const kw = search.toLowerCase();
      list = list.filter(
        (it) =>
          it.name.toLowerCase().includes(kw) || it.description.toLowerCase().includes(kw),
      );
    }
    if (activeCategory !== 'all') {
      list = list.filter((it) => deriveCategory(it).key === activeCategory);
    }
    return list;
  }, [data, search, activeCategory]);

  const total = data?.length ?? 0;

  return (
    <div className="space-y-5">
      <SectionHeading
        title="技能市场"
        subtitle={`为研究员装配专业技能 · 共 ${total} 个模块`}
        actions={
          <Input
            prefix={<SearchOutlined className="text-ink-300" />}
            placeholder="搜索技能…"
            className="w-full sm:!w-56"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
        }
      />

      {/* 分类筛选 chip 行 */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setActiveCategory('all')}
          className={[
            'rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
            activeCategory === 'all'
              ? 'bg-brand-600 text-white shadow-brand'
              : 'border border-ink-50 bg-white text-ink-600 hover:border-brand-600 hover:text-brand-600',
          ].join(' ')}
        >
          全部
        </button>
        {CATEGORIES.map((cat) => {
          const active = activeCategory === cat.key;
          return (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActiveCategory(cat.key)}
              className={[
                'flex items-center gap-1 rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
                active
                  ? 'bg-brand-600 text-white shadow-brand'
                  : 'border border-ink-50 bg-white text-ink-600 hover:border-brand-600 hover:text-brand-600',
              ].join(' ')}
            >
              <span aria-hidden>{cat.icon}</span>
              <span>{cat.label}</span>
            </button>
          );
        })}
      </div>

      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((it) => (
            <SkillCard key={it.skill_id} item={it} />
          ))}
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-ink-50 bg-white py-24 text-center text-ink-400">
          暂无匹配的技能模块
        </div>
      )}
    </div>
  );
}
