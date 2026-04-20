export type ResearcherVisibility = 'draft' | 'private' | 'public';
export type ResearcherPublishStatus = 'draft' | 'published' | 'unpublished';

export interface ResearcherMarketCard {
  id: string;
  name: string;
  avatar?: string | null;
  introduction: string;
  level: string;
  hire_count: number;
  version: string;
  tags: string[];
  template_visible: boolean;
  is_hired: boolean;
}

export interface ResearcherMarketDetail extends ResearcherMarketCard {
  resume: string;
  prompt: string;
}

export interface ResearcherMineItem {
  id: string;
  name: string;
  avatar?: string | null;
  introduction: string;
  level: string;
  visibility: ResearcherVisibility;
  published_version?: string | null;
  publish_status: ResearcherPublishStatus;
  version: string;
  updated_at: string;
}

export interface ResearcherOptionItem {
  id: string;
  name: string;
}

export interface ResearcherDetail {
  researcher_id: string;
  name: string;
  title: string;
  style: string;
  status: string;
  today_pnl: number;
  win_rate_30d: number;
  level: string;
  avatar_url?: string | null;
  description: string;
  prompt: string;
  visibility: ResearcherVisibility;
  published_version?: string | null;
  skills: string[];
  knowledge_bases: string[];
  mcp_servers: string[];
  self_drive_tasks: string[];
  created_at: string;
  updated_at: string;
}

export interface ResearcherCreatePayload {
  name: string;
  title?: string;
  style?: string;
  description?: string;
  prompt?: string;
  visibility?: ResearcherVisibility;
  skills?: string[];
  knowledge_bases?: string[];
  mcp_servers?: string[];
  self_drive_tasks?: string[];
}

export interface ResearcherUpdatePayload {
  title?: string;
  style?: string;
  description?: string;
  prompt?: string;
  visibility?: ResearcherVisibility;
  skills?: string[];
  knowledge_bases?: string[];
  mcp_servers?: string[];
  self_drive_tasks?: string[];
}

export interface ResearcherPublishRecord {
  version: string;
  publish_time: string;
  status: ResearcherPublishStatus;
}

export interface ResearcherTestChatRequest {
  question: string;
}

export interface ResearcherTestChatResponse {
  researcher_id: string;
  question: string;
  answer: string;
  version_used: string;
  reply_time: string;
}
