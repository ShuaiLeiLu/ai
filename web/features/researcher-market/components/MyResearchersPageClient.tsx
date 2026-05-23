/**
 * 我的研究员页面
 *
 * 视觉骨架：
 *   ① SectionHeading —— 标题 + 概览 + 右侧创建按钮
 *   ② 研究员卡片 3 列网格（顶部 3px 色带 / 流派色头像 / 性能数字 / 技能 chip / footer）
 *   ③ 末尾"+ 创建新研究员"虚线占位卡
 *
 * 数据流：useMineResearchers() / routes.researcherEditor 跳转保持不变。
 */
'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Empty, Spin } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

import { SectionHeading } from '@/components/ui/section-heading';
import { useMineResearchers } from '@/features/researcher-market/hooks';
import { routes } from '@/lib/constants/routes';
import type { ResearcherMineItem, ResearcherPublishStatus } from '@/types/researcher';

/** 流派 → 色带/色调 token。若无法识别，落到 brand。 */
type SchoolTone = 'brand' | 'up' | 'down' | 'gold';

const SCHOOL_TONE_BY_KEYWORD: Array<{ test: RegExp; tone: SchoolTone }> = [
  { test: /价值|长线|VALUE/i, tone: 'brand' },
  { test: /量化|QUANT/i, tone: 'gold' },
  { test: /趋势|动量|MOMENTUM|TREND/i, tone: 'up' },
  { test: /稳健|防守|对冲|DEFENSIVE|HEDGE/i, tone: 'down' }
];

function resolveSchoolTone(level: string | undefined | null): SchoolTone {
  const v = String(level ?? '');
  for (const rule of SCHOOL_TONE_BY_KEYWORD) {
    if (rule.test.test(v)) return rule.tone;
  }
  return 'brand';
}

const toneTopBorder: Record<SchoolTone, string> = {
  brand: 'border-t-brand-600',
  up: 'border-t-up-500',
  down: 'border-t-down-500',
  gold: 'border-t-gold-500'
};

const toneAvatarBg: Record<SchoolTone, string> = {
  brand: 'bg-brand-50 text-brand-700',
  up: 'bg-up-50 text-up-600',
  down: 'bg-down-50 text-down-600',
  gold: 'bg-gold-50 text-gold-600'
};

const toneTag: Record<SchoolTone, string> = {
  brand: 'bg-brand-50 text-brand-700',
  up: 'bg-up-50 text-up-600',
  down: 'bg-down-50 text-down-600',
  gold: 'bg-gold-50 text-gold-600'
};

/** 状态圆点 + 文案：根据 publish_status 决定。 */
function StatusDot({ status }: { status: ResearcherPublishStatus }) {
  const cfg: Record<ResearcherPublishStatus, { cls: string; label: string }> = {
    published: { cls: 'bg-up-500', label: '已发布' },
    unpublished: { cls: 'bg-gold-500', label: '已下架' },
    draft: { cls: 'bg-ink-200', label: '草稿' }
  };
  const item = cfg[status];
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-ink-400">
      <span className={['h-1.5 w-1.5 rounded-full', item.cls].join(' ')} />
      {item.label}
    </span>
  );
}

