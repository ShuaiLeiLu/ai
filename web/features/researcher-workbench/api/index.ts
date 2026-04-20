import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import {
  HiredResearcher,
  HotDocument,
  PublicRankItem,
  RankSortBy,
  WorkbenchOverview
} from '@/types/researcher-workbench';

const API_BASE = '/researchers/workbench';

export const getWorkbenchOverview = async (sortBy: RankSortBy = 'today'): Promise<WorkbenchOverview> => {
  const response = await http<ApiResponse<WorkbenchOverview>>(`${API_BASE}/overview?sort_by=${sortBy}`);
  return response.data;
};

export const getHiredResearchers = async (): Promise<HiredResearcher[]> => {
  const response = await http<ApiResponse<ListResponse<HiredResearcher>>>(`${API_BASE}/hired`);
  return response.data.items;
};

export const getHotDocuments = async (): Promise<HotDocument[]> => {
  const response = await http<ApiResponse<ListResponse<HotDocument>>>(`${API_BASE}/hot-documents`);
  return response.data.items;
};

export const getPublicRank = async (sortBy: RankSortBy): Promise<PublicRankItem[]> => {
  const response = await http<ApiResponse<ListResponse<PublicRankItem>>>(
    `${API_BASE}/public-rank?sort_by=${sortBy}`
  );
  return response.data.items;
};
