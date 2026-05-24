'use client';

import { useEffect, useMemo, useState } from 'react';
import { Alert, Empty, Modal, Skeleton, message } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import { routes } from '@/lib/constants/routes';
import { EventDrivenChain } from '@/features/event-driven/components/EventDrivenChain';
import { ExpectationRadar } from '@/features/event-driven/components/ExpectationRadar';
import { MarketStory } from '@/features/event-driven/components/MarketStory';
import { ThemeListSidebar } from '@/features/event-driven/components/ThemeListSidebar';
import { TheySayBoard } from '@/features/event-driven/components/TheySayBoard';
import {
  useAccessStatus,
  useThemeDetail,
  useThemes,
  useTheySay,
  useUnlockToday,
} from '@/features/event-driven/hooks';
import type {
  AnchorRecommendItem,
  ConsensusBreakdown,
  HiddenLogicItem,
  OpinionStance,
  ResearcherOpinion,
  Scenario,
  ThemeStatus,
} from '@/features/event-driven/types';

const STATUS_LABEL: Record<ThemeStatus, string> = {
  today_hot: '今日火爆',
  yesterday_hot: '昨日火爆',
  waiting: '暂避锋芒',
  lurking: '潜伏中',
};

const STANCE_STYLE: Record<OpinionStance, { label: string; className: string }> = {
  bullish: { label: '看涨', className: 'bg-up-50 text-up-600' },
  bearish: { label: '看跌', className: 'bg-down-50 text-down-600' },
  neutral: { label: '中性', className: 'bg-ink-25 text-ink-600' },
  watch: { label: '观望', className: 'bg-gold-50 text-gold-700' },
};

