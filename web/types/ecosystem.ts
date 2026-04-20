export interface KnowledgeBaseItem {
  kb_id: string;
  name: string;
  document_count: number;
  updated_at: string;
}

export interface SkillItem {
  skill_id: string;
  name: string;
  description: string;
  installed: boolean;
}

export interface McpServerItem {
  server_id: string;
  name: string;
  category: string;
  connected: boolean;
}

