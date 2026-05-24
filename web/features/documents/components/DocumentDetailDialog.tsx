/**
 * 研报详情对话框 —— 对照设计稿 5C
 *
 * 三栏：左目录(200) / 中正文(flex-1) / 右评论区(280)
 *  - 顶部：思源宋体标题 + 关闭
 *  - 风险提示横条（金色底）
 *  - 任务进度块（浅蓝底，6 个 ✓）
 *  - markdown 正文（H1/H2/H3 带左侧 brand 强调条）
 *  - 评论区：列表 + ♥ 计数 + 底部输入框 + @ 召唤研究员
 *
 * 同时支持「关键弹窗 3 · 文档工作流节点」状态：
 * 当 document.status === 'generating' 时，正文位置渲染工作流节点卡片。
 *
 * 触发场景：研报库列表卡片点击 / AI 摘要面板「阅读全文」/ 研究员主页研报卡片点击。
 */
'use client';

import { useMemo, useState } from 'react';
import { Avatar, Empty, Modal, Skeleton, Tag, message } from 'antd';
import dayjs from 'dayjs';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { useCommunityMentionConfig } from '@/features/community/hooks';
import { useCreateDocumentComment, useDocumentComments, useDocumentDetail } from '@/features/documents/hooks';
import type { CommunityMentionResearcher } from '@/types/community';
import type { DocumentComment, DocumentDetail, DocumentWorkflowNode } from '@/types/documents';

/** ───────── Props ───────── */
export interface DocumentDetailDialogProps {
  /** 文档 ID；为空时不会发起请求 */
  documentId?: string;
  open: boolean;
  onClose: () => void;
  /**
   * 强制覆盖状态（可选）。
   * 当 document 接口未来扩展 status 字段时，这里也可以直接传入。
   * 'generating' 表示研报正在生成，正文位置渲染工作流节点卡片。
   */
  status?: 'generating' | 'ready';
}

/** ───────── 工作流任务（5C 顶部任务进度） ───────── */
const PROGRESS_TASKS = [
  '市场数据收集',
  '驱动逻辑分析',
  '估值透支评估',
  '策略适用性对比',
  '风险机会识别',
  '综合结论输出',
];

/** ───────── 工作流节点（关键弹窗 3）兜底 ───────── */
const FALLBACK_WORKFLOW_NODES: DocumentWorkflowNode[] = [
  { label: '① 进入处理队列', caption: '已完成 · 用时 1.2s', state: 'done' },
  { label: '② 研究员规划任务步骤', caption: '已完成 · 拆解为 6 个子任务', state: 'done' },
  {
    label: '③ 收集市场数据',
    caption: '已完成 · 8 个数据源（akshare/同花顺/雪球/中信...）',
    state: 'done',
  },
  {
    label: '④ 子任务并行执行',
    caption: '已完成 · 6/6 子任务（涨停结构 / 估值检测 / 资金面 / 历史镜鉴 / PEG / DCF）',
    state: 'done',
  },
  {
    label: '⑤ 正在汇总输出',
    caption: '进行中 · 已生成 1,247 字 / 预计 4,500 字',
    state: 'active',
  },
  { label: '⑥ 生成最终报告', caption: '待执行', state: 'pending' },
];

/** ───────── 默认目录（无大纲时回退） ───────── */
const FALLBACK_TOC: { level: 1 | 2 | 3; text: string; active?: boolean }[] = [
  { level: 1, text: '半导体板块巨大分歧研究：趋势派满仓 vs 估值派看空', active: true },
  { level: 2, text: '引言/背景' },
  { level: 2, text: '核心分析' },
  { level: 3, text: '分析维度一：市场温度实测—情绪已到沸点' },
  { level: 3, text: '分析维度二：五大龙头估值体检—除了韦尔，...' },
  { level: 3, text: '分析维度三：三大驱动因素的拆解与权重' },
  { level: 3, text: '分析维度四：PEG 计算—基于一致预期的"性价比"' },
  { level: 3, text: '分析维度五：历史镜鉴—"这次不一样"是最贵的一句话' },
  { level: 3, text: '分析维度六：反推 DCF—当前估值隐含的"不可能假设"' },
  { level: 2, text: '趋势派 VS 估值派：逻辑对答案' },
  { level: 2, text: '结论与建议' },
  { level: 2, text: '风险提示' },
];

