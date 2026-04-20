import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import { ResearcherMarketCard, ResearcherMarketDetail, ResearcherMineItem } from '@/types/researcher';

const RESEARCHER_API_BASE = '/researchers';

export interface MarketQueryParams {
  q?: string;
  page?: number;
  page_size?: number;
}

function buildMarketQuery(params?: MarketQueryParams): string {
  if (!params) return '';
  const query = new URLSearchParams();
  if (params.q) query.set('q', params.q);
  if (params.page) query.set('page', String(params.page));
  if (params.page_size) query.set('page_size', String(params.page_size));
  const text = query.toString();
  return text ? `?${text}` : '';
}

export const getMarketResearchers = async (
  params?: MarketQueryParams
): Promise<ListResponse<ResearcherMarketCard>> => {
  const response = await http<ApiResponse<ListResponse<ResearcherMarketCard>>>(
    `${RESEARCHER_API_BASE}/market${buildMarketQuery(params)}`
  );
  return response.data;
};

export const getMarketResearcherDetail = async (researcherId: string): Promise<ResearcherMarketDetail> => {
  const response = await http<ApiResponse<ResearcherMarketDetail>>(`${RESEARCHER_API_BASE}/market/${researcherId}`);
  return response.data;
};

export const getMyResearchers = async (): Promise<ResearcherMineItem[]> => {
  const response = await http<ApiResponse<ListResponse<ResearcherMineItem>>>(`${RESEARCHER_API_BASE}/mine`);
  return response.data.items;
};

export const hireResearcher = async (researcherId: string): Promise<void> => {
  await http<ApiResponse<unknown>>(`${RESEARCHER_API_BASE}/${researcherId}/hire`, {
    method: 'POST'
  });
};

export const dismissResearcher = async (researcherId: string): Promise<void> => {
  await http<ApiResponse<unknown>>(`${RESEARCHER_API_BASE}/${researcherId}/dismiss`, {
    method: 'POST'
  });
};

export const duplicateResearcher = async (researcherId: string): Promise<void> => {
  await http<ApiResponse<unknown>>(`${RESEARCHER_API_BASE}/${researcherId}/duplicate`, {
    method: 'POST'
  });
};

export const publishResearcher = async (researcherId: string): Promise<void> => {
  await http<ApiResponse<unknown>>(`${RESEARCHER_API_BASE}/${researcherId}/publish`, {
    method: 'POST'
  });
};

export const unpublishResearcher = async (researcherId: string): Promise<void> => {
  await http<ApiResponse<unknown>>(`${RESEARCHER_API_BASE}/${researcherId}/unpublish`, {
    method: 'POST'
  });
};
