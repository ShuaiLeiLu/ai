/**
 * 使用说明页面（中国金融审美重构）
 *
 * 顶部：SectionHeading「使用说明」+ 副标题
 * 主区：6 张步骤卡（grid-cols-3 md / 单列 sm），每卡 emoji + 思源宋体标题 + 12.5px 正文 + 操作按钮
 * 主题：🚀 3 分钟上手 / 🤖 研究员是什么 / ⚡ 算力如何计费 / 📊 模拟交易 / 📚 投喂私域知识 / ⚠️ 风险提示
 *
 * 底部：常见问题 + 联系入口（保留原内容，视觉迁移到 PageCard）。
 */
'use client';

import Link from 'next/link';
import type { Route } from 'next';
import { Collapse } from 'antd';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';

/** 步骤卡数据结构 */
interface GuideCard {
  /** 表情图标（28px 显示） */
  emoji: string;
  /** 卡片标题（思源宋体） */
  title: string;
  /** 正文（12.5px） */
  body: string;
  /** 按钮文案 */
  cta: string;
  /** 按钮目标（路由） */
  href: string;
  /** 按钮类型 */
  ctaType?: 'primary' | 'default';
  /** 强调条颜色 */
  accent?: 'brand' | 'gold' | 'up' | 'down';
}

/** 6 个核心场景 */
const GUIDE_CARDS: GuideCard[] = [
  {
    emoji: '🚀',
    title: '3 分钟上手',
    body: '注册登录 → 雇佣首位研究员 → 查看 AI 早间研判。无需配置，开箱即用。',
    cta: '开始体验',
    href: '/',
    ctaType: 'primary',
    accent: 'brand',
  },
  {
    emoji: '🤖',
    title: '研究员是什么',
    body: '研究员是为你工作的 AI 投研助手，每个都有独立策略、知识库与产出物，支持自建或雇佣。',
    cta: '了解研究员',
    href: '/researchers',
    accent: 'brand',
  },
  {
    emoji: '⚡',
    title: '算力如何计费',
    body: '所有 AI 任务消耗「电池」算力，按 token 与模型档位计费。会员享 7~9 折，每月赠送额度。',
    cta: '查看账户',
    href: '/billing',
    accent: 'gold',
  },
  {
    emoji: '📊',
    title: '模拟交易',
    body: '虚拟资金 100 万元起步，跟踪研究员的策略复盘真实盘面，不涉及真实下单与资金风险。',
    cta: '进入模拟盘',
    href: '/trading',
    accent: 'up',
  },
  {
    emoji: '📚',
    title: '投喂私域知识',
    body: '上传研报、公告、笔记到「我的知识库」，研究员将基于你的资料做检索增强分析（RAG）。',
    cta: '管理知识库',
    href: '/lab',
    accent: 'brand',
  },
  {
    emoji: '⚠️',
    title: '风险提示',
    body: 'AI 输出仅供研究参考，不构成投资建议。市场有风险，决策请独立判断并控制仓位。',
    cta: '阅读合规说明',
    href: '#',
    accent: 'down',
  },
];

/** 常见问题列表 */
const FAQ_ITEMS = [
  {
    key: '1',
    label: '如何创建我的第一个 AI 研究员？',
    children:
      '前往「极睿实验室 → 创建研究员」，点击「创建研究员」按钮，填写名称、等级、简介等信息即可。创建后可在「AI 研究员」工作台中查看和管理。',
  },
  {
    key: '2',
    label: '雇佣研究员和自己创建有什么区别？',
    children:
      '雇佣研究员是使用其他用户公开发布的研究员配置，适合快速上手；自建研究员可以完全自定义策略、知识库和提示词，灵活度更高。',
  },
  {
    key: '3',
    label: '知识库支持哪些文件格式？',
    children:
      '目前支持 PDF、Word（.docx）、TXT、Markdown 等文本格式，后续将支持更多格式。单个文件大小限制为 50MB。',
  },
  {
    key: '4',
    label: '模拟账户的资金是真实的吗？',
    children: '模拟账户使用虚拟资金进行策略验证，不涉及真实交易。初始虚拟资金为 100 万元，可在设置中重置。',
  },
  {
    key: '5',
    label: 'MCP 市场是什么？',
    children:
      'MCP（Model Context Protocol）市场提供各种数据源服务器的接入能力，如实时行情、K 线数据、公告检索等，让 AI 研究员获取实时市场数据。',
  },
  {
    key: '6',
    label: '如何联系客服或反馈问题？',
    children: '如遇到问题或有建议，可在「极睿社区」发帖反馈，或发送邮件至 support@cyberfininvest.com。',
  },
];