function formatMinute(value?: string) {
  if (!value) return undefined;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function LoadingCard({ rows = 6 }: { rows?: number }) {
  return (
    <PageCard>
      <Skeleton active paragraph={{ rows }} />
    </PageCard>
  );
}

function EmptyCard({ title, description }: { title: string; description: string }) {
  return (
    <PageCard title={title}>
      <div className="py-10">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={description} />
      </div>
    </PageCard>
  );
}

function MetricStrip({
  status,
  limitUpCount,
  researcherCount,
  consensus,
}: {
  status: ThemeStatus;
  limitUpCount: number;
  researcherCount: number;
  consensus: string;
}) {
  const items = [
    { label: '题材状态', value: STATUS_LABEL[status] },
    { label: '涨停数量', value: `${limitUpCount} 只` },
    { label: '观点覆盖', value: researcherCount > 0 ? `${researcherCount} 位` : '未接入' },
    { label: '共识状态', value: consensus },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-[10px] border border-ink-50 bg-white px-4 py-3 shadow-card">
          <div className="text-[11px] tracking-[1.5px] text-ink-400">{item.label}</div>
          <div className="serif mt-1 truncate text-[16px] font-bold text-ink-900">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

function HiddenLogicPanel({ items }: { items: HiddenLogicItem[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, 2);

  return (
    <PageCard
      title="暗线逻辑"
      subtitle="由涨停池行业映射派生"
      accent="brand"
      extra={
        items.length > 2 ? (
          <button type="button" onClick={() => setExpanded((v) => !v)} className="text-brand-600">
            {expanded ? '收起' : `展开 ${items.length - 2} 条`}
          </button>
        ) : null
      }
    >
      {visible.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-ink-400">暂无暗线逻辑</div>
      ) : (
        <div className="space-y-3">
          {visible.map((item) => (
            <div key={item.id} className="rounded-[10px] border border-brand-100 bg-brand-50/70 p-3">
              <div className="serif text-[14px] font-bold text-brand-700">{item.title}</div>
              <p className="mt-1 text-[12px] leading-[1.7] text-ink-600">{item.description}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.tags.map((tag) => (
                  <span key={tag} className="rounded bg-white px-2 py-0.5 text-[11px] text-brand-700">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageCard>
  );
}

function AnchorPanel({ items }: { items: AnchorRecommendItem[] }) {
  const horizonLabel: Record<AnchorRecommendItem['horizon'], string> = {
    today: '今天',
    this_week: '本周',
  };
  return (
    <PageCard title="主心骨推荐" subtitle="最具爆发潜力的方向" accent="gold">
      {items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-ink-400">暂无主心骨推荐</div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={`${item.horizon}-${item.title}`} className="rounded-[10px] border border-gold-200 bg-gold-50 p-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="rounded bg-gold-500 px-1.5 py-[1px] font-semibold text-white">
                  {horizonLabel[item.horizon]}
                </span>
                <span className="text-gold-700">{item.label}</span>
              </div>
              <div className="serif mt-1.5 text-[14px] font-bold text-ink-900">{item.title}</div>
              <p className="mt-1 text-[12px] leading-[1.7] text-ink-600">{item.description}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.related_symbols.map((symbol) => (
                  <span key={symbol} className="rounded bg-white px-2 py-0.5 text-[11px] text-gold-700">
                    {symbol}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageCard>
  );
}

function ScenarioPanel({ items }: { items: Scenario[] }) {
  return (
    <PageCard title="情景观察" subtitle="仅展示已接入的真实推演数据" accent="up">
      {items.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-ink-400">暂无推演场景</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {items.map((item) => (
            <div key={item.kind} className="rounded-[10px] border border-ink-50 bg-ink-25 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="rounded bg-white px-2 py-0.5 text-[11px] font-semibold text-ink-600">
                  {item.label}
                </span>
                <span className="tnum text-[12px] font-bold text-up-600">
                  {(item.probability * 100).toFixed(0)}%
                </span>
              </div>
              <div className="serif mt-2 text-[14px] font-bold text-ink-900">{item.title}</div>
              <p className="mt-1 text-[12px] leading-[1.7] text-ink-600">{item.strategy}</p>
              <div className="mt-2 rounded bg-white px-2 py-1.5 text-[11.5px] text-ink-500">
                <b className="text-ink-700">关键观察：</b>
                {item.key_observation}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageCard>
  );
}

function OpinionPanel({ items }: { items: ResearcherOpinion[] }) {
  const [expanded, setExpanded] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const visible = expanded ? items : items.slice(0, 4);
  const groupedOpinions = useMemo(() => {
    const groups = new Map<
      string,
      {
        researcher_id: string;
        researcher_name: string;
        avatar_initial: string;
        avatar_color: string;
        opinions: ResearcherOpinion[];
      }
    >();

    items.forEach((item) => {
      const current =
        groups.get(item.researcher_id) ??
        {
          researcher_id: item.researcher_id,
          researcher_name: item.researcher_name,
          avatar_initial: item.avatar_initial,
          avatar_color: item.avatar_color,
          opinions: [],
        };
      current.opinions.push(item);
      groups.set(item.researcher_id, current);
    });

    return Array.from(groups.values());
  }, [items]);

  return (
    <>
      <PageCard
        title="观点汇集"
        subtitle={`真实观点源 · ${groupedOpinions.length} 位 · ${items.length} 条`}
        accent="brand"
        extra={
          items.length > 0 ? (
            <button type="button" onClick={() => setDetailOpen(true)} className="text-brand-600">
              聚合详情
            </button>
          ) : null
        }
      >
        {visible.length === 0 ? (
          <div className="py-6 text-center text-[12px] text-ink-400">暂无研究员观点</div>
        ) : (
          <div className="divide-y divide-dashed divide-ink-50">
            {visible.map((item) => (
              <OpinionRow key={item.id} item={item} onOpen={() => setDetailOpen(true)} />
            ))}
            {items.length > 4 ? (
              <div className="px-2 py-3 text-center">
                <button
                  type="button"
                  onClick={() => setExpanded((value) => !value)}
                  className="text-[12px] font-semibold text-brand-600"
                >
                  {expanded ? '收起观点' : `展开查看全部 ${items.length} 条观点 ›`}
                </button>
              </div>
            ) : null}
          </div>
        )}
      </PageCard>

      <Modal
        open={detailOpen}
        title="研究员观点详情"
        footer={null}
        onCancel={() => setDetailOpen(false)}
        width={760}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-[10px] border border-ink-50 bg-ink-25 px-4 py-3">
              <div className="text-[11px] text-ink-400">观点源覆盖</div>
              <div className="serif mt-1 text-[20px] font-bold text-ink-900">{groupedOpinions.length} 位</div>
            </div>
            <div className="rounded-[10px] border border-ink-50 bg-ink-25 px-4 py-3">
              <div className="text-[11px] text-ink-400">观点总数</div>
              <div className="serif mt-1 text-[20px] font-bold text-ink-900">{items.length} 条</div>
            </div>
          </div>

          {groupedOpinions.length === 0 ? (
            <div className="py-8 text-center text-[12px] text-ink-400">暂无研究员观点</div>
          ) : (
            <div className="max-h-[62vh] space-y-3 overflow-y-auto pr-1">
              {groupedOpinions.map((group) => (
                <section key={group.researcher_id} className="rounded-[10px] border border-ink-50 bg-white">
                  <div className="flex items-center gap-2 border-b border-ink-50 px-3 py-2.5">
                    <OpinionAvatar initial={group.avatar_initial} color={group.avatar_color} size="md" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-semibold text-ink-900">{group.researcher_name}</div>
                      <div className="text-[11px] text-ink-400">{group.opinions.length} 条观点</div>
                    </div>
                  </div>
                  <div className="divide-y divide-dashed divide-ink-50 px-1">
                    {group.opinions.map((item) => (
                      <OpinionRow key={item.id} item={item} compact />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </>
  );
}

function OpinionAvatar({
  initial,
  color,
  size = 'sm',
}: {
  initial: string;
  color: string;
  size?: 'sm' | 'md';
}) {
  const colorClass: Record<string, string> = {
    up: 'bg-gradient-to-br from-up-500 to-up-700',
    down: 'bg-down-500',
    brand: 'bg-gradient-to-br from-brand-500 to-brand-700',
    gold: 'bg-gold-500',
  };
  const sizeClass = size === 'md' ? 'h-8 w-8 text-[12px]' : 'h-[26px] w-[26px] text-[11px]';

  return (
    <span
      className={`grid shrink-0 place-items-center rounded-full font-bold text-white ${sizeClass} ${
        colorClass[color] ?? 'bg-brand-600'
      }`}
    >
      {initial}
    </span>
  );
}

function OpinionRow({
  item,
  compact = false,
  onOpen,
}: {
  item: ResearcherOpinion;
  compact?: boolean;
  onOpen?: () => void;
}) {
  const style = STANCE_STYLE[item.stance];
  const body = (
    <div className={`${compact ? 'px-2 py-3' : 'px-2 py-3'}`}>
      <div className="flex items-center gap-2">
        <OpinionAvatar initial={item.avatar_initial} color={item.avatar_color} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[12.5px] font-semibold text-ink-900">{item.researcher_name}</div>
          <div className="text-[11px] text-ink-400">
            关联：<span className="rounded bg-brand-50 px-1.5 py-0.5 font-semibold text-brand-700">{item.related_symbol ?? '题材观点'}</span>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${style.className}`}>{style.label}</span>
          <div className="mt-0.5 text-[11px] text-ink-500">
            置信度 <b className={item.stance === 'bearish' ? 'text-down-600' : 'text-up-600'}>{item.confidence_pct}%</b>
          </div>
        </div>
      </div>
      <p className="mt-1.5 text-left text-[12px] leading-[1.7] text-ink-600">{item.content}</p>
    </div>
  );

  if (!onOpen) return body;

  return (
    <button type="button" onClick={onOpen} className="block w-full text-left transition hover:bg-ink-25">
      {body}
    </button>
  );
}

function ConsensusPanel({ consensus }: { consensus: ConsensusBreakdown }) {
  const total = consensus.bullish + consensus.neutral + consensus.bearish + consensus.watch;
  const rows = [
    { key: 'bullish', label: '看涨', count: consensus.bullish, textClass: 'text-up-600', trackClass: 'bg-up-50', barClass: 'bg-up-500' },
    { key: 'neutral', label: '中性', count: consensus.neutral, textClass: 'text-ink-600', trackClass: 'bg-ink-25', barClass: 'bg-ink-400' },
    { key: 'bearish', label: '看跌', count: consensus.bearish, textClass: 'text-down-600', trackClass: 'bg-down-50', barClass: 'bg-down-500' },
    { key: 'watch', label: '观望', count: consensus.watch, textClass: 'text-gold-700', trackClass: 'bg-gold-50', barClass: 'bg-gold-500' },
  ].filter((row) => row.count > 0 || row.key !== 'watch');
  const badge =
    consensus.summary.includes('强共识')
      ? { label: '强共识', className: 'bg-up-50 text-up-600' }
      : consensus.summary.includes('中等共识')
        ? { label: '中等共识', className: 'bg-gold-50 text-gold-700' }
        : { label: '有分歧', className: 'bg-down-50 text-down-600' };
  const note = consensus.summary.includes('·') ? consensus.summary.split('·').slice(1).join('·').trim() : consensus.summary;

  return (
    <PageCard title="共识分布" subtitle={`${total} 条研究员判断`} accent="brand">
      {total === 0 ? (
        <div className="py-6 text-center text-[12px] text-ink-400">暂无共识统计</div>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const pct = total > 0 ? (row.count / total) * 100 : 0;
            const pctText = Number.isInteger(pct) ? pct.toFixed(0) : pct.toFixed(1);
            return (
              <div key={row.key}>
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-ink-700">
                    {row.label} {row.count}
                  </span>
                  <span className={`tnum font-semibold ${row.textClass}`}>{pctText}%</span>
                </div>
                <div className={`mt-1 h-2 overflow-hidden rounded-full ${row.trackClass}`}>
                  <div className={`h-full rounded-full ${row.barClass}`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}

          <div className="flex flex-wrap items-center gap-2 border-t border-dashed border-ink-50 pt-3">
            <span className={`rounded px-2.5 py-1 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span>
            <span className="text-[11px] text-ink-400">{note}</span>
          </div>
        </div>
      )}
    </PageCard>
  );
}

function UnlockBanner({
  vip,
  unlockedToday,
  balance,
  cost,
  onUnlock,
  loading,
}: {
  vip: boolean;
  unlockedToday: boolean;
  balance: number;
  cost: number;
  onUnlock: () => void;
  loading: boolean;
}) {
  if (vip || unlockedToday) {
    return (
      <div className="rounded-[10px] border border-brand-100 bg-brand-50 px-4 py-3 text-[12px] text-brand-700">
        已解锁今日题材掘金真实市场快照详情。
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-[10px] border border-gold-300 bg-gold-50 px-4 py-3 md:flex-row md:items-center md:justify-between">
      <div>
        <div className="serif text-[14px] font-bold text-ink-900">VIP 专属深度内容</div>
        <div className="mt-0.5 text-[12px] text-ink-500">
          当前算力余额：{balance}。可开通 VIP，或花费 <b className="text-gold-600">{cost} 算力</b> 单日解锁。
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <a
          href={routes.billing}
          className="rounded-lg bg-brand-600 px-4 py-2 text-[12px] font-semibold text-white transition hover:bg-brand-700"
        >
          开通 VIP
        </a>
        <button
          type="button"
          onClick={onUnlock}
          disabled={loading}
          className="rounded-lg border border-gold-300 bg-white px-4 py-2 text-[12px] font-semibold text-gold-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? '解锁中...' : `单日 ${cost} 算力`}
        </button>
      </div>
    </div>
  );
}

export default function EventDrivenPage() {
  const [messageApi, messageContext] = message.useMessage();
  const themesQuery = useThemes();
  const theySayQuery = useTheySay();
  const accessQuery = useAccessStatus();
  const unlockMutation = useUnlockToday();

  const [activeId, setActiveId] = useState<string>();
  const themes = useMemo(() => themesQuery.data ?? [], [themesQuery.data]);
  const selectedId = activeId ?? themes[0]?.id;
  const detailQuery = useThemeDetail(selectedId);
  const detail = detailQuery.data;

  useEffect(() => {
    if (!activeId && themes[0]?.id) setActiveId(themes[0].id);
  }, [activeId, themes]);

  const generatedAt = useMemo(
    () => formatMinute(theySayQuery.data?.generated_at ?? detail?.they_say.generated_at),
    [detail?.they_say.generated_at, theySayQuery.data?.generated_at],
  );

  const handleUnlock = () => {
    const access = accessQuery.data;
    const cost = access?.unlock_cost ?? 200;
    const balance = access?.battery_balance ?? 0;
    if (balance < cost) {
      Modal.warning({
        title: '算力不足',
        content: (
          <div className="space-y-3 text-sm leading-relaxed text-ink-500">
            <div>
              单日解锁需要 <b className="text-gold-600">{cost}</b> 算力，当前余额仅{' '}
              <b className="text-up-600">{balance}</b> 算力。
            </div>
            <Alert
              type="warning"
              showIcon
              message="可通过签到、充值或升级 VIP 获取更多算力。"
            />
          </div>
        ),
        okText: '知道了',
      });
      return;
    }

    Modal.confirm({
      title: '确认解锁今日题材掘金',
      content: (
        <div className="space-y-2 text-sm leading-relaxed text-ink-500">
          <div>使用算力单日解锁后，今日内可自由查看本题材真实市场快照详情。</div>
          <div className="space-y-1 rounded-lg border border-dashed border-gold-300 bg-gold-50 px-3 py-2 text-xs">
            <div className="flex justify-between">
              <span className="text-ink-400">解锁费用</span>
              <b className="serif text-[15px] text-gold-700">{cost} 算力</b>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-400">当前余额</span>
              <span className="tnum text-ink-700">{balance} 算力</span>
            </div>
            <div className="border-t border-gold-200 pt-1" />
            <div className="flex justify-between">
              <span className="font-semibold text-ink-700">解锁后余额</span>
              <b className="tnum text-brand-700">{Math.max(0, balance - cost)} 算力</b>
            </div>
          </div>
          <Alert type="info" showIcon message="单日有效，今日内可自由查看本题材真实市场快照详情。" />
        </div>
      ),
      okText: '确认解锁',
      cancelText: '暂不解锁',
      okButtonProps: { loading: unlockMutation.isPending },
      onOk: async () => {
        try {
          await unlockMutation.mutateAsync();
          messageApi.success('解锁成功');
        } catch (error) {
          messageApi.error(error instanceof Error ? error.message : '解锁失败');
        }
      },
    });
  };

  return (
    <div className="mx-auto w-full max-w-[1920px]">
      {messageContext}
      <SectionHeading
        title="题材掘金"
        subtitle="真实市场快照 · 题材分类 · 涨停统计 · 事件驱动链"
        actions={
          <span className="flex items-center gap-1.5">
            <span className="pulse-dot" />
            <span>{generatedAt ? `${generatedAt} 生成` : '数据同步中'}</span>
          </span>
        }
      />

      {theySayQuery.isLoading && <LoadingCard rows={4} />}
      {!theySayQuery.isLoading && theySayQuery.data && <TheySayBoard data={theySayQuery.data} />}
      {!theySayQuery.isLoading && theySayQuery.isError && (
        <EmptyCard title="市场快照概览" description="真实市场快照加载异常，请稍后重试" />
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="xl:sticky xl:top-[84px] xl:h-[calc(100vh-108px)]">
          {themesQuery.isLoading ? (
            <LoadingCard rows={12} />
          ) : themesQuery.isError ? (
            <EmptyCard title="题材列表" description="加载题材数据失败" />
          ) : themes.length === 0 ? (
            <EmptyCard title="题材列表" description="当前未获取到真实市场题材数据" />
          ) : (
            <ThemeListSidebar themes={themes} activeId={selectedId} onSelect={setActiveId} generatedAt={generatedAt} />
          )}
        </div>

        <div className="min-w-0 space-y-4">
          {detailQuery.isLoading && <LoadingCard rows={14} />}
          {!detailQuery.isLoading && detailQuery.isError && <EmptyCard title="题材详情" description="加载数据失败" />}
          {!detailQuery.isLoading && !detail && !detailQuery.isError && (
            <EmptyCard title="题材详情" description="从左侧选择一个题材查看完整事件驱动链分析" />
          )}

          {detail && (
            <>
              <div className="rounded-2xl border border-ink-50 bg-white p-5 shadow-card">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <div className="text-[11px] font-semibold tracking-[2px] text-brand-600">THEME MINING</div>
                    <h2 className="serif mt-1 text-[28px] font-bold text-ink-900">{detail.name}</h2>
                    <p className="mt-1 max-w-3xl text-[12.5px] leading-[1.7] text-ink-500">
                      汇总涨停池、行业板块与实时快讯，形成可追踪的真实市场题材链。
                    </p>
                  </div>
                  {accessQuery.data && (
                    <div className="rounded-[10px] bg-ink-25 px-3 py-2 text-[12px] text-ink-500">
                      算力余额 <b className="tnum text-ink-900">{accessQuery.data.battery_balance}</b>
                    </div>
                  )}
                </div>
                <div className="mt-4">
                  <MetricStrip
                    status={detail.status}
                    limitUpCount={detail.limit_up_count}
                    researcherCount={detail.researcher_count}
                    consensus={detail.consensus.summary}
                  />
                </div>
                {accessQuery.data && (
                  <div className="mt-4">
                    <UnlockBanner
                      vip={accessQuery.data.vip}
                      unlockedToday={accessQuery.data.unlocked_today}
                      balance={accessQuery.data.battery_balance}
                      cost={accessQuery.data.unlock_cost}
                      loading={unlockMutation.isPending}
                      onUnlock={handleUnlock}
                    />
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
                <ExpectationRadar items={detail.expectation_gaps} />
                <MarketStory data={detail.market_story} />
              </div>

              <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1fr_1fr]">
                <HiddenLogicPanel items={detail.hidden_logic} />
                <AnchorPanel items={detail.anchor_recommendations} />
              </div>

              <ScenarioPanel items={detail.scenarios} />
              <OpinionPanel items={detail.opinions} />
              <ConsensusPanel consensus={detail.consensus} />
              <EventDrivenChain themeName={detail.name} data={detail.event_chain} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
