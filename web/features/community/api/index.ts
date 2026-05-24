import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import {
  CommunityComment,
  CommunityCreateCommentPayload,
  CommunityCreatePostPayload,
  CommunityMentionConfig,
  CommunityModerationPayload,
  CommunityPostListParams,
  CommunityPost,
  CommunityPostDetail,
} from '@/types/community';
import { OperationResponse } from '@/types/api';

const API_BASE = '/ai-community/post';
const COMMENT_BASE = '/ai-community/comment';

export const listCommunityPosts = async (params: CommunityPostListParams = {}): Promise<CommunityPost[]> => {
  const search = new URLSearchParams();
  if (params.q?.trim()) search.set('q', params.q.trim());
  if (params.scope) search.set('scope', params.scope);
  if (params.sort) search.set('sort', params.sort);
  const query = search.toString();
  const response = await http<ApiResponse<ListResponse<CommunityPost>>>(
    `${API_BASE}/list${query ? `?${query}` : ''}`,
  );
  return response.data.items;
};

export const getCommunityPostDetail = async (postId: string): Promise<CommunityPostDetail> => {
  const response = await http<ApiResponse<CommunityPostDetail>>(`${API_BASE}/${postId}`);
  return response.data;
};

export const createCommunityPost = async (payload: CommunityCreatePostPayload): Promise<CommunityPostDetail> => {
  const response = await http<ApiResponse<CommunityPostDetail>>(`${API_BASE}/create`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  return response.data;
};

export const listCommunityComments = async (postId: string): Promise<CommunityComment[]> => {
  const response = await http<ApiResponse<ListResponse<CommunityComment>>>(
    `${COMMENT_BASE}/list?post_id=${encodeURIComponent(postId)}`,
  );
  return response.data.items;
};

export const createCommunityComment = async (
  payload: CommunityCreateCommentPayload,
): Promise<CommunityComment> => {
  const response = await http<ApiResponse<CommunityComment>>(`${COMMENT_BASE}/create`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return response.data;
};

export const getCommunityMentionConfig = async (): Promise<CommunityMentionConfig> => {
  const response = await http<ApiResponse<CommunityMentionConfig>>('/ai-community/mention/config');
  return response.data;
};

export const setCommunityPostFeatured = async (
  postId: string,
  isFeatured: boolean,
): Promise<CommunityPostDetail> => {
  const response = await http<ApiResponse<CommunityPostDetail>>(`${API_BASE}/${postId}/feature`, {
    method: 'POST',
    body: JSON.stringify({ is_featured: isFeatured }),
  });
  return response.data;
};

export const deleteCommunityPost = async (
  postId: string,
  payload: CommunityModerationPayload,
): Promise<OperationResponse> => {
  const response = await http<ApiResponse<OperationResponse>>(`${API_BASE}/${postId}/delete`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return response.data;
};

export const deleteCommunityComment = async (
  commentId: string,
  payload: CommunityModerationPayload,
): Promise<OperationResponse> => {
  const response = await http<ApiResponse<OperationResponse>>(
    `/ai-community/comment/${commentId}/delete`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
  return response.data;
};
