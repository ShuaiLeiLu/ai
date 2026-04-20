import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';
import { CommunityCreatePostPayload } from '@/types/community';

const featureKey = 'community';

export const useCommunityPosts = () =>
  useQuery({
    queryKey: [featureKey, 'posts'],
    queryFn: api.listCommunityPosts
  });

export const useCommunityPostDetail = (postId?: string) =>
  useQuery({
    queryKey: [featureKey, 'detail', postId ?? 'none'],
    queryFn: () => api.getCommunityPostDetail(postId as string),
    enabled: Boolean(postId)
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

