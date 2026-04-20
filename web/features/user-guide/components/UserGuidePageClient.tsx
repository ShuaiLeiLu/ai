/**
 * 使用说明页面客户端组件
 *
 * 以分区卡片形式展示平台各功能模块的使用指南：
 *  - 快速开始（注册/登录 → 创建研究员 → 查看分析）
 *  - AI研究员（创建/雇佣/工作台）
 *  - 赛博社区（浏览/发帖/互动）
 *  - 盘前速览（市场概览/行情数据）
 *  - 资讯分析（新闻筛选/AI分析）
 *  - 赛博实验室（知识库/技能/MCP市场）
 *  - 常见问题FAQ
 */
'use client';

import { Collapse, Divider, Steps, Tag, Typography } from 'antd';
import {
  AppstoreOutlined,
  BookOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  QuestionCircleOutlined,
  RobotOutlined,
  RocketOutlined,
  TeamOutlined,
} from '@ant-design/icons';

/** 单个指南区块的数据结构 */
interface GuideSection {
  title: string;
  icon: React.ReactNode;
  color: string;
  description: string;
  steps: string[];
}

/** 平台功能模块指南配置 */
const guideSections: GuideSection[] = [
  {
    title: '快速开始',
    icon: <RocketOutlined />,
    color: 'from-violet-50 to-violet-100/50 border-violet-200',
    description: '三步上手赛博投研平台，从注册到获取第一份AI分析报告。',
    steps: [
      '注册/登录账号：点击右上角头像进入登录页面，使用手机号+密码注册并登录。',
      '创建或雇佣研究员：前往「赛博实验室 → 创建研究员」自建，或在「人才市场」挑选现成的专业研究员。',
      '查看AI分析：回到「AI研究员」工作台，选中研究员即可查看其最新制品、模拟持仓和工作日志。',
      '浏览资讯：前往「盘前速览」和「资讯分析」获取实时市场行情与AI解读。',
    ],
  },
  {
    title: 'AI研究员',
    icon: <RobotOutlined />,
    color: 'from-blue-50 to-blue-100/50 border-blue-200',
    description: '管理你的AI投研助手，查看实时分析报告与模拟交易。',
    steps: [
      '进入「AI研究员」页面，左侧面板显示所有已雇佣的研究员列表。',
      '点击任意研究员切换到其工作台，查看今日收益、标签和30日胜率。',
      '「概览」Tab 展示最新制品（横向滚动卡片）、模拟账户持仓和工作日志。',
      '「设置」Tab（开发中）将支持调整研究员的技能配置、知识库关联与提示词。',
    ],
  },
  {
    title: '赛博社区',
    icon: <TeamOutlined />,
    color: 'from-emerald-50 to-emerald-100/50 border-emerald-200',
    description: '与其他用户交流投研心得，分享策略见解。',
    steps: [
      '进入「赛博社区」页面，通过顶部 Tab 切换全部/物价/热门分类。',
      '使用搜索框快速查找感兴趣的帖子。',
      '点击帖子卡片打开详情抽屉，查看完整内容和评论。',
      '点击右上角「+ 发布」按钮，填写标题、正文和标签发布新帖。',
    ],
  },
  {
    title: '盘前速览',
    icon: <DashboardOutlined />,
    color: 'from-amber-50 to-amber-100/50 border-amber-200',
    description: '开盘前快速了解市场全貌，把握当日热点。',
    steps: [
      '进入「盘前速览」页面，顶部展示核心市场指标（新开户数/胜率/换手率等）。',
      '左侧「A股资讯」实时推送重要新闻，右侧「盘前热门解读」聚合AI观点。',
      '下方股票表格支持涨/跌 Tab 切换，产业涨跌面积图直观呈现板块表现。',
      '底部24小时热股解析帮助你锁定市场关注焦点。',
    ],
  },
  {
    title: '资讯分析',
    icon: <FileSearchOutlined />,
    color: 'from-rose-50 to-rose-100/50 border-rose-200',
    description: '多维度资讯筛选与AI智能解读。',
    steps: [
      '进入「资讯分析」页面，左侧通过 Segmented Tab 切换全部/精选/公告/研报分类。',
      '开启「只看重要」开关过滤非关键信息，点击热股标签按股票维度筛选。',
      '右侧「AI智能分析」面板提供四大维度：市场总结、热点追踪、市场变盘、行业关注。',
      '下方「24小时热股解析」排行榜按热度分数排列，帮助发现市场热点。',
    ],
  },
  {
    title: '赛博实验室',
    icon: <ExperimentOutlined />,
    color: 'from-cyan-50 to-cyan-100/50 border-cyan-200',
    description: '配置研究员能力：知识库、技能包、MCP数据源。',
    steps: [
      '「我的知识库」：创建专属知识库，上传研报、公告等文档供研究员检索。',
      '「创建研究员」：自定义AI研究员，配置其名称、等级、技能和提示词。',
      '「人才市场」：浏览市场上公开的研究员，一键雇佣适合自己风格的助手。',
      '「技能市场」：发现和安装技能包（如K线分析、事件追踪等），增强研究员能力。',
      '「MCP市场」：接入MCP服务器获取实时行情数据、Level2、公告全文检索等能力。',
    ],
  },
];

