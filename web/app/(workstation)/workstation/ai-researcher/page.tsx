/**
 * AI 研究员工作台 —— 对标设计稿 5A · AI 研究员总览主页
 *
 * 入口（总览态）：
 *   1. 顶部 横向研究员切换 Tab —— ResearcherSwitcher
 *   2. 双栏：金色 Hero 问答 + AI 战绩榜单 —— AskHero + RankingBoard
 *   3. 底部 6 张研报文档网格 —— DocumentGrid
 *
 * 详情态（点击非"总览"chip）：
 *   ResearcherDetailView —— 保留原有视图（最新制品 + 模拟账户 + 工作日志）
 */
'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Alert,
  Badge,
  Button,
  Drawer,
  Empty,
  Input,
  message,
  Modal,
  Segmented,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import {
  ClearOutlined,
  CloseOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  FileTextOutlined,
  LoadingOutlined,
  PlusOutlined,
  RightOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
} from '@ant-design/icons';

import {
  useKnowledgeBaseOptions,
  useMcpServerOptions,
  useResearcherDetail,
  useSkillOptions,
  useTestChatWithResearcher,
  useUpdateResearcher,
} from '@/features/researcher-editor/hooks';
import { useDismissResearcher } from '@/features/researcher-market/hooks';
import { DocumentDetailDialog } from '@/features/documents/components/DocumentDetailDialog';
import { AskHero } from '@/features/researcher-workbench/components/AskHero';
import { DocumentGrid } from '@/features/researcher-workbench/components/DocumentGrid';
import { RankingBoard } from '@/features/researcher-workbench/components/RankingBoard';
import { ResearcherSwitcher } from '@/features/researcher-workbench/components/ResearcherSwitcher';
import { ResearcherAvatar, getResearcherBg } from '@/features/researcher-workbench/components/ResearcherAvatar';
import { useWorkbenchOverview } from '@/features/researcher-workbench/hooks';
import { useGenerateTradeReflection, useTradingLogsWhenEnabled, useTradingPortfolio } from '@/features/trading/hooks';
import { routes } from '@/lib/constants/routes';
import { useUserSessionStore } from '@/stores/user-session.store';
import type { ResearcherDetail, ResearcherUpdatePayload, ResearcherVisibility } from '@/types/researcher';
import type { HiredResearcher, HotDocument, RankSortBy } from '@/types/researcher-workbench';
import type { TradeLogItem, TradeLogSection } from '@/types/trading';

// ──────────── 通用工具函数 ────────────

