import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import { KnowledgeBaseItem, McpServerItem, SkillItem } from '@/types/ecosystem';

const API_BASE = '/ecosystem';

export const listKnowledgeBases = async (): Promise<KnowledgeBaseItem[]> => {
  const response = await http<ApiResponse<ListResponse<KnowledgeBaseItem>>>(`${API_BASE}/knowledge-bases`);
  return response.data.items;
};

export const listSkills = async (installed?: boolean): Promise<SkillItem[]> => {
  const suffix = typeof installed === 'boolean' ? `?installed=${installed}` : '';
  const response = await http<ApiResponse<ListResponse<SkillItem>>>(`${API_BASE}/skills${suffix}`);
  return response.data.items;
};

export const listMcpServers = async (): Promise<McpServerItem[]> => {
  const response = await http<ApiResponse<ListResponse<McpServerItem>>>(`${API_BASE}/mcp-servers`);
  return response.data.items;
};