/** 单张研究员卡：色带 / 头像 / 名称 / 性能 / 技能 chip / footer。 */
function ResearcherCard({
  item,
  onClick
}: {
  item: ResearcherMineItem;
  onClick: () => void;
}) {
  const tone = resolveSchoolTone(item.level);
  // 数据库未提供性能/技能字段 —— 这里以占位符呈现，等接口扩展后替换。
  const skills: string[] = [];

  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'group flex flex-col rounded-2xl border border-ink-50 border-t-[3px] bg-white text-left shadow-card transition-all',
        'hover:shadow-card-lg hover:border-brand-200',
        toneTopBorder[tone]
      ].join(' ')}
    >
      {/* header */}
      <div className="flex items-start gap-3 px-5 pt-5">
        <div
          className={[
            'flex h-12 w-12 shrink-0 items-center justify-center rounded-xl serif text-[22px] font-semibold',
            toneAvatarBg[tone]
          ].join(' ')}
        >
          {item.name?.charAt(0) ?? 'R'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-[15px] font-semibold text-ink-900 group-hover:text-brand-700">
              {item.name}
            </h3>
            <StatusDot status={item.publish_status} />
          </div>
          {item.level && (
            <span
              className={[
                'mt-1 inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium',
                toneTag[tone]
              ].join(' ')}
            >
              {item.level}
            </span>
          )}
        </div>
      </div>

      {/* 描述 */}
      <p className="line-clamp-2 px-5 pt-3 text-[12.5px] leading-relaxed text-ink-500">
        {item.introduction || '暂无介绍'}
      </p>

      {/* 性能数字（3 列） */}
      <div className="mx-5 mt-4 grid grid-cols-3 gap-2 rounded-xl bg-ink-25 px-3 py-3 text-center">
        <div>
          <div className="text-[10.5px] text-ink-400">本月收益</div>
          <div className="mt-0.5 tnum text-[15px] font-semibold text-up-600">--</div>
        </div>
        <div className="border-x border-ink-50">
          <div className="text-[10.5px] text-ink-400">胜率</div>
          <div className="mt-0.5 tnum text-[15px] font-semibold text-ink-800">--</div>
        </div>
        <div>
          <div className="text-[10.5px] text-ink-400">夏普</div>
          <div className="mt-0.5 tnum text-[15px] font-semibold text-ink-800">--</div>
        </div>
      </div>

      {/* 技能 chip */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5 px-5">
        {skills.length === 0 ? (
          <span className="text-[11px] text-ink-300">未配置技能</span>
        ) : (
          <>
            {skills.slice(0, 3).map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center rounded-md bg-ink-50 px-1.5 py-0.5 text-[11px] text-ink-600"
              >
                {skill}
              </span>
            ))}
            {skills.length > 3 && (
              <span className="text-[11px] text-ink-400">+ {skills.length - 3} 技能</span>
            )}
          </>
        )}
      </div>

      {/* footer */}
      <div className="mt-4 flex items-center justify-between border-t border-ink-25 px-5 py-3 text-[11.5px] text-ink-400">
        <span className="tnum">
          更新于 {new Date(item.updated_at).toLocaleDateString('zh-CN')}
        </span>
        <span className="text-brand-600 group-hover:text-brand-700">对话 →</span>
      </div>
    </button>
  );
}

/** 占位卡：虚线 + 创建按钮。 */
function CreatePlaceholderCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[260px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-ink-100 bg-white/40 text-ink-400 transition-all hover:border-brand-300 hover:bg-brand-50/40 hover:text-brand-600"
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
        <PlusOutlined style={{ fontSize: 18 }} />
      </span>
      <span className="mt-3 text-sm font-medium">创建新研究员</span>
      <span className="mt-1 text-[11.5px] text-ink-400">为你的策略矩阵新增一位 AI 助手</span>
    </button>
  );
}

export function MyResearchersPageClient() {
  const router = useRouter();
  const { data, isLoading } = useMineResearchers();
  const isEmpty = !isLoading && (!data || data.length === 0);

  const handleCreate = () => {
    router.push(routes.researcherEditor);
  };

  const handleEdit = (id: string) => {
    router.push(`${routes.researcherEditor}?id=${id}`);
  };

  // 概览数字
  const summary = useMemo(() => {
    const items = data ?? [];
    let active = 0;
    let dormant = 0;
    for (const r of items) {
      if (r.publish_status === 'published') active += 1;
      else dormant += 1;
    }
    return { active, dormant, calls: 0 };
  }, [data]);

  return (
    <div className="space-y-4 sm:space-y-5">
      <SectionHeading
        title="我的研究员"
        subtitle={`${summary.active} 个活跃 · ${summary.dormant} 个休眠 · 当月累计调用 ${summary.calls} 次`}
        actions={
          <button
            type="button"
            onClick={handleCreate}
            className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-brand transition-colors hover:bg-brand-700"
          >
            <PlusOutlined />
            创建研究员
          </button>
        }
      />

      {isLoading && (
        <div className="flex items-center justify-center rounded-2xl border border-ink-50 bg-white py-24 shadow-card">
          <Spin size="large" />
        </div>
      )}

      {isEmpty && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-100 bg-white/60 py-20 shadow-card">
          <Empty
            description={
              <span className="text-ink-400 text-sm">
                开启你的智能投资之旅，点击下方按钮定制第一位 AI 研究员
              </span>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
          <button
            type="button"
            onClick={handleCreate}
            className="mt-6 inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-brand transition-colors hover:bg-brand-700"
          >
            <PlusOutlined />
            立即创建研究员
          </button>
        </div>
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((item) => (
            <ResearcherCard key={item.id} item={item} onClick={() => handleEdit(item.id)} />
          ))}
          <CreatePlaceholderCard onClick={handleCreate} />
        </div>
      )}
    </div>
  );
}
