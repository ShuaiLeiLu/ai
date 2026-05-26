/**
 * AI 早间研判焦点卡 ——「重点位置」深绿底焦点卡
 *
 * 设计目标（对照设计稿）：
 *   - 松烟墨深绿渐变背景，金色装饰光晕
 *   - 思源宋体大字摘要叙事，关键词用金色 mark 高亮
 *   - 底部标签 chip 阵列展示驱动板块
 *
 * 数据流：useAiDigestQuery → 后端 /preopen/ai-digest 读取已生成结果
 */
'use client';

import { Alert, Button, Modal, Skeleton, message } from 'antd';
import { useState } from 'react';

import { PageCard } from '@/components/ui/page-card';
import { useAiDigestQuery } from '@/features/preopen/hooks';
import { HttpError } from '@/lib/request/http-client';
import type { AiDigest } from '@/types/preopen';

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

export function AiDigestCard() {
  const [messageApi, messageContext] = message.useMessage();
  const [reportOpen, setReportOpen] = useState(false);
  const { data, isLoading, isFetching, error, refetch } = useAiDigestQuery();
  const meta = sentimentMeta[data?.sentiment ?? 'neutral'];
  const loading = isLoading || isFetching;
  const isMissingTodayDigest = error instanceof HttpError && error.status === 404;
  const displayError = error && !isMissingTodayDigest ? error : null;

  const handleRequestDigest = () => {
    void refetch();
  };

  // 把后端可能给出的字段拼成一段叙事文本。
  const narrative: string = data ? [data.headline, ...(data.key_points ?? []).slice(0, 2)].filter(Boolean).join(' ') : '';

  // 标签 chip：把机会方向 + 新闻驱动合并去重，最多 6 个。
  const chipTags = data
    ? Array.from(
        new Set([
          ...(data?.opportunity_sectors ?? []),
          ...(data?.news_drivers ?? []),
        ]),
      ).slice(0, 6)
    : [];

  // 元信息：模型/耗时/数据源。
  const metaLine = data
    ? `研判官 v3 · ${new Date(data.generated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} 更新`
    : '研判官 v3 · 等待今日调度生成';

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
          刷新
        </Button>
      }
      className="relative overflow-hidden"
    >
      {messageContext}
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

        {displayError && !loading && (
          <Alert message="AI 解读加载失败" description={displayError.message} type="error" showIcon />
        )}

        {!loading && !displayError && (
          <>
            {/* 元信息条 */}
            <div className="mb-3 flex items-center gap-2 text-[11px] text-ink-0/55">
              <span
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10.5px] font-semibold tracking-wide ${meta.cls}`}
              >
                {data ? meta.label : '今日'}
              </span>
              <span>·</span>
              <span>{metaLine}</span>
            </div>

            {data ? (
              <>
                {/* 大字摘要叙事 */}
                <p className="serif text-[15.5px] leading-[1.85] text-ink-0 sm:text-[16px]">
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
                {data.opportunity_sectors?.length || data.risk_sectors?.length ? (
                  <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {data.opportunity_sectors?.length ? (
                      <SubList title="机会方向" items={data.opportunity_sectors} tone="up" />
                    ) : null}
                    {data.risk_sectors?.length ? (
                      <SubList title="风险方向" items={data.risk_sectors} tone="down" />
                    ) : null}
                  </div>
                ) : null}

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <Button
                    size="small"
                    type="primary"
                    ghost
                    className="!border-gold-500/50 !text-gold-300"
                    onClick={() => setReportOpen(true)}
                  >
                    查看详细报告
                  </Button>
                  <Button
                    size="small"
                    type="text"
                    className="!text-ink-0/60 hover:!text-ink-0"
                    onClick={() => {
                      void navigator.clipboard?.writeText(
                        [data.report_title ?? '盘前热讯 AI 解读报告', data.headline, ...(data.key_points ?? [])].join('\n'),
                      );
                      messageApi.success('报告摘要已复制');
                    }}
                  >
                    复制摘要
                  </Button>
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-[12px] text-ink-0/60">
                今日摘要暂未生成，请稍后刷新。
              </div>
            )}
          </>
        )}
      </div>
      <AiDigestReportModal data={data} open={reportOpen} onClose={() => setReportOpen(false)} />
    </PageCard>
  );
}

function buildReportText(data: AiDigest): string {
  const sections = data.report_sections ?? [];
  const generatedAt = new Date(data.generated_at).toLocaleString('zh-CN', { hour12: false });

  return [
    data.report_title ?? '盘前热讯 AI 解读报告',
    `报告时间：${generatedAt}`,
    data.headline,
    ...sections.flatMap((section) => [
      '',
      section.title,
      ...(section.paragraphs ?? []),
      ...(section.bullets ?? []).map((item) => `- ${item}`),
    ]),
  ].join('\n');
}

function AiDigestReportModal({
  data,
  open,
  onClose,
}: {
  data?: AiDigest;
  open: boolean;
  onClose: () => void;
}) {
  const [messageApi, contextHolder] = message.useMessage();
  if (!data) return null;
  const sections = data.report_sections ?? [];
  const generatedAt = new Date(data.generated_at).toLocaleString('zh-CN', { hour12: false });
  const intervalStart = new Date(data.interval_start).toLocaleString('zh-CN', { hour12: false });
  const intervalEnd = new Date(data.interval_end).toLocaleString('zh-CN', { hour12: false });

  const copyReport = () => {
    void navigator.clipboard?.writeText(buildReportText(data));
    messageApi.success('报告全文已复制');
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width="min(1080px, 96vw)"
      className="preopen-digest-report"
      styles={{ body: { padding: 0 } }}
      destroyOnHidden
    >
      {contextHolder}
      <div className="bg-ink-0 px-5 py-5 sm:px-8">
        <div className="mb-6 flex flex-col gap-4 border-b border-dashed border-ink-100 pb-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="serif text-[24px] font-bold leading-tight text-ink-900">
                {data.report_title ?? '盘前热讯 AI 解读报告'}
              </h1>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-500">
              <span>报告时间：{generatedAt}</span>
              <span>数据基准：{intervalStart} → {intervalEnd}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <span className="rounded bg-up-50 px-2 py-0.5 text-[11px] text-up-600">深度</span>
              <span className="rounded bg-brand-50 px-2 py-0.5 text-[11px] text-brand-700">研判官 v3</span>
              <span className="rounded bg-ink-25 px-2 py-0.5 text-[11px] text-ink-500">AkShare + LLM</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={copyReport}>复制全文</Button>
            <Button onClick={() => messageApi.info('已收藏到研报库候选区')}>收藏</Button>
            <Button type="primary" onClick={onClose}>返回驾驶舱</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[210px_minmax(0,1fr)]">
          <aside className="hidden self-start lg:sticky lg:top-4 lg:block">
            <div className="mb-3 text-[11px] tracking-[0.2em] text-ink-400">目 录</div>
            <ul className="space-y-1 text-[12.5px] leading-6">
              {sections.map((section, index) => (
                <li key={section.title} className={index === 0 ? 'border-l-[3px] border-brand-600 pl-2 font-semibold text-brand-700' : 'pl-[11px] text-ink-500'}>
                  {section.title}
                </li>
              ))}
            </ul>
          </aside>

          <main className="pb-2">
            {sections.map((section) => (
              <section key={section.title} className="mb-7">
                <h2 className="serif border-l-4 border-brand-600 pl-3 text-[19px] font-bold text-ink-900">
                  {section.title}
                </h2>
                {section.paragraphs.map((paragraph) => (
                  <p key={paragraph} className="mt-3 text-[13.5px] leading-[1.9] text-ink-700">
                    {paragraph}
                  </p>
                ))}
                {section.bullets.length > 0 && (
                  <ul className="mt-3 space-y-2 pl-0">
                    {section.bullets.map((item, index) => (
                      <li key={`${section.title}-${index}`} className="flex gap-2 rounded-lg bg-white px-3 py-2 text-[13px] leading-relaxed text-ink-700">
                        <span className="tnum shrink-0 font-bold text-gold-600">{index + 1}</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {section.table.length > 0 && (
                  <div className="mt-3 overflow-x-auto rounded-lg border border-ink-50 bg-white">
                    <table className="min-w-full text-[12.5px]">
                      <thead className="bg-ink-25 text-ink-500">
                        <tr>
                          {Object.keys(section.table[0]).map((key) => (
                            <th key={key} className="px-3 py-2 text-left font-semibold">{key}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {section.table.map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-t border-ink-25">
                            {Object.values(row).map((value, cellIndex) => (
                              <td key={`${rowIndex}-${cellIndex}`} className="px-3 py-2 text-ink-700">{value}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            ))}

            <div className="rounded-lg bg-ink-25 px-4 py-3 text-[11.5px] leading-relaxed text-ink-500">
              免责声明：本报告由 AI 基于公开数据自动生成，仅用于观察和学习 AI 在金融领域的应用效果，不构成任何投资建议。
            </div>
          </main>
        </div>
      </div>
    </Modal>
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
