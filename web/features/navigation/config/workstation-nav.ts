import type { ComponentType } from 'react';
import {
  AppstoreOutlined,
  CommentOutlined,
  CompassOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FireOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  LineChartOutlined,
  RobotOutlined,
  ShopOutlined,
  TeamOutlined,
  UserAddOutlined,
} from '@ant-design/icons';

import { routes } from '@/lib/constants/routes';

export interface NavItem {
  key: string;
  label: string;
  href?: string;
  icon: ComponentType;
  /** 角标（数字或文字，如未读数 / 新功能标记） */
  badge?: string | number;
  children?: NavItem[];
}

/** 导航分组 —— 对齐设计稿：核心工作台 / 研究员 / 数据与文档 */
export interface NavGroup {
  key: string;
  /** 分组标题（侧栏 letter-spaced 小标题） */
  title: string;
  items: NavItem[];
}

export const workstationNavGroups: NavGroup[] = [
  {
    key: 'core',
    title: '核心工作台',
    items: [
      { key: 'overview', label: '盘前速览', href: routes.preopen, icon: DashboardOutlined },
      { key: 'event-driven', label: '题材掘金', href: routes.eventDriven, icon: FireOutlined },
      { key: 'ai-researcher', label: 'AI研究员', href: routes.aiResearcher, icon: RobotOutlined },
      { key: 'community', label: '赛博社区', href: routes.community, icon: CommentOutlined },
      { key: 'news-analysis', label: '资讯分析', href: routes.newsAnalysis, icon: FileSearchOutlined },
      { key: 'trading', label: '策略交易', href: routes.trading, icon: LineChartOutlined },
      { key: 'tasks', label: '任务编排', href: routes.tasks, icon: CompassOutlined },
    ],
  },
  {
    key: 'researcher',
    title: '研究员',
    items: [
      { key: 'my-researchers', label: '我的研究员', href: routes.labCreateResearcher, icon: UserAddOutlined },
      { key: 'talent-market', label: '人才市场', href: routes.labTalentMarket, icon: TeamOutlined },
      { key: 'skill-market', label: '技能市场', href: routes.labSkillMarket, icon: ShopOutlined },
      { key: 'mcp-market', label: 'MCP 市场', href: routes.labMcpMarket, icon: AppstoreOutlined },
    ],
  },
  {
    key: 'data',
    title: '数据与文档',
    items: [
      { key: 'documents', label: '研报库', href: routes.documents, icon: FileTextOutlined },
      { key: 'knowledge-base', label: '我的知识库', href: routes.labKnowledgeBase, icon: DatabaseOutlined },
    ],
  },
];

/** 兼容旧消费方（扁平化） */
export const workstationNav: NavItem[] = workstationNavGroups.flatMap((g) => g.items);
