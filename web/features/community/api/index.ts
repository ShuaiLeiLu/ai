import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import { CommunityCreatePostPayload, CommunityPost, CommunityPostDetail } from '@/types/community';

const API_BASE = '/community/posts';

export const listCommunityPosts = async (): Promise<CommunityPost[]> => {
  const response = await http<ApiResponse<ListResponse<CommunityPost>>>(API_BASE);
  return response.data.items;
};

export const getCommunityPostDetail = async (postId: string): Promise<CommunityPostDetail> => {
  const response = await http<ApiResponse<CommunityPostDetail>>(`${API_BASE}/${postId}`);
  return response.data;
};

export const createCommunityPost = async (payload: CommunityCreatePostPayload): Promise<CommunityPostDetail> => {
  const response = await http<ApiResponse<CommunityPostDetail>>(API_BASE, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  return response.data;
};