/** 从 markdown 解析多级目录（# / ## / ###） */
function extractToc(md?: string): { level: 1 | 2 | 3; text: string; active?: boolean }[] {
  if (!md) return FALLBACK_TOC;
  const headings: { level: 1 | 2 | 3; text: string }[] = [];
  md.split('\n').forEach((line) => {
    const m = /^(#{1,3})\s+(.+?)\s*$/.exec(line);
    if (!m) return;
    const lvl = m[1].length as 1 | 2 | 3;
    headings.push({ level: lvl, text: m[2].replace(/[#*`]/g, '').trim() });
  });
  if (headings.length === 0) return FALLBACK_TOC;
  return headings.map((h, i) => ({ ...h, active: i === 0 }));
}

/** ───────── Subcomponents ───────── */

function TocSidebar({ toc }: { toc: ReturnType<typeof extractToc> }) {
  return (
    <aside className="w-[200px] shrink-0 overflow-y-auto border-r border-ink-50 bg-ink-25 py-5">
      <div className="px-4 pb-2.5 text-[11px] tracking-[2px] text-ink-400">目 录</div>
      <nav>
        {toc.map((it, idx) => {
          const base =
            it.level === 1
              ? 'px-4 py-1.5 text-[12px] font-semibold text-ink-700'
              : it.level === 2
              ? 'px-4 py-1 text-[12px] text-ink-500'
              : 'px-6 py-1 text-[11.5px] text-ink-400';
          if (it.active) {
            return (
              <div
                key={`${idx}-${it.text}`}
                className={`${base} cursor-pointer border-l-[3px] border-brand-600 bg-brand-50/60`}
              >
                {it.text}
              </div>
            );
          }
          return (
            <div
              key={`${idx}-${it.text}`}
              className={`${base} cursor-pointer hover:bg-ink-50/60`}
            >
              {it.text}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

function RiskBar() {
  return (
    <div className="mb-4 rounded-lg border border-gold-200 bg-gold-50 px-3 py-2 text-[12px] text-gold-700">
      ⚠️ 此文档由 AI 生成，不提供任何投资参考，请理性阅读
    </div>
  );
}

function ProgressTasks() {
  return (
    <div className="mb-5 rounded-xl bg-[#eff7fa] px-4 py-3.5">
      <div className="mb-2.5 text-[13px] font-semibold text-[#0a5d7c]">任务进度</div>
      <div className="flex flex-col gap-2">
        {PROGRESS_TASKS.map((t) => (
          <div
            key={t}
            className="flex items-center justify-between text-[12.5px] text-ink-700"
          >
            <span className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-up-500 text-[10px] text-white">
                ✓
              </span>
              {t}
            </span>
            <span className="text-[11px] text-ink-400">👁</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function WorkflowPanel({ title, nodes = FALLBACK_WORKFLOW_NODES }: { title?: string; nodes?: DocumentWorkflowNode[] }) {
  const completedCount = nodes.filter((n) => n.state === 'done').length;
  return (
    <div className="mx-auto max-w-[640px] py-4">
      <div className="mb-4 flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-[#6e9d83] to-[#2e6e51] text-[14px] font-bold text-white">
          平
        </div>
        <div className="min-w-0">
          <div className="text-[13px] font-semibold text-ink-700">
            基本面分析·阿平 正在为你撰写
          </div>
          <div className="serif mt-0.5 truncate text-[15px] font-bold text-ink-900">
            「{title ?? '半导体板块巨大分歧研究：趋势派满仓 vs 估值派看空'}」
          </div>
        </div>
        <div className="ml-auto text-right">
          <div className="text-[11.5px] text-ink-400">预计还需</div>
          <div className="serif tnum text-[20px] font-bold text-brand-600">2 分 18 秒</div>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-ink-50 bg-white">
        <div className="flex items-center justify-between border-b border-ink-25 px-4 py-3">
          <div className="text-[13px] font-semibold text-ink-800">📋 工作流进度</div>
          <div className="text-[12px] text-ink-500">
            已完成 <b className="text-brand-600">{completedCount}/{nodes.length}</b>
          </div>
        </div>
        <div className="px-4 py-4">
          <div className="relative pl-6">
            <div className="absolute left-2 top-2 bottom-2 w-[2px] bg-ink-50" />
            <div
              className="absolute left-2 top-2 w-[2px] bg-gradient-to-b from-up-500 to-brand-500"
              style={{ height: `${(completedCount / nodes.length) * 100}%` }}
            />
            {nodes.map((n) => {
              const dotClass =
                n.state === 'done'
                  ? 'bg-up-500 text-white'
                  : n.state === 'active'
                  ? 'bg-brand-600 text-white'
                  : 'bg-ink-100 text-ink-400';
              return (
                <div key={n.label} className="relative py-1.5">
                  <span
                    className={`absolute -left-[22px] top-2.5 grid h-[18px] w-[18px] place-items-center rounded-full text-[10px] font-bold ${dotClass}`}
                  >
                    {n.state === 'done' ? '✓' : n.state === 'active' ? '●' : ''}
                  </span>
                  <div
                    className={`text-[13px] font-semibold ${
                      n.state === 'pending'
                        ? 'text-ink-400'
                        : n.state === 'active'
                        ? 'text-brand-700'
                        : 'text-ink-800'
                    }`}
                  >
                    {n.label}
                  </div>
                  <div className="text-[11.5px] text-ink-400">{n.caption}</div>
                  {n.state === 'active' && (
                    <div className="mt-1 h-1 overflow-hidden rounded bg-ink-25">
                      <div className="h-full w-[28%] bg-gradient-to-r from-brand-500 to-brand-600" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-4 rounded-lg bg-brand-50 px-3.5 py-2.5 text-[12px] text-brand-700">
            💡 你可以离开此页面，研报完成后会推送通知到工作台铃铛。
          </div>
        </div>
      </div>
    </div>
  );
}

/** markdown 渲染 —— 自定义 H1/H2/H3 左侧 brand 强调条样式 */
function DocBody({ detail }: { detail: DocumentDetail }) {
  return (
    <div className="space-y-3">
      {detail.tags?.length ? (
        <div className="flex flex-wrap gap-1">
          {detail.tags.map((t) => (
            <Tag key={t} color="default">
              {t}
            </Tag>
          ))}
        </div>
      ) : null}
      <article className="document-markdown text-[13px] leading-[1.85] text-ink-700">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => (
              <h1 className="serif border-l-[4px] border-brand-600 pl-2.5 text-[18px] font-bold text-ink-900">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="mt-5 border-l-[3px] border-brand-400 pl-2.5 text-[15px] font-bold text-ink-900">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="mt-3 border-l-[3px] border-gold-500 pl-2.5 text-[14px] font-semibold text-ink-800">
                {children}
              </h3>
            ),
            p: ({ children }) => <p className="mt-2 text-[13px] text-ink-700">{children}</p>,
            ul: ({ children }) => (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-ink-700">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-[13px] text-ink-700">{children}</ol>
            ),
            strong: ({ children }) => <b className="text-ink-900">{children}</b>,
            table: ({ children }) => (
              <div className="my-3 overflow-x-auto">
                <table className="w-full border-collapse text-[12.5px]">{children}</table>
              </div>
            ),
            th: ({ children }) => (
              <th className="border-b border-ink-50 bg-ink-25 px-3 py-2 text-left font-semibold text-ink-700">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border-b border-ink-25 px-3 py-2 text-ink-700">{children}</td>
            ),
          }}
        >
          {detail.content_markdown}
        </ReactMarkdown>
      </article>
    </div>
  );
}

function VipLockedBody({ detail }: { detail: DocumentDetail }) {
  return (
    <div className="mx-auto max-w-[620px] py-8 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-gold-50 text-[28px]">
        🔒
      </div>
      <div className="serif mt-4 text-[22px] font-bold text-ink-900">
        此内容需要VIP才能观看
      </div>
      <p className="mx-auto mt-3 max-w-[440px] text-[13px] leading-relaxed text-ink-500">
        {detail.vip_message ?? '开通后可查看完整研报正文、交易计划与风险清单。'}
      </p>
      <div className="mt-5 flex justify-center gap-2">
        <a
          href="/workstation/billing"
          className="rounded-lg bg-gold-500 px-4 py-2 text-[13px] font-semibold text-white hover:bg-gold-600"
        >
          开通VIP
        </a>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(`${detail.title}\n\n${detail.vip_message ?? '此内容需要VIP才能观看'}`);
          }}
          className="rounded-lg border border-ink-50 px-4 py-2 text-[13px] font-semibold text-ink-600 hover:bg-ink-25"
        >
          复制摘要
        </button>
      </div>
      <div className="mt-6 rounded-lg border border-gold-100 bg-gold-50 px-4 py-3 text-left text-[12px] leading-relaxed text-gold-700">
        VIP 权限包含专属文档完整查看、模拟交易实时执行与接收权限；当前仍可在右侧评论区讨论摘要或 @ 研究员补充问题。
      </div>
    </div>
  );
}

function CommentsPanel({
  comments,
  loading,
  submitting,
  mentionResearchers,
  mentionsLoading,
  onSubmit,
}: {
  comments: DocumentComment[];
  loading: boolean;
  submitting: boolean;
  mentionResearchers: CommunityMentionResearcher[];
  mentionsLoading: boolean;
  onSubmit: (text: string, replyToId?: string | null) => void;
}) {
  const [draft, setDraft] = useState('');
  const [replyTo, setReplyTo] = useState<DocumentComment | null>(null);
  const insertMention = (researcher: CommunityMentionResearcher) => {
    const token = `@${researcher.name}`;
    setDraft((prev) => {
      if (prev.includes(token)) return prev;
      const spacer = prev && !prev.endsWith(' ') ? ' ' : '';
      return `${prev}${spacer}${token} `;
    });
  };
  const submit = () => {
    const t = draft.trim();
    if (!t) return;
    onSubmit(t, replyTo?.comment_id ?? null);
    setDraft('');
    setReplyTo(null);
  };
  return (
    <aside className="flex w-[280px] shrink-0 flex-col border-l border-ink-50">
      <div className="flex items-center justify-between border-b border-ink-50 px-4 py-3">
        <div className="text-[14px] font-semibold text-ink-800">
          评论区{' '}
          <span className="ml-1 text-[11px] text-ink-400">♥ {comments.length}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {loading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : comments.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center py-12">
            <div className="text-[36px] opacity-30">💬</div>
            <div className="mt-2 text-[12px] text-ink-400">暂无评论，快来抢沙发吧～</div>
          </div>
        ) : (
          <ul className="space-y-4">
            {comments.map((c) => (
              <li key={c.comment_id} className="flex gap-2">
                <Avatar size={28}>{c.author.charAt(0) || '评'}</Avatar>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[11.5px] text-ink-500">
                    <b className="text-ink-700">{c.author}</b>
                    {c.author_type === 'ai_researcher' && (
                      <span className="rounded bg-gold-50 px-1.5 py-px text-[10px] font-semibold text-gold-700">
                        AI研究员
                      </span>
                    )}
                    <span className="text-ink-400">{dayjs(c.created_at).format('MM-DD HH:mm')}</span>
                  </div>
                  <div className="mt-1 text-[12.5px] leading-relaxed text-ink-700">
                    {c.reply_to_author && (
                      <div className="mb-1 rounded bg-brand-50 px-2 py-1 text-[11px] text-brand-700">
                        回复 @{c.reply_to_author}
                      </div>
                    )}
                    {c.content}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-[11px] text-ink-400">
                    <span>♥ {c.likes}</span>
                    <button
                      type="button"
                      onClick={() => {
                        setReplyTo(c);
                        setDraft((prev) => (prev.trim() ? prev : `@${c.author} `));
                      }}
                      className="hover:text-brand-600"
                    >
                      回复
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-ink-50 px-4 py-3">
        <div className="mb-2 rounded-lg bg-ink-25 px-2.5 py-2">
          {replyTo && (
            <div className="mb-2 flex items-center justify-between rounded-md bg-white px-2 py-1 text-[11px] text-ink-500">
              <span className="min-w-0 truncate">正在回复 @{replyTo.author}</span>
              <button
                type="button"
                onClick={() => setReplyTo(null)}
                className="ml-2 shrink-0 text-ink-400 hover:text-ink-700"
              >
                取消
              </button>
            </div>
          )}
          <div className="mb-1.5 text-[11px] font-semibold text-ink-500">
            @ 强制召唤研究员
          </div>
          {mentionsLoading ? (
            <div className="text-[11px] text-ink-400">正在读取已雇佣研究员…</div>
          ) : mentionResearchers.length ? (
            <div className="flex flex-wrap gap-1.5">
              {mentionResearchers.slice(0, 4).map((r) => (
                <button
                  key={r.researcher_id}
                  type="button"
                  onClick={() => insertMention(r)}
                  className="max-w-full truncate rounded-full border border-brand-100 bg-white px-2 py-0.5 text-[11px] font-semibold text-brand-700 transition-colors hover:border-brand-300 hover:bg-brand-50"
                  title={r.title ?? r.name}
                >
                  @{r.name}
                </button>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-ink-400">暂无可召唤的已雇佣研究员</div>
          )}
        </div>

        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="写下你的评论，输入 @ 强制召唤你的研究员…"
            className="min-w-0 flex-1 rounded-lg border border-ink-50 bg-ink-25 px-2.5 py-1.5 text-[12px] text-ink-800 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={submit}
            disabled={submitting}
            className="rounded-lg bg-brand-600 px-3.5 py-1.5 text-[11.5px] font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? '发送中' : '发送'}
          </button>
        </div>
      </div>
    </aside>
  );
}

async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
}

/** ───────── Main Component ───────── */
export function DocumentDetailDialog({
  documentId,
  open,
  onClose,
  status,
}: DocumentDetailDialogProps) {
  const [messageApi, messageContext] = message.useMessage();
  const query = useDocumentDetail(open ? documentId : undefined);
  const detail = query.data;
  const commentsQuery = useDocumentComments(documentId, open);
  const mentionQuery = useCommunityMentionConfig(open);
  const createCommentMutation = useCreateDocumentComment();

  const toc = useMemo(() => extractToc(detail?.content_markdown), [detail?.content_markdown]);
  const comments = commentsQuery.data ?? [];
  const mentionResearchers = mentionQuery.data?.researchers ?? [];

  // 推断状态：优先 prop > 后端字段（未来扩展） > 'ready'
  const inferred: 'generating' | 'ready' =
    status ??
    ((detail as unknown as { status?: 'generating' | 'ready' } | undefined)?.status ?? 'ready');

  const handleAddComment = async (text: string, replyToId?: string | null) => {
    if (!documentId) return;
    try {
      await createCommentMutation.mutateAsync({ documentId, content: text, replyToId });
      messageApi.success('评论已发送');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '评论发送失败');
    }
  };

  const handleCopyLink = async () => {
    if (!documentId) return;
    const origin = typeof window === 'undefined' ? '' : window.location.origin;
    const url = `${origin}/workstation/ai-insight/document/${documentId}`;
    try {
      await copyText(url);
      messageApi.success('分享链接已复制到剪贴板');
    } catch {
      messageApi.error('复制失败，请手动复制链接');
    }
  };

  const handleCopyFullText = async () => {
    if (!detail) return;
    try {
      await copyText(`${detail.title}\n\n${detail.content_markdown}`);
      messageApi.success('研报全文已复制');
    } catch {
      messageApi.error('复制失败，请手动复制文本');
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width="90vw"
      centered
      destroyOnHidden
      closable={false}
      title={null}
      styles={{
        body: { padding: 0, height: '78vh', overflow: 'hidden' },
        container: { padding: 0, overflow: 'hidden', borderRadius: 16 },
      }}
    >
      <div className="flex h-full w-full overflow-hidden bg-white">
        {messageContext}
        {/* 左：目录 */}
        <TocSidebar toc={toc} />

        {/* 中：内容 */}
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <header className="flex items-center justify-between border-b border-ink-50 px-5 py-3.5">
            <div className="serif min-w-0 truncate pr-3 text-[16px] font-bold text-ink-900">
              {detail?.title ?? '研报详情'}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {detail?.is_vip_only && (
                <span className="rounded bg-gold-50 px-2 py-1 text-[11px] font-semibold text-gold-700">
                  VIP专属
                </span>
              )}
              <button
                type="button"
                onClick={() => void handleCopyLink()}
                disabled={!documentId}
                className="rounded-lg border border-ink-50 bg-white px-2.5 py-1.5 text-[11.5px] font-semibold text-ink-600 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                复制链接
              </button>
              <button
                type="button"
                onClick={() => void handleCopyFullText()}
                disabled={!detail}
                className="rounded-lg border border-ink-50 bg-white px-2.5 py-1.5 text-[11.5px] font-semibold text-ink-600 transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                复制全文
              </button>
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭"
                className="grid h-7 w-7 place-items-center rounded text-[18px] text-ink-400 transition-colors hover:bg-ink-25 hover:text-ink-700"
              >
                ×
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-5">
            {query.isLoading ? (
              <Skeleton active paragraph={{ rows: 10 }} />
            ) : query.isError ? (
              <Empty description="文档详情加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : inferred === 'generating' ? (
              <WorkflowPanel title={detail?.title} nodes={detail?.workflow_nodes} />
            ) : detail ? (
              <>
                <RiskBar />
                <ProgressTasks />
                {detail.can_view_full ? <DocBody detail={detail} /> : <VipLockedBody detail={detail} />}
              </>
            ) : (
              <Empty description="暂无内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </div>
        </main>

        {/* 右：评论区 */}
        <CommentsPanel
          comments={comments}
          loading={commentsQuery.isLoading}
          submitting={createCommentMutation.isPending}
          mentionResearchers={mentionResearchers}
          mentionsLoading={mentionQuery.isLoading}
          onSubmit={(text) => void handleAddComment(text)}
        />
      </div>
    </Modal>
  );
}

export default DocumentDetailDialog;