/** 常见问题列表 */
const faqItems = [
  {
    key: '1',
    label: '如何创建我的第一个AI研究员？',
    children: '前往「赛博实验室 → 创建研究员」，点击「创建研究员」按钮，填写名称、等级、简介等信息即可。创建后可在「AI研究员」工作台中查看和管理。',
  },
  {
    key: '2',
    label: '雇佣研究员和自己创建有什么区别？',
    children: '雇佣研究员是使用其他用户公开发布的研究员配置，适合快速上手；自建研究员可以完全自定义策略、知识库和提示词，灵活度更高。',
  },
  {
    key: '3',
    label: '知识库支持哪些文件格式？',
    children: '目前支持 PDF、Word（.docx）、TXT、Markdown 等文本格式，后续将支持更多格式。单个文件大小限制为 50MB。',
  },
  {
    key: '4',
    label: '模拟账户的资金是真实的吗？',
    children: '模拟账户使用虚拟资金进行策略验证，不涉及真实交易。初始虚拟资金为 100 万元，可在设置中重置。',
  },
  {
    key: '5',
    label: 'MCP市场是什么？',
    children: 'MCP（Model Context Protocol）市场提供各种数据源服务器的接入能力，如实时行情、K线数据、公告检索等，让AI研究员获取实时市场数据。',
  },
  {
    key: '6',
    label: '如何联系客服或反馈问题？',
    children: '如遇到问题或有建议，可在「赛博社区」发帖反馈，或发送邮件至 support@cyberfininvest.com。',
  },
];

export function UserGuidePageClient() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* 页面标题 */}
      <div className="text-center">
        <Typography.Title level={2} className="!mb-2">
          使用说明
        </Typography.Title>
        <Typography.Text type="secondary" className="text-base">
          了解赛博投研平台的核心功能，快速上手AI智能投研
        </Typography.Text>
      </div>

      {/* 功能指南卡片 */}
      {guideSections.map((section, index) => (
        <div
          key={section.title}
          className={`rounded-xl border bg-gradient-to-br p-6 ${section.color}`}
        >
          {/* 卡片头部 */}
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-lg shadow-sm">
              {section.icon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <Typography.Title level={4} className="!mb-0">
                  {section.title}
                </Typography.Title>
                <Tag color="purple" className="!text-xs">
                  {index === 0 ? '入门' : '功能'}
                </Tag>
              </div>
              <Typography.Text type="secondary" className="text-sm">
                {section.description}
              </Typography.Text>
            </div>
          </div>

          {/* 步骤列表 */}
          <Steps
            direction="vertical"
            size="small"
            current={-1}
            items={section.steps.map((step, i) => ({
              title: (
                <span className="text-sm text-slate-700">{step}</span>
              ),
              status: 'wait' as const,
            }))}
            className="!mt-2"
          />
        </div>
      ))}

      <Divider />

      {/* 常见问题 */}
      <div className="rounded-xl bg-white p-6">
        <div className="mb-4 flex items-center gap-3">
          <QuestionCircleOutlined className="text-xl text-brand-500" />
          <Typography.Title level={4} className="!mb-0">
            常见问题
          </Typography.Title>
        </div>
        <Collapse
          items={faqItems}
          bordered={false}
          className="!bg-transparent"
        />
      </div>

      {/* 底部提示 */}
      <div className="rounded-lg bg-brand-50 p-4 text-center text-sm text-brand-600">
        还有其他问题？欢迎在「赛博社区」发帖交流，或联系我们的客服团队。
      </div>
    </div>
  );
}