/** 按钮样式映射 —— 用 Tailwind 写定，不引入 antd Button 以保持设计一致 */
function CtaButton({
  type = 'default',
  accent = 'brand',
  href,
  children,
}: {
  type?: 'primary' | 'default';
  accent?: GuideCard['accent'];
  href: string;
  children: React.ReactNode;
}) {
  const baseColorMap: Record<NonNullable<GuideCard['accent']>, { bg: string; text: string; border: string }> = {
    brand: { bg: 'bg-brand-600 hover:bg-brand-700', text: 'text-white', border: 'border-brand-600' },
    gold: { bg: 'bg-gold-500 hover:bg-gold-600', text: 'text-white', border: 'border-gold-500' },
    up: { bg: 'bg-up-500 hover:bg-up-600', text: 'text-white', border: 'border-up-500' },
    down: { bg: 'bg-down-500 hover:bg-down-600', text: 'text-white', border: 'border-down-500' },
  };
  const c = baseColorMap[accent ?? 'brand'];

  const primaryCls = `${c.bg} ${c.text} ${c.border}`;
  const defaultCls = 'bg-white text-ink-800 border-ink-100 hover:border-brand-400 hover:text-brand-600';

  return (
    <Link
      href={href as Route}
      className={[
        'inline-flex items-center justify-center rounded-md border px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
        type === 'primary' ? primaryCls : defaultCls,
      ].join(' ')}
    >
      {children}
      <span className="ml-1">→</span>
    </Link>
  );
}

export function UserGuidePageClient() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* 页面标题 */}
      <SectionHeading title="使用说明" subtitle="10 分钟上手极睿智投 · 5 个核心场景" />

      {/* 6 张步骤卡 */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {GUIDE_CARDS.map((card) => (
          <PageCard key={card.title} accent={card.accent ?? 'brand'}>
            <div className="card-bd">
              {/* 大 emoji */}
              <div style={{ fontSize: 28, lineHeight: 1 }} aria-hidden>
                {card.emoji}
              </div>

              {/* 思源宋体标题 */}
              <div className="serif mt-3 text-[18px] font-bold text-ink-900">{card.title}</div>

              {/* 正文 */}
              <p className="mt-2 text-[12.5px] leading-[1.7] text-ink-600">{card.body}</p>

              {/* 操作按钮 */}
              <div className="mt-4">
                <CtaButton type={card.ctaType ?? 'default'} accent={card.accent} href={card.href}>
                  {card.cta}
                </CtaButton>
              </div>
            </div>
          </PageCard>
        ))}
      </div>

      {/* 常见问题 */}
      <PageCard title="常见问题" subtitle="高频咨询与解答" accent="brand">
        <Collapse
          items={FAQ_ITEMS}
          bordered={false}
          className="!bg-transparent"
        />
      </PageCard>

      {/* 底部提示 */}
      <div className="rounded-2xl border border-brand-100 bg-brand-50/60 px-5 py-4 text-center text-[13px] text-brand-700">
        还有其他问题？欢迎在「极睿社区」发帖交流，或联系我们的客服团队。
      </div>
    </div>
  );
}
