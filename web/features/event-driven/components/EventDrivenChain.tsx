/** 事件驱动链：已发生事件 + 未来预期 + 核心标的 */
import { PageCard } from '@/components/ui/page-card';
import type {
  EventDrivenChain as EventDrivenChainData,
  ImpactLevel,
  RoleGroup,
} from '@/features/event-driven/types';

interface Props {
  themeName: string;
  data: EventDrivenChainData;
}

const IMPACT_BADGE: Record<ImpactLevel, { label: string; className: string }> = {
  high: { label: '高影响', className: 'bg-up-50 text-up-600 border border-up-200' },
  medium: { label: '中影响', className: 'bg-gold-50 text-gold-700 border border-gold-200' },
  low: { label: '低影响', className: 'bg-ink-25 text-ink-600 border border-ink-50' },
};

const CATEGORY_LABEL: Record<string, string> = {
  policy: '政策',
  theme: '题材',
  sentiment: '情绪',
  industry: '行业',
  company: '公司',
  macro: '宏观',
  other: '其他',
};

const ROLE_STYLE: Record<RoleGroup, { icon: string; className: string; accent: string }> = {
  sentiment_core: {
    icon: '🔥',
    className:
      'bg-gradient-to-b from-[#fdecec] to-transparent border border-[#f5d3cf]',
    accent: 'text-up-600',
  },
  logic_core: {
    icon: '🎯',
    className: 'bg-gradient-to-b from-[#e9f1ec] to-transparent border border-brand-100',
    accent: 'text-brand-600',
  },
  trend_anchor: {
    icon: '📈',
    className: 'bg-gradient-to-b from-[#fdf4d8] to-transparent border border-gold-300',
    accent: 'text-gold-600',
  },
};

export function EventDrivenChain({ themeName, data }: Props) {
  return (
    <PageCard title={`📌 事件驱动链 · ${themeName}`} accent="brand">
      {/* 已发生事件（时间轴） */}
      <div className="mb-2 text-[12px] font-bold tracking-[1px] text-brand-700">
        ▶ 已发生事件（{data.past_events.length}）
      </div>
      <div className="relative pl-5">
        {data.past_events.length === 0 ? (
          <EmptyLine label="暂无已发生事件" />
        ) : (
          <>
            <div className="absolute bottom-1.5 left-1.5 top-1.5 w-[2px] bg-brand-100" />
            {data.past_events.map((e) => (
              <div key={e.id} className="relative py-2">
                <span className="absolute -left-4 top-3.5 h-2.5 w-2.5 rounded-full bg-up-500 shadow-[0_0_0_3px_var(--up-50,#fdecec)]" />
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className={`rounded px-1.5 py-[1px] ${IMPACT_BADGE[e.impact].className}`}>
                    {IMPACT_BADGE[e.impact].label}
                  </span>
                  <span className="rounded border border-brand-100 bg-brand-50 px-1.5 py-[1px] text-brand-600">
                    {CATEGORY_LABEL[e.category] ?? e.category}
                  </span>
                  <span className="text-ink-400">{e.occurred_at}</span>
                </div>
                <div className="serif mt-1 text-[14px] font-bold text-ink-900">{e.title}</div>
                <p className="mt-1 text-[12px] leading-[1.7] text-ink-600">
                  {e.description}
                  {e.source && (
                    <>
                      {' '}
                      <span className="text-ink-400">来源：</span>
                      {e.source}
                    </>
                  )}
                </p>
              </div>
            ))}
          </>
        )}
      </div>

      {/* 未来预期 */}
      <div className="mb-2 mt-5 text-[12px] font-bold tracking-[1px] text-gold-600">
        ▶ 未来预期（{data.future_expectations.length}）
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {data.future_expectations.length === 0 ? (
          <EmptyLine label="暂无未来预期" />
        ) : (
          data.future_expectations.map((f) => {
            const isCatalyst = f.kind === 'catalyst';
            return (
              <div
                key={f.id}
                className={[
                  'rounded-[10px] border p-3',
                  isCatalyst
                    ? 'border-gold-200 bg-gold-50'
                    : 'border-[#f5d3cf] bg-up-50',
                ].join(' ')}
              >
                <div className="flex items-center gap-2 text-[11px]">
                  <span
                    className={
                      isCatalyst
                        ? 'rounded bg-gold-500 px-1.5 py-[1px] text-white'
                        : 'rounded bg-up-500 px-1.5 py-[1px] text-white'
                    }
                  >
                    {isCatalyst ? '利好催化点' : '风险提示'}
                  </span>
                  <span className="text-ink-400">{f.when}</span>
                </div>
                <div className="serif mt-1.5 text-[13.5px] font-bold text-ink-900">{f.title}</div>
                <p className="mt-1 text-[11.5px] leading-[1.7] text-ink-600">{f.description}</p>
              </div>
            );
          })
        )}
      </div>

      {/* 核心标的 */}
      <div className="mb-2 mt-5 text-[12px] font-bold tracking-[1px] text-up-600">
        ▶ 核心标的（按角色分组）
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {data.core_target_groups.length === 0 ? (
          <EmptyLine label="暂无核心标的" />
        ) : (
          data.core_target_groups.map((g) => {
            const style = ROLE_STYLE[g.role];
            return (
              <div key={g.role} className={`rounded-[10px] p-3 ${style.className}`}>
                <div className={`text-[11.5px] font-bold tracking-[1px] ${style.accent}`}>
                  {style.icon} {g.label}
                </div>
                {g.items.length === 0 ? (
                  <div className="mt-2 text-[11px] text-ink-400">暂无核心标的</div>
                ) : (
                  <div className="mt-1.5 space-y-1.5">
                    {g.items.map((it) => (
                      <div key={`${g.role}-${it.symbol}`}>
                        <div className="flex justify-between text-[13px]">
                          <b className="text-ink-900">{it.name}</b>
                          <span className="up tnum text-up-600">{it.metric}</span>
                        </div>
                        <div className="text-[11px] text-ink-400">{it.note}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </PageCard>
  );
}

function EmptyLine({ label }: { label: string }) {
  return (
    <div className="rounded-[10px] border border-dashed border-ink-50 bg-ink-25 px-3 py-5 text-center text-[12px] text-ink-400">
      {label}
    </div>
  );
}
