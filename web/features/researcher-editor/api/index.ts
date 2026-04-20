import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import {
  ResearcherCreatePayload,
  ResearcherDetail,
  ResearcherOptionItem,
  ResearcherTestChatRequest,
  ResearcherTestChatResponse,
  ResearcherUpdatePayload
} from '@/types/researcher';

const RESEARCHER_API_BASE = '/researchers';

export const getResearcherDetail = async (researcherId: string): Promise<ResearcherDetail> => {
  const response = await http<ApiResponse<ResearcherDetail>>(`${RESEARCHER_API_BASE}/${researcherId}`);
  return response.data;
};

export const createResearcher = async (payload: ResearcherCreatePayload): Promise<ResearcherDetail> => {
  const response = await http<ApiResponse<ResearcherDetail>>(RESEARCHER_API_BASE, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  return response.data;
};

export const updateResearcher = async (
  researcherId: string,
  payload: ResearcherUpdatePayload
): Promise<ResearcherDetail> => {
  const response = await http<ApiResponse<ResearcherDetail>>(`${RESEARCHER_API_BASE}/${researcherId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
  return response.data;
};

export const listSkillOptions = async (): Promise<ResearcherOptionItem[]> => {
  const response = await http<ApiResponse<ListResponse<ResearcherOptionItem>>>(`${RESEARCHER_API_BASE}/options/skills`);
  return response.data.items;
};

export const listKnowledgeBaseOptions = async (): Promise<ResearcherOptionItem[]> => {
  const response = await http<ApiResponse<ListResponse<ResearcherOptionItem>>>(
    `${RESEARCHER_API_BASE}/options/knowledge-bases`
  );
  return response.data.items;
};

export const listMcpServerOptions = async (): Promise<ResearcherOptionItem[]> => {
  const response = await http<ApiResponse<ListResponse<ResearcherOptionItem>>>(
    `${RESEARCHER_API_BASE}/options/mcp-servers`
  );
  return response.data.items;
};

export const testChatWithResearcher = async (
  researcherId: string,
  payload: ResearcherTestChatRequest
): Promise<ResearcherTestChatResponse> => {
  const response = await http<ApiResponse<ResearcherTestChatResponse>>(`${RESEARCHER_API_BASE}/${researcherId}/test-chat`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  return response.data;
};