/** 根据收益正负返回对应的 Tailwind 文字色 */
function yieldColor(value: number) {
  if (value > 0) return 'text-up-500';
  if (value < 0) return 'text-down-600';
  return 'text-ink-500';
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

const WORK_LOG_SECTION_TITLES = ['交易复盘', '执行反思', '次日展望'];

function stripMarkdown(value: string) {
  return value
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^\s*[-*]\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim();
}

function parseWorkLogSections(content: string): TradeLogSection[] {
  const lines = content.trim().split(/\r?\n/);
  const sections = new Map<string, string[]>();
  let currentTitle: string | null = null;

  for (const line of lines) {
    const heading = line.trim().match(/^##\s+(.+)$/);
    if (heading) {
      const title = heading[1].trim();
      currentTitle = WORK_LOG_SECTION_TITLES.includes(title) ? title : null;
      if (currentTitle && !sections.has(currentTitle)) sections.set(currentTitle, []);
      continue;
    }
    if (currentTitle) {
      sections.get(currentTitle)?.push(line);
    }
  }

  return WORK_LOG_SECTION_TITLES.map((title) => ({
    key: title,
    title,
    content: stripMarkdown((sections.get(title) ?? []).join('\n')),
  })).filter((section) => section.content.length > 0);
}

function getWorkLogSections(log: TradeLogItem): TradeLogSection[] {
  const structured = (log.sections ?? [])
    .filter((section) => WORK_LOG_SECTION_TITLES.includes(section.title) && section.content.trim())
    .map((section) => ({ ...section, content: stripMarkdown(section.content) }));
  if (structured.length > 0) return structured;

  return parseWorkLogSections(log.content);
}

interface ResearcherSettingsFormState {
  title: string;
  style: string;
  description: string;
  prompt: string;
  visibility: ResearcherVisibility;
  skills: string[];
  knowledge_bases: string[];
  mcp_servers: string[];
  self_drive_tasks: string[];
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'status';
  content: string;
  time: string;
  masterMode?: boolean;
  statusText?: string;
}

function formFromDetail(detail: ResearcherDetail): ResearcherSettingsFormState {
  return {
    title: detail.title,
    style: detail.style,
    description: detail.description,
    prompt: detail.prompt,
    visibility: detail.visibility,
    skills: detail.skills,
    knowledge_bases: detail.knowledge_bases,
    mcp_servers: detail.mcp_servers,
    self_drive_tasks: detail.self_drive_tasks,
  };
}

function nowTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function ResearcherChatDrawer({
  open,
  onClose,
  researchers,
  activeId,
  onActiveIdChange,
  initialQuestion,
  documents,
}: {
  open: boolean;
  onClose: () => void;
  researchers: HiredResearcher[];
  activeId: string | null;
  onActiveIdChange: (id: string) => void;
  initialQuestion: string | null;
  documents: HotDocument[];
}) {
  const [messageApi, messageContext] = message.useMessage();
  const [input, setInput] = useState('');
  const [masterMode, setMasterMode] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [seed, setSeed] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastInitialQuestion, setLastInitialQuestion] = useState<string | null>(null);
  const testChatMutation = useTestChatWithResearcher();

  const activeResearcher = useMemo(() => {
    if (researchers.length === 0) return null;
    return researchers.find((item) => item.researcher_id === activeId) ?? researchers[0];
  }, [activeId, researchers]);

  useEffect(() => {
    if (!open || activeId || researchers.length === 0) return;
    onActiveIdChange(researchers[0].researcher_id);
  }, [activeId, onActiveIdChange, open, researchers]);

  const recommendedQuestions = useMemo(() => {
    const pool = [
      '帮我分析下中国神华的投资价值。',
      '半导体板块下周走势怎么看？',
      '央行近期货币政策对 A 股的影响是什么？',
      '当前低估值蓝筹股有哪些值得跟踪？',
      'AI 行业未来 3 年趋势和产业链机会在哪里？',
      '帮我评估一下大盘系统性风险。',
      '如何构建一个低回撤的防守组合？',
      '用均线策略做一套简单的择时规则。',
      '如何用量化因子筛选低估成长股？',
      '当前市场环境更适合进攻还是防守？',
      '今天热点机会里哪些有持续性？',
      '给我的模拟盘做一份风险管理建议。',
    ];
    const start = (seed * 6) % pool.length;
    return Array.from({ length: 6 }, (_, index) => pool[(start + index) % pool.length]);
  }, [seed]);

  const sendQuestion = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed) return;
    if (!activeResearcher) {
      messageApi.warning('请先招募或创建研究员');
      return;
    }

    const userMessage: ChatMessage = {
      id: `${Date.now()}-user`,
      role: 'user',
      content: trimmed,
      time: nowTime(),
    };
    const statusMessage: ChatMessage = {
      id: `${Date.now()}-status`,
      role: 'status',
      content: masterMode
        ? '深度思考中 · 正在召回研报、行情和研究员记忆'
        : '正在回复中 · 正在召回研究员记忆',
      statusText: masterMode ? '预计消耗 20 算力' : '预计消耗 5 算力',
      time: nowTime(),
      masterMode,
    };

    setMessages((prev) => [...prev, userMessage, statusMessage]);
    setInput('');

    try {
      const result = await testChatMutation.mutateAsync({
        researcherId: activeResearcher.researcher_id,
        payload: { question: trimmed },
      });
      setMessages((prev) => [
        ...prev.filter((item) => item.id !== statusMessage.id),
        {
          id: `${Date.now()}-assistant`,
          role: 'assistant',
          content: result.answer,
          time: new Date(result.reply_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
          masterMode,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev.filter((item) => item.id !== statusMessage.id),
        {
          id: `${Date.now()}-assistant-error`,
          role: 'assistant',
          content: error instanceof Error ? `此回复出现错误：${error.message}` : '此回复出现错误，请稍后重试。',
          time: nowTime(),
          masterMode,
        },
      ]);
    }
  };

  useEffect(() => {
    if (!open || !initialQuestion || initialQuestion === lastInitialQuestion || !activeResearcher) return;
    setLastInitialQuestion(initialQuestion);
    void sendQuestion(initialQuestion);
  }, [activeResearcher, initialQuestion, lastInitialQuestion, open]);

  const confirmClearMessages = () => {
    if (!activeResearcher) return;
    Modal.confirm({
      title: `清除与「${activeResearcher.name}」的对话历史？`,
      content: (
        <div className="text-sm leading-relaxed text-ink-500">
          所有对话记录（含上下文记忆）将被清除，无法恢复。新建对话会重新建立上下文。
        </div>
      ),
      okText: '确认清除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => {
        setMessages([]);
        setLastInitialQuestion(null);
        setInput('');
        messageApi.success('对话已清空');
      },
    });
  };

  const latestDocuments = documents.slice(0, 2);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      width="min(1180px, 96vw)"
      closable={false}
      styles={{ body: { padding: 0, background: '#fbfaf7' } }}
    >
      {messageContext}
      <div className="grid h-full min-h-[720px] grid-cols-1 bg-ink-0 lg:grid-cols-[240px_minmax(0,1fr)_320px]">
        <aside className="hidden border-r border-ink-50 bg-white p-3 lg:block">
          <div className="px-2 pb-2 text-[11px] tracking-[0.2em] text-ink-400">我 的 研 究 员</div>
          <div className="space-y-1">
            {researchers.length === 0 ? (
              <div className="rounded-lg bg-ink-25 px-3 py-8 text-center text-xs text-ink-400">暂无研究员</div>
            ) : (
              researchers.map((researcher) => {
                const selected = researcher.researcher_id === activeResearcher?.researcher_id;
                return (
                  <button
                    key={researcher.researcher_id}
                    type="button"
                    onClick={() => onActiveIdChange(researcher.researcher_id)}
                    className={[
                      'flex w-full items-center gap-2 rounded-xl px-2.5 py-2.5 text-left transition-colors',
                      selected ? 'border-l-[3px] border-brand-600 bg-brand-50' : 'hover:bg-ink-25',
                    ].join(' ')}
                  >
                    <ResearcherAvatar name={researcher.name} size="md" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-semibold text-ink-900">{researcher.name}</div>
                      <div className="truncate text-[11px] text-ink-400">
                        {researcher.status === 'active' ? '在线' : '空闲'} · {researcher.level}
                      </div>
                    </div>
                    {researcher.status === 'active' && <span className="h-1.5 w-1.5 rounded-full bg-up-500" />}
                  </button>
                );
              })
            )}
          </div>
          <Link
            href={routes.researcherEditor}
            className="mt-4 block rounded-xl border border-dashed border-ink-100 px-3 py-3 text-center text-xs text-ink-400 hover:border-brand-200 hover:text-brand-600"
          >
            + 创建新研究员
          </Link>
        </aside>

        <main className="flex min-h-0 flex-col">
          <div className="flex flex-col gap-3 border-b border-ink-50 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              {activeResearcher && <ResearcherAvatar name={activeResearcher.name} size="md" />}
              <div>
                <div className="flex items-center gap-2">
                  <span className="serif text-[16px] font-bold text-ink-900">
                    {activeResearcher?.name ?? 'AI 研究员'}
                  </span>
                  {activeResearcher?.level && <span className="rounded bg-brand-50 px-1.5 py-px text-[11px] font-semibold text-brand-700">{activeResearcher.level}</span>}
                </div>
                <div className="text-[11px] text-up-600">● 在线 · 已接入研报、资讯与模拟盘上下文</div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-full border border-gold-300 bg-gold-50 px-3 py-1.5">
                <span className="text-xs font-semibold text-gold-700">大师模式</span>
                <Switch size="small" checked={masterMode} onChange={setMasterMode} />
                <span className="rounded bg-gold-100 px-1.5 py-px text-[10px] font-semibold text-gold-700">大师版+</span>
              </div>
              <Button size="small" icon={<ClearOutlined />} onClick={confirmClearMessages}>清空对话</Button>
              <Button size="small" icon={<CloseOutlined />} onClick={onClose}>收起</Button>
            </div>
          </div>

          {masterMode && (
            <div className="mx-4 mt-3 rounded-r-lg border-l-4 border-gold-500 bg-gold-50 px-3 py-2 text-xs leading-relaxed text-gold-700">
              <b>大师模式已启用</b> · 使用更强 AI 模型、深度思考和多源交叉验证，适合重要决策。每次对话预计消耗 20 算力。
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto bg-ink-25 px-4 py-5">
            <div className="mb-4 text-center text-[11px] text-ink-300">今天 {nowTime()}</div>
            {messages.length === 0 ? (
              <div className="mx-auto mt-16 max-w-md rounded-2xl border border-dashed border-ink-100 bg-white px-6 py-8 text-center">
                <div className="serif text-lg font-bold text-ink-900">向研究员发起一次深度研判</div>
                <div className="mt-2 text-xs leading-relaxed text-ink-500">
                  点击右侧推荐问题，或直接输入你关心的股票、题材、政策、仓位和风险问题。
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {messages.map((item) => {
                  if (item.role === 'status') {
                    return (
                      <div key={item.id} className="flex gap-2">
                        {activeResearcher && <ResearcherAvatar name={activeResearcher.name} size="sm" />}
                        <div className="flex max-w-[80%] items-center gap-2 rounded-2xl border border-ink-50 bg-white px-3.5 py-2.5 text-[12.5px] text-ink-600 shadow-card">
                          <LoadingOutlined className="text-brand-600" />
                          <span>{item.content}</span>
                          {item.statusText && <span className="rounded bg-gold-50 px-1.5 py-px text-[11px] text-gold-700">{item.statusText}</span>}
                        </div>
                      </div>
                    );
                  }
                  const isUser = item.role === 'user';
                  return (
                    <div key={item.id} className={['flex gap-2', isUser ? 'justify-end' : 'justify-start'].join(' ')}>
                      {!isUser && activeResearcher && <ResearcherAvatar name={activeResearcher.name} size="sm" />}
                      <div className={['max-w-[82%]', isUser ? 'items-end' : 'items-start'].join(' ')}>
                        {item.masterMode && !isUser && (
                          <div className="mb-2 rounded-xl border border-gold-200 bg-white px-3 py-2 text-xs text-gold-700">
                            <b>深度思考过程</b> · 已召回研报、行情、资讯和研究员角色设定；完成多源交叉验证。
                          </div>
                        )}
                        <div
                          className={[
                            'whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed shadow-card',
                            isUser
                              ? 'rounded-br-md bg-brand-600 text-white'
                              : 'rounded-bl-md border border-ink-50 bg-white text-ink-800',
                          ].join(' ')}
                        >
                          {item.content}
                        </div>
                        {!isUser && (
                          <div className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-ink-400">
                            <span>有用</span>
                            <span>重新生成</span>
                            <span>收藏到知识库</span>
                            <span>AI 回答不构成投资建议</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="border-t border-ink-50 bg-white px-4 py-3">
            <div className="mb-3 flex flex-wrap gap-2">
              {recommendedQuestions.slice(0, 4).map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => void sendQuestion(question)}
                  className="rounded-full border border-ink-50 bg-ink-25 px-3 py-1.5 text-[11.5px] text-ink-600 transition-colors hover:border-brand-200 hover:text-brand-700"
                >
                  {question}
                </button>
              ))}
              <button type="button" className="text-[11.5px] text-brand-600" onClick={() => setSeed((value) => value + 1)}>
                ↻ 换一批
              </button>
            </div>
            <div className="rounded-2xl border border-brand-100 bg-white p-3 shadow-[0_0_0_3px_rgba(29,74,52,.04)]">
              <Input.TextArea
                value={input}
                rows={2}
                placeholder={`向「${activeResearcher?.name ?? 'AI研究员'}」提问，输入 / 选择技能，输入 @ 引用持仓 / 资讯...`}
                className="!border-0 !p-0 !shadow-none"
                onChange={(event) => setInput(event.target.value)}
                onPressEnter={(event) => {
                  if (!event.shiftKey) {
                    event.preventDefault();
                    void sendQuestion(input);
                  }
                }}
              />
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex gap-3 text-[11.5px] text-ink-400">
                  <span>附件</span>
                  <span>引用持仓</span>
                  <span>引用资讯</span>
                  <span>引用研报</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-ink-400">预计消耗 <b className="text-gold-600">{masterMode ? 20 : 5} 算力</b></span>
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    loading={testChatMutation.isPending}
                    onClick={() => void sendQuestion(input)}
                  >
                    发送
                  </Button>
                </div>
              </div>
            </div>
            <div className="mt-2 text-center text-[11px] text-ink-400">AI 回答不构成投资建议。请理性参考、独立决策。</div>
          </div>
        </main>

        <aside className={['border-l border-ink-50 bg-white p-4 lg:block', historyCollapsed ? 'hidden' : 'hidden lg:block'].join(' ')}>
          <button
            type="button"
            className="mb-3 text-[11px] tracking-[0.2em] text-ink-400"
            onClick={() => setHistoryCollapsed((value) => !value)}
          >
            对 话 上 下 文
          </button>
          <div className="mb-4 rounded-2xl bg-gradient-to-br from-brand-700 to-[#0a1f18] p-4 text-white">
            <div className="text-sm font-semibold text-gold-300">3 天 VIP 体验卡</div>
            <div className="serif mt-1 text-[15px] font-bold">解锁大师模式 · 实时模拟交易</div>
            <div className="mt-2 space-y-1 text-[11px] leading-relaxed text-white/75">
              <div>每日签到 50 算力</div>
              <div>创建 AI 研究员 +5 名额</div>
              <div>专属文档完整查看</div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button type="button" className="rounded-lg bg-gold-500 px-2 py-1.5 text-[11px] font-bold text-ink-900">立即体验</button>
              <button type="button" className="rounded-lg border border-white/20 px-2 py-1.5 text-[11px] text-white/70">稍后再说</button>
            </div>
          </div>

          <div className="mb-4">
            <div className="mb-2 text-[11px] tracking-[0.2em] text-ink-400">最 近 研 判</div>
            <div className="space-y-2">
              {latestDocuments.length === 0 ? (
                <div className="rounded-lg bg-ink-25 px-3 py-5 text-center text-xs text-ink-400">暂无研判文档</div>
              ) : (
                latestDocuments.map((doc) => (
                  <div key={doc.id} className="rounded-lg bg-ink-25 px-3 py-2">
                    <div className="line-clamp-1 text-xs font-semibold text-ink-800">{doc.title}</div>
                    <div className="mt-1 text-[11px] text-ink-400">{doc.researcher_name} · {timeAgo(doc.create_time)}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="mb-4 rounded-xl border border-gold-200 bg-gold-50 px-3 py-3">
            <div className="text-xs font-semibold text-gold-700">首问奖励</div>
            <div className="mt-1 text-[11.5px] text-ink-600">
              完成今日首次提问，获得 <b className="text-gold-700">+10 算力</b>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded bg-gold-100">
              <div className="h-full w-full bg-gold-500" />
            </div>
          </div>

          <div>
            <div className="mb-2 text-[11px] tracking-[0.2em] text-ink-400">研 究 员 能 力</div>
            <div className="flex flex-wrap gap-1.5">
              {(activeResearcher?.tags.length ? activeResearcher.tags : ['估值分析', '财报解读', '行业对比', '风险控制']).map((tag) => (
                <span key={tag} className="rounded bg-brand-50 px-2 py-1 text-[11px] font-semibold text-brand-700">{tag}</span>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </Drawer>
  );
}

function ResearcherSettingsPanel({ researcherId }: { researcherId: string }) {
  const [messageApi, messageContext] = message.useMessage();
  const detailQuery = useResearcherDetail(researcherId);
  const skillsQuery = useSkillOptions();
  const knowledgeBasesQuery = useKnowledgeBaseOptions();
  const mcpServersQuery = useMcpServerOptions();
  const updateMutation = useUpdateResearcher();
  const [form, setForm] = useState<ResearcherSettingsFormState | null>(null);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [taskDraft, setTaskDraft] = useState('');
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setForm(null);
    setLoadedId(null);
    setTaskDraft('');
    setDirty(false);
  }, [researcherId]);

  useEffect(() => {
    if (!detailQuery.data || loadedId === detailQuery.data.researcher_id || dirty) return;
    setForm(formFromDetail(detailQuery.data));
    setLoadedId(detailQuery.data.researcher_id);
  }, [detailQuery.data, dirty, loadedId]);

  const setField = <K extends keyof ResearcherSettingsFormState>(key: K, value: ResearcherSettingsFormState[K]) => {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    setDirty(true);
  };

  const optionLoading = skillsQuery.isLoading || knowledgeBasesQuery.isLoading || mcpServersQuery.isLoading;
  const skillOptions = (skillsQuery.data ?? []).map((item) => ({ label: item.name, value: item.id }));
  const knowledgeBaseOptions = (knowledgeBasesQuery.data ?? []).map((item) => ({ label: item.name, value: item.id }));
  const mcpOptions = (mcpServersQuery.data ?? []).map((item) => ({ label: item.name, value: item.id }));

  const addTask = () => {
    const value = taskDraft.trim();
    if (!value || !form) return;
    if (form.self_drive_tasks.length >= 10) {
      messageApi.warning('自驱任务最多 10 项');
      return;
    }
    setField('self_drive_tasks', [...form.self_drive_tasks, value]);
    setTaskDraft('');
  };

  const removeTask = (index: number) => {
    if (!form) return;
    setField('self_drive_tasks', form.self_drive_tasks.filter((_, itemIndex) => itemIndex !== index));
  };

  const save = async () => {
    if (!form) return;
    if (!form.description.trim()) {
      messageApi.warning('研究员介绍不能为空');
      return;
    }
    if (!form.prompt.trim()) {
      messageApi.warning('提示词不能为空');
      return;
    }
    const payload: ResearcherUpdatePayload = {
      title: form.title.trim(),
      style: form.style.trim(),
      description: form.description.trim(),
      prompt: form.prompt,
      visibility: form.visibility,
      skills: form.skills,
      knowledge_bases: form.knowledge_bases,
      mcp_servers: form.mcp_servers,
      self_drive_tasks: form.self_drive_tasks,
    };
    try {
      const next = await updateMutation.mutateAsync({ researcherId, payload });
      setForm(formFromDetail(next));
      setDirty(false);
      messageApi.success('研究员配置已保存');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '保存失败');
    }
  };

  if (detailQuery.isError) {
    return (
      <div className="rounded-2xl border border-ink-50 bg-white p-6">
        <Empty description="研究员配置加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  if (detailQuery.isLoading || !form) {
    return (
      <div className="rounded-2xl border border-ink-50 bg-white p-4">
        <Skeleton active paragraph={{ rows: 8 }} />
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-ink-50 bg-white p-4">
      {messageContext}
      <div className="mb-4 flex flex-col gap-3 border-b border-dashed border-ink-100 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Typography.Title level={5} className="!mb-1">研究员配置</Typography.Title>
          <div className="text-xs text-ink-400">
            技能 / 知识库 / MCP / 提示词 / 自驱任务会直接保存到当前研究员。
          </div>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={updateMutation.isPending} onClick={save}>
          保存配置
        </Button>
      </div>

      {dirty && (
        <Alert
          type="warning"
          showIcon
          className="!mb-4"
          message="存在未保存改动"
          description="保存后总览卡片与研究员详情会同步刷新。"
        />
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.15fr]">
        <div className="space-y-4">
          <div className="rounded-xl border border-ink-50 p-4">
            <div className="mb-3 text-sm font-semibold text-ink-900">基本信息</div>
            <Space direction="vertical" className="w-full" size={12}>
              <div>
                <Typography.Text className="text-xs text-ink-500">定位标题</Typography.Text>
                <Input
                  value={form.title}
                  placeholder="如：短线情绪周期研究员"
                  onChange={(event) => setField('title', event.target.value)}
                />
              </div>
              <div>
                <Typography.Text className="text-xs text-ink-500">研究风格</Typography.Text>
                <Input
                  value={form.style}
                  placeholder="如：事件驱动 + 资金博弈"
                  onChange={(event) => setField('style', event.target.value)}
                />
              </div>
              <div>
                <Typography.Text className="text-xs text-ink-500">简介</Typography.Text>
                <Input.TextArea
                  rows={4}
                  value={form.description}
                  placeholder="描述研究员擅长方向、适用场景与风控边界"
                  onChange={(event) => setField('description', event.target.value)}
                />
              </div>
              <div>
                <Typography.Text className="text-xs text-ink-500">可见性</Typography.Text>
                <Select
                  value={form.visibility}
                  className="w-full"
                  options={[
                    { label: '草稿', value: 'draft' },
                    { label: '私有', value: 'private' },
                    { label: '公开', value: 'public' },
                  ]}
                  onChange={(value) => setField('visibility', value)}
                />
              </div>
            </Space>
          </div>

          <div className="rounded-xl border border-ink-50 p-4">
            <div className="mb-3 text-sm font-semibold text-ink-900">能力挂载</div>
            <Space direction="vertical" className="w-full" size={12}>
              <div>
                <Typography.Text className="text-xs text-ink-500">技能</Typography.Text>
                <Select
                  mode="multiple"
                  allowClear
                  maxCount={25}
                  loading={optionLoading}
                  value={form.skills}
                  options={skillOptions}
                  placeholder="选择技能"
                  className="w-full"
                  onChange={(value) => setField('skills', value)}
                />
              </div>
              <div>
                <Typography.Text className="text-xs text-ink-500">知识库</Typography.Text>
                <Select
                  mode="multiple"
                  allowClear
                  loading={optionLoading}
                  value={form.knowledge_bases}
                  options={knowledgeBaseOptions}
                  placeholder="选择知识库"
                  className="w-full"
                  onChange={(value) => setField('knowledge_bases', value)}
                />
              </div>
              <div>
                <Typography.Text className="text-xs text-ink-500">MCP 服务</Typography.Text>
                <Select
                  mode="multiple"
                  allowClear
                  loading={optionLoading}
                  value={form.mcp_servers}
                  options={mcpOptions}
                  placeholder="选择 MCP 服务"
                  className="w-full"
                  onChange={(value) => setField('mcp_servers', value)}
                />
              </div>
            </Space>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-ink-50 p-4">
            <div className="mb-3 text-sm font-semibold text-ink-900">系统提示词</div>
            <Input.TextArea
              rows={13}
              value={form.prompt}
              placeholder="写入研究目标、分析框架、风险约束与输出格式"
              onChange={(event) => setField('prompt', event.target.value)}
            />
          </div>

          <div className="rounded-xl border border-ink-50 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-sm font-semibold text-ink-900">自驱任务</div>
              <span className="text-xs text-ink-400">{form.self_drive_tasks.length}/10</span>
            </div>
            <div className="mb-3 flex gap-2">
              <Input
                value={taskDraft}
                placeholder="如：每日 08:00 生成盘前风险扫描"
                onChange={(event) => setTaskDraft(event.target.value)}
                onPressEnter={addTask}
              />
              <Button icon={<PlusOutlined />} onClick={addTask} />
            </div>
            {form.self_drive_tasks.length === 0 ? (
              <div className="rounded-lg bg-ink-25 px-3 py-6 text-center text-xs text-ink-400">
                暂无自驱任务
              </div>
            ) : (
              <div className="space-y-2">
                {form.self_drive_tasks.map((task, index) => (
                  <div key={`${task}-${index}`} className="flex items-center gap-2 rounded-lg bg-ink-25 px-3 py-2">
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-50 text-[10px] font-bold text-brand-600">
                      {index + 1}
                    </span>
                    <span className="min-w-0 flex-1 text-xs leading-relaxed text-ink-700">{task}</span>
                    <button
                      type="button"
                      className="text-xs text-ink-400 transition-colors hover:text-down-600"
                      onClick={() => removeTask(index)}
                    >
                      删除
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ──────────── 研究员详情视图 —— 保留原有实现 ────────────

/**
 * 最新制品 —— 横向滚动文档卡片
 */
function LatestDocuments({
  documents,
  loading,
  researcherName,
  onSelectDocument,
}: {
  documents: HotDocument[];
  loading: boolean;
  researcherName: string;
  onSelectDocument: (id: string) => void;
}) {
  if (loading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="w-60 shrink-0 rounded-xl border border-ink-50 p-4">
            <Skeleton active paragraph={{ rows: 3 }} />
          </div>
        ))}
      </div>
    );
  }
  if (documents.length === 0) {
    return <div className="py-8 text-center text-sm text-ink-400">暂无最新制品</div>;
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-thin">
      {documents.slice(0, 8).map((doc, index) => {
        const accents = ['bg-gold-50', 'bg-white', 'bg-ink-25', 'bg-up-50', 'bg-brand-50', 'bg-down-50'];
        const isFirst = index === 0;
        return (
          <button
            key={doc.id}
            type="button"
            onClick={() => onSelectDocument(doc.id)}
            className={[
              'flex h-48 w-52 shrink-0 cursor-pointer flex-col rounded-xl border border-ink-50 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-md',
              isFirst ? '' : accents[index % accents.length],
            ].join(' ')}
            style={isFirst ? { background: 'linear-gradient(135deg, #fdf4d8, #fcefc6)' } : undefined}
          >
            <div className="mb-2 text-[20px] leading-none text-gold-500 serif">“</div>
            <div className="serif line-clamp-2 text-[13px] font-bold leading-snug text-ink-900">
              {doc.title}
            </div>
            {doc.is_vip_only && (
              <span className="mt-1 inline-flex rounded bg-gold-50 px-1.5 py-px text-[10px] font-semibold text-gold-700">
                VIP专属
              </span>
            )}
            <div className="mt-2 line-clamp-3 flex-1 text-[11px] leading-relaxed text-ink-600">
              {doc.summary}
            </div>
            <div className="mt-2.5 border-t border-dashed border-ink-100 pt-2">
              <div className="flex items-center gap-1.5 text-[11px]">
                <ResearcherAvatar name={researcherName} size="xs" />
                <span className="truncate text-ink-500">{researcherName}</span>
                <span className="ml-auto text-ink-400">
                  {doc.metrics_ready && doc.view_count !== null ? `👁 ${doc.view_count}` : '👁 0'}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="rounded bg-up-50 px-1.5 py-px text-[10px] font-semibold text-up-600">自驱</span>
                <span className="text-[11px] text-ink-400">{timeAgo(doc.create_time)}</span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

/** 模拟账户区块 */
function PortfolioSection({ researcher }: { researcher: HiredResearcher }) {
  const rid = researcher.researcher_id;
  const snapshotQuery = useTradingPortfolio(rid);

  const loading = snapshotQuery.isLoading && !snapshotQuery.data;
  const acct = snapshotQuery.data?.account;
  const positions = snapshotQuery.data?.positions ?? [];

  const todayPnl = acct?.daily_pnl ?? 0;
  const todayStartAsset = acct ? acct.total_asset - todayPnl : 1_000_000;
  const todayPnlPct = todayStartAsset > 0 ? todayPnl / todayStartAsset : 0;

  return (
    <div className="rounded-2xl border border-ink-50 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Typography.Title level={5} className="!mb-0 !text-base">模拟账户</Typography.Title>
          <span className="text-xs text-ink-400">当前持仓 {positions.length} 只</span>
        </div>
        <Link
          href={routes.tradingDetail(rid)}
          className="text-xs text-brand-500 hover:text-brand-600 flex items-center gap-0.5 transition-colors"
        >
          查看详情 <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>

      {loading && <Skeleton active paragraph={{ rows: 5 }} />}

      {!loading && acct && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[200px_1fr]">
          <div className="space-y-4 border-r border-ink-25 pr-4">
            <div>
              <div className="text-xs text-ink-400 mb-1">总资产</div>
              <div className="serif tnum text-2xl font-bold text-ink-900">{formatWan(acct.total_asset)}</div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-ink-400">今日盈亏</span>
                <span className={`font-bold tnum ${yieldColor(todayPnl)}`}>
                  {todayPnl > 0 ? '+' : ''}{formatMoney(todayPnl)}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-ink-400">今日收益率</span>
                <span className={`font-bold tnum ${yieldColor(todayPnlPct)}`}>{formatPct(todayPnlPct)}</span>
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <div className="rounded-lg bg-ink-25 px-3 py-2">
                <div className="text-[10px] uppercase tracking-wider text-ink-400 mb-0.5">持仓资金</div>
                <div className="text-sm font-bold text-ink-700 tnum">{formatWan(acct.holding_value)}</div>
              </div>
              <div className="rounded-lg bg-brand-50 px-3 py-2 border border-brand-100/50">
                <div className="text-[10px] uppercase tracking-wider text-brand-400 mb-0.5">可用资金</div>
                <div className="text-sm font-bold text-brand-600 tnum">{formatWan(acct.available_cash)}</div>
              </div>
            </div>
          </div>

          <div className="min-w-0">
            <div className="max-h-[260px] overflow-x-auto overflow-y-auto pr-1">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="border-b border-ink-50 text-left text-xs text-ink-400">
                    <th className="px-2 py-2.5 font-medium">股票</th>
                    <th className="px-2 py-2.5 font-medium text-right">数量</th>
                    <th className="px-2 py-2.5 font-medium text-right">成本/现价</th>
                    <th className="px-2 py-2.5 font-medium text-right">当日盈亏</th>
                    <th className="px-2 py-2.5 font-medium text-right">累计盈亏%</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-25">
                  {positions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-12 text-center text-sm text-ink-400 italic">
                        暂无持仓 — 策略待执行或尚未开盘
                      </td>
                    </tr>
                  ) : positions.map((p) => (
                    <tr key={p.symbol} className="hover:bg-ink-25 transition-colors">
                      <td className="px-2 py-3">
                        <div className="font-semibold text-ink-900">{p.name}</div>
                        <div className="text-[11px] font-mono text-ink-400">{p.symbol}</div>
                      </td>
                      <td className="px-2 py-3 text-right font-medium text-ink-600 tnum">{p.quantity}</td>
                      <td className="px-2 py-3 text-right tnum">
                        <div className="text-ink-600 font-medium">{p.cost_price.toFixed(2)}</div>
                        <div className="text-[11px] text-ink-400">{p.current_price.toFixed(2)}</div>
                      </td>
                      <td className="px-2 py-3 text-right">
                        <div className={`font-bold tnum ${yieldColor(p.pnl)}`}>
                          {p.pnl > 0 ? '+' : ''}{p.pnl.toFixed(2)}
                        </div>
                      </td>
                      <td className="px-2 py-3 text-right">
                        <div className={`inline-flex rounded px-1.5 py-0.5 text-xs font-bold tnum ${p.pnl >= 0 ? 'bg-up-50 text-up-600' : 'bg-down-50 text-down-600'}`}>
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
        </div>
      )}
    </div>
  );
}

/** 工作日志时间线 */
function WorkLogSection({ researcherId }: { researcherId: string }) {
  const logsQuery = useTradingLogsWhenEnabled(researcherId);
  const generateReflection = useGenerateTradeReflection();
  const tradeLogCount = (logsQuery.data ?? []).filter((log) => log.log_type === 'trade').length;
  const reviewLogs = useMemo(() => {
    return (logsQuery.data ?? [])
      .filter((log) => log.log_type === 'analysis')
      .map((log) => ({ log, sections: getWorkLogSections(log) }))
      .filter((item) => item.sections.length > 0)
      .sort((a, b) => new Date(b.log.created_at).getTime() - new Date(a.log.created_at).getTime())
      .slice(0, 6);
  }, [logsQuery.data]);

  return (
    <div className="rounded-2xl border border-ink-50 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <Typography.Title level={5} className="!mb-0 !text-sm text-gold-600">工作日志</Typography.Title>
        <Link href={routes.tradingDetail(researcherId)} className="flex items-center gap-0.5 text-xs text-gold-600 hover:text-gold-700">
          查看详情 <RightOutlined style={{ fontSize: 10 }} />
        </Link>
      </div>
      {logsQuery.isLoading && (
        <div className="space-y-3 py-1">
          {[1, 2, 3].map((item) => (
            <Skeleton key={item} active paragraph={{ rows: 2 }} title={false} />
          ))}
        </div>
      )}
      {!logsQuery.isLoading && reviewLogs.length === 0 && (
        <div className="rounded-md bg-ink-25 px-3 py-6 text-center">
          <Empty
            description={tradeLogCount > 0 ? `已有 ${tradeLogCount} 条真实成交日志，暂无 AI 复盘日志` : '暂无 AI 复盘日志'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
          {tradeLogCount > 0 && (
            <>
              <div className="mx-auto mt-2 max-w-xs text-xs leading-relaxed text-ink-400">
                当前历史数据只有成交记录。点击下方按钮会基于最近一笔真实成交调用 AI，并把复盘保存到日志。
              </div>
              <Button
                size="small"
                type="primary"
                className="mt-3"
                loading={generateReflection.isPending}
                onClick={async () => {
                  try {
                    await generateReflection.mutateAsync(researcherId);
                    message.success('AI 复盘已生成');
                  } catch {
                    message.error('AI 复盘生成失败，请稍后再试');
                  }
                }}
              >
                生成 AI 复盘
              </Button>
            </>
          )}
        </div>
      )}
      {!logsQuery.isLoading && reviewLogs.length > 0 && (
        <Timeline
          items={reviewLogs.map(({ log, sections }) => ({
            dot: <ClockCircleOutlined className="text-brand-500" />,
            children: (
              <div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-400">
                  <span>{formatDate(log.created_at)} {new Date(log.created_at).toLocaleTimeString('zh-CN', { hour12: false })}</span>
                  <Tag color="purple" className="!text-xs !px-1.5 !py-0">AI复盘</Tag>
                </div>
                {log.title && <div className="mt-1 text-xs font-semibold text-ink-700">{log.title}</div>}
                <div className="mt-2 space-y-2">
                  {sections.map((section) => (
                    <div key={section.key} className="rounded-md bg-ink-25 px-2.5 py-2">
                      <div className="mb-1 text-[11px] font-semibold text-gold-600">{section.title}</div>
                      <div className="line-clamp-3 text-xs leading-relaxed text-ink-600">{section.content}</div>
                    </div>
                  ))}
                </div>
              </div>
            ),
          }))}
        />
      )}
    </div>
  );
}

/** 研究员详情视图 */
function ResearcherDetailView({
  researcher,
  documents,
  docsLoading,
  onSelectDocument,
  onDismiss,
  dismissing,
  onBack,
}: {
  researcher: HiredResearcher;
  documents: HotDocument[];
  docsLoading: boolean;
  onSelectDocument: (id: string) => void;
  onDismiss: (researcher: HiredResearcher) => void;
  dismissing: boolean;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<'overview' | 'settings'>('overview');
  const headerBg = getResearcherBg(researcher.name);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="rounded-2xl border border-ink-50 bg-white px-4 py-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={[
                'grid h-16 w-16 place-items-center rounded-2xl serif text-[28px] font-bold text-white',
                headerBg.className ?? '',
              ].filter(Boolean).join(' ')}
              style={headerBg.style}
            >
              {researcher.name.split('·').pop()?.[0] ?? researcher.name[0]}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="serif text-[22px] font-bold text-ink-900">{researcher.name}</span>
                {researcher.level && (
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">
                    {researcher.level}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 mt-1">
                <Badge status={researcher.status === 'active' ? 'processing' : 'default'} />
                <span className="text-xs text-ink-400">
                  {researcher.status === 'active' ? '努力工作中' : '空闲'}
                </span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={dismissing}
              onClick={() => onDismiss(researcher)}
            >
              解雇研究员
            </Button>
            <button
              type="button"
              onClick={onBack}
              className="rounded-md border border-ink-50 px-3 py-1.5 text-xs text-ink-500 hover:bg-ink-25 transition-colors"
            >
              ← 返回总览
            </button>
          </div>
        </div>

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

      {tab === 'overview' && (
        <>
          <div className="rounded-2xl border border-ink-50 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <Typography.Title level={5} className="!mb-0 !text-base">最新制品</Typography.Title>
              <Link href="#" className="flex items-center gap-0.5 text-xs text-brand-500 hover:text-brand-600">
                查看全部 <RightOutlined style={{ fontSize: 10 }} />
              </Link>
            </div>
            <LatestDocuments
              documents={documents}
              loading={docsLoading}
              researcherName={researcher.name}
              onSelectDocument={onSelectDocument}
            />
          </div>

          <PortfolioSection researcher={researcher} />
          <WorkLogSection researcherId={researcher.researcher_id} />
        </>
      )}

      {tab === 'settings' && (
        <ResearcherSettingsPanel researcherId={researcher.researcher_id} />
      )}
    </div>
  );
}

// ──────────── 页面主组件 ────────────

export default function AIResearcherWorkstationPage() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<RankSortBy>('today');
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInitialQuestion, setChatInitialQuestion] = useState<string | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>();
  const accessToken = useUserSessionStore((s) => s.accessToken);
  const overviewQuery = useWorkbenchOverview(sortBy, Boolean(accessToken));
  const hiredResearchers = overviewQuery.data?.hired ?? [];
  const hotDocuments = overviewQuery.data?.hot_documents ?? [];
  const publicRankings = overviewQuery.data?.rankings ?? [];
  const loading = overviewQuery.isLoading;
  const dismissResearcher = useDismissResearcher();

  const activeResearcher = hiredResearchers.find((r) => r.researcher_id === activeId) ?? null;

  // 今日最热研究员：按今日收益率取榜首
  const hotResearcher = useMemo(() => {
    if (hiredResearchers.length === 0) return null;
    const sorted = [...hiredResearchers].sort((a, b) => {
      const ya = a.today_yield_rate ?? -Infinity;
      const yb = b.today_yield_rate ?? -Infinity;
      return yb - ya;
    });
    return sorted[0];
  }, [hiredResearchers]);

  // 今日已生成研报数：取 24h 内的 hot_documents
  const todayDocCount = useMemo(() => {
    const dayAgo = Date.now() - 24 * 3600 * 1000;
    return hotDocuments.filter((d) => new Date(d.create_time).getTime() >= dayAgo).length;
  }, [hotDocuments]);

  // 详情态下传给 LatestDocuments 的文档列表
  const detailDocuments = useMemo(() => {
    if (!activeResearcher) return hotDocuments;
    const filtered = hotDocuments.filter((d) => d.researcher_name === activeResearcher.name);
    return filtered.length > 0 ? filtered : hotDocuments;
  }, [activeResearcher, hotDocuments]);

  const openChatWithQuestion = (question: string) => {
    const targetResearcher = activeResearcher ?? hotResearcher ?? hiredResearchers[0] ?? null;
    if (!targetResearcher) {
      message.warning('请先招募或创建研究员');
      return;
    }
    setActiveId(targetResearcher.researcher_id);
    setChatInitialQuestion(question);
    setChatOpen(true);
  };

  const confirmDismissResearcher = (researcher: HiredResearcher) => {
    Modal.confirm({
      title: `确认解雇「${researcher.name}」？`,
      content: (
        <div className="space-y-2 text-sm leading-relaxed text-ink-500">
          <div>解雇后将无法继续使用该研究员：</div>
          <ul className="list-disc space-y-1 pl-5">
            <li>当前对话记录会被清除，无法恢复。</li>
            <li>该研究员的定时任务会停止执行。</li>
            <li>历史研报仍会保留在文档库中。</li>
          </ul>
        </div>
      ),
      okText: '确认解雇',
      cancelText: '取消',
      okButtonProps: { danger: true, loading: dismissResearcher.isPending },
      onOk: async () => {
        try {
          await dismissResearcher.mutateAsync(researcher.researcher_id);
          if (activeId === researcher.researcher_id) {
            setActiveId(null);
          }
          setChatOpen(false);
          setChatInitialQuestion(null);
          message.success('已解雇研究员');
        } catch (error) {
          const description = error instanceof Error ? error.message : '解雇失败，请稍后重试。';
          message.error(description);
          throw error;
        }
      },
    });
  };

  return (
    <div className="space-y-4">
      {/* 顶部 横向研究员切换 Tab —— 始终显示 */}
      <ResearcherSwitcher
        researchers={hiredResearchers}
        activeId={activeId}
        onSelect={setActiveId}
      />

      {activeResearcher ? (
        <ResearcherDetailView
          researcher={activeResearcher}
          documents={detailDocuments}
          docsLoading={loading}
          onSelectDocument={setSelectedDocumentId}
          onDismiss={confirmDismissResearcher}
          dismissing={dismissResearcher.isPending}
          onBack={() => setActiveId(null)}
        />
      ) : (
        <>
          {/* 双栏：问答区 + 战绩榜 */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
            <AskHero
              todayCount={todayDocCount}
              hotResearcher={hotResearcher}
              onAskQuestion={openChatWithQuestion}
            />
            <RankingBoard
              rankings={publicRankings}
              loading={loading}
              sortBy={sortBy}
              onSortChange={setSortBy}
              onSelect={(id) => setActiveId(id)}
            />
          </div>

          {/* 研报文档网格 */}
          <DocumentGrid
            documents={hotDocuments}
            loading={loading}
            onSelectDocument={setSelectedDocumentId}
          />
        </>
      )}

      <ResearcherChatDrawer
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        researchers={hiredResearchers}
        activeId={activeId}
        onActiveIdChange={setActiveId}
        initialQuestion={chatInitialQuestion}
        documents={hotDocuments}
      />

      <DocumentDetailDialog
        documentId={selectedDocumentId}
        open={Boolean(selectedDocumentId)}
        onClose={() => setSelectedDocumentId(undefined)}
      />

    </div>
  );
}
