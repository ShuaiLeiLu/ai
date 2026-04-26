import type { ComponentType } from 'react';
import {
  AppstoreOutlined,
  BookOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  RobotOutlined,
  ShopOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UserAddOutlined,
} from '@ant-design/icons';

import { routes } from '@/lib/constants/routes';

export interface NavItem {
  key: string;
  label: string;
  href?: string;
  icon: ComponentType;
  children?: NavItem[];
}

export const workstationNav: NavItem[] = [
  { key: 'ai-researcher', label: 'AI研究员', href: routes.aiResearcher, icon: RobotOutlined },
  { key: 'community', label: '极睿社区', href: routes.community, icon: TeamOutlined },
  { key: 'overview', label: '盘前速览', href: routes.preopen, icon: DashboardOutlined },
  { key: 'news-analysis', label: '资讯分析', href: routes.newsAnalysis, icon: FileSearchOutlined },
  {
    key: 'lab',
    label: '极睿实验室',
    icon: ExperimentOutlined,
    children: [
      { key: 'lab-knowledge', label: '我的知识库', href: routes.labKnowledgeBase, icon: BookOutlined },
      { key: 'lab-researchers', label: '创建研究员', href: routes.labCreateResearcher, icon: UserAddOutlined },
      { key: 'lab-talent', label: '人才市场', href: routes.labTalentMarket, icon: ShopOutlined },
      { key: 'lab-skill', label: '技能市场', href: routes.labSkillMarket, icon: ThunderboltOutlined },
      { key: 'lab-mcp', label: 'MCP市场', href: routes.labMcpMarket, icon: AppstoreOutlined },
    ],
  },
];
