/**
 * AI 早间研判焦点卡 ——「重点位置」深绿底焦点卡
 *
 * 设计目标（对照设计稿）：
 *   - 松烟墨深绿渐变背景，金色装饰光晕
 *   - 思源宋体大字摘要叙事，关键词用金色 mark 高亮
 *   - 底部标签 chip 阵列展示驱动板块
 *
 * 数据流：useAiDigestQuery → 后端 /preopen/ai-digest
 */
'use client';

import { Alert, Button, Skeleton } from 'antd';
import { useState } from 'react';

import { PageCard } from '@/components/ui/page-card';
import { useAiDigestQuery } from '@/features/preopen/hooks';

/** 情绪 → 标签 */
const sentimentMeta: Record<string, { label: string; cls: string }> = {
  bullish: { label: '偏多', cls: 'bg-up-500/15 text-up-500 border-up-500/30' },
  bearish: { label: '偏空', cls: 'bg-down-500/15 text-down-500 border-down-500/30' },
  neutral: { label: '中性', cls: 'bg-white/10 text-ink-0/80 border-white/15' },
};

/** 从全文挑出潜在关键短语高亮（板块名 / 资金 / 数据词） */
const HIGHLIGHT_KEYWORDS = [
  '半导体', 'AI算力', 'AI 算力', '机器人', '科创50', '创业板', '北向资金',
  '人工智能', '消费', '新能源', '医药', '军工', '券商', '银行', '地产',
  '低空经济', '智能驾驶', '锂电', '光伏', '储能',
];

function highlightText(text: string): React.ReactNode {
  if (!text) return null;
  // 构造一个正则，匹配任意命中关键词；保留分隔符以便逐段渲染
  const pattern = new RegExp(`(${HIGHLIGHT_KEYWORDS.join('|')})`, 'g');
  const parts = text.split(pattern);
  return parts.map((seg, i) =>
    HIGHLIGHT_KEYWORDS.includes(seg) ? (
      <mark
        key={i}
        className="rounded-[3px] bg-gold-500/20 px-1 text-gold-300"
        style={{ background: 'rgba(200,154,58,.22)' }}
      >
        {seg}
      </mark>
    ) : (
      <span key={i}>{seg}</span>
    ),
  );
}

/** 无数据/未登录时的占位演示文案（与设计稿一致） */
const MOCK_NARRATIVE =
  '隔夜美股科技股领涨，纳指收涨 1.4%。结合北向资金连续 3 日净流入与科创50成分股突破关键阻力位，建议关注半导体设备、AI算力 板块开盘竞价表现。需警惕地产链情绪修复后的获利回吐压力。';
const MOCK_TAGS = ['半导体', 'AI算力', '北向资金', '科创50'];

export function AiDigestCard() {
  const [requested, setRequested] = useState(false);
  const { data, isLoading, isFetching, error, refetch } = useAiDigestQuery(requested);
  const meta = sentimentMeta[data?.sentiment ?? 'neutral'];
  const loading = isLoading || isFetching;

  const handleRequestDigest = () => {
    if (requested) {
      void refetch();
      return;
    }
    setRequested(true);
  };

  // 把后端可能给出的字段拼成一段叙事文本；无数据时用占位演示文案
  const narrative: string = data
    ? [data.headline, ...(data.key_points ?? []).slice(0, 2)].filter(Boolean).join(' ')
    : MOCK_NARRATIVE;

  // 标签 chip：把机会方向 + 新闻驱动合并去重，最多 6 个；无数据时用占位
  const chipTags = data
    ? Array.from(
        new Set([
          ...(data?.opportunity_sectors ?? []),
          ...(data?.news_drivers ?? []),
        ]),
      ).slice(0, 6)
    : MOCK_TAGS;

  // 元信息：模型/耗时/数据源（无数据时也展示占位）
  const isPreview = !data && !loading;
  const metaLine = data
    ? `研判官 v3 · ${new Date(data.generated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} 更新`
    : '研判官 v3.2 · 待生成 · 引用 21 个数据源';

  return (
    <PageCard
      tone="dark"
      accent="gold"
      title="AI 早间研判"
      extra={
        <Button
          size="small"
          ghost
          className="!border-gold-500/40 !text-gold-300 hover:!border-gold-300 hover:!text-gold-200"
          loading={loading}
          onClick={handleRequestDigest}
        >
          {data ? '重新生成' : 'AI 解读'}
        </Button>
      }
      className="relative overflow-hidden"
    >
      {/* 装饰光晕 */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(200,154,58,.16), transparent 65%)' }}
      />

      <div className="relative">
        {loading && (
          <div className="opacity-80">
            <Skeleton active paragraph={{ rows: 4 }} />
          </div>
        )}

        {error && !loading && (
          <Alert message="AI 解读生成失败" description={error.message} type="error" showIcon />
        )}

        {!loading && !error && (
          <>
            {/* 元信息条 */}
            <div className="mb-3 flex items-center gap-2 text-[11px] text-ink-0/55">
              <span
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10.5px] font-semibold tracking-wide ${meta.cls}`}
              >
                {data ? meta.label : '示例'}
              </span>
              <span>·</span>
              <span>{metaLine}</span>
            </div>

            {/* 大字摘要叙事 */}
            <p className={`serif text-[15.5px] leading-[1.85] sm:text-[16px] ${isPreview ? 'text-ink-0/60' : 'text-ink-0'}`}>
              {highlightText(narrative)}
            </p>

            {/* 标签 chip */}
            {chipTags.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {chipTags.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-0.5 text-[11px] text-ink-0/80"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}

            {/* 次级要点（机会/风险） */}
            {data && (data.opportunity_sectors?.length || data.risk_sectors?.length) ? (
              <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {data.opportunity_sectors?.length ? (
                  <SubList title="机会方向" items={data.opportunity_sectors} tone="up" />
                ) : null}
                {data.risk_sectors?.length ? (
                  <SubList title="风险方向" items={data.risk_sectors} tone="down" />
                ) : null}
              </div>
            ) : null}

            {isPreview && (
              <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-[11.5px] text-ink-0/55">
                以上为示例预览 · 点击右上「AI 解读」基于今日实时数据生成研判
              </div>
            )}
          </>
        )}
      </div>
    </PageCard>
  );
}

function SubList({ title, items, tone }: { title: string; items: string[]; tone: 'up' | 'down' }) {
  const dotCls = tone === 'up' ? 'bg-up-400' : 'bg-down-400';
  const titleCls = tone === 'up' ? 'text-up-400' : 'text-down-400';
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.04] px-3 py-2.5">
      <div className={`mb-1.5 text-[10.5px] font-semibold tracking-[1.5px] ${titleCls}`}>
        {title}
      </div>
      <ul className="space-y-1 pl-0">
        {items.slice(0, 3).map((it, i) => (
          <li key={i} className="flex items-start gap-1.5 text-[12.5px] leading-5 text-ink-0/85">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dotCls}`} />
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
