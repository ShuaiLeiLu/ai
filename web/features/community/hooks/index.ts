import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';
import {
  CommunityCreateCommentPayload,
  CommunityCreatePostPayload,
  CommunityModerationPayload,
  CommunityPostListParams,
} from '@/types/community';

const featureKey = 'community';

export const useCommunityPosts = (params: CommunityPostListParams = {}) =>
  useQuery({
    queryKey: [featureKey, 'posts', params],
    queryFn: () => api.listCommunityPosts(params),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useCommunityPostDetail = (postId?: string) =>
  useQuery({
    queryKey: [featureKey, 'detail', postId ?? 'none'],
    queryFn: () => api.getCommunityPostDetail(postId as string),
    enabled: Boolean(postId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useCommunityComments = (postId?: string) =>
  useQuery({
    queryKey: [featureKey, 'comments', postId ?? 'none'],
    queryFn: () => api.listCommunityComments(postId as string),
    enabled: Boolean(postId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useCommunityMentionConfig = (enabled = true) =>
  useQuery({
    queryKey: [featureKey, 'mention-config'],
    queryFn: api.getCommunityMentionConfig,
    enabled,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useCreateCommunityPost = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CommunityCreatePostPayload) => api.createCommunityPost(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [featureKey] });
    }
  });
};

export const useCreateCommunityComment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CommunityCreateCommentPayload) => api.createCommunityComment(payload),
    onSuccess: (_data, payload) => {
      queryClient.invalidateQueries({ queryKey: [featureKey, 'posts'] });
      queryClient.invalidateQueries({ queryKey: [featureKey, 'detail', payload.post_id] });
      queryClient.invalidateQueries({ queryKey: [featureKey, 'comments', payload.post_id] });
    },
  });
};

export const useSetCommunityPostFeatured = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ postId, isFeatured }: { postId: string; isFeatured: boolean }) =>
      api.setCommunityPostFeatured(postId, isFeatured),
    onSuccess: (_data, payload) => {
      queryClient.invalidateQueries({ queryKey: [featureKey, 'posts'] });
      queryClient.invalidateQueries({ queryKey: [featureKey, 'detail', payload.postId] });
    },
  });
};

export const useDeleteCommunityPost = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ postId, payload }: { postId: string; payload: CommunityModerationPayload }) =>
      api.deleteCommunityPost(postId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: [featureKey, 'posts'] });
      queryClient.removeQueries({ queryKey: [featureKey, 'detail', variables.postId] });
      queryClient.removeQueries({ queryKey: [featureKey, 'comments', variables.postId] });
    },
  });
};

export const useDeleteCommunityComment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ commentId, payload }: { commentId: string; payload: CommunityModerationPayload }) =>
      api.deleteCommunityComment(commentId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [featureKey, 'posts'] });
      queryClient.invalidateQueries({ queryKey: [featureKey, 'detail'] });
      queryClient.invalidateQueries({ queryKey: [featureKey, 'comments'] });
    },
  });
};
