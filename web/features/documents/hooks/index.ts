import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'documents';

export const useDocuments = (params?: api.ListDocumentsParams) =>
  useQuery({
    queryKey: [featureKey, 'list', params ?? {}],
    queryFn: () => api.listDocuments(params),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useHotDocuments = (limit = 6) =>
  useQuery({
    queryKey: [featureKey, 'hot', limit],
    queryFn: () => api.listHotDocuments(limit),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useDocumentDetail = (documentId?: string) =>
  useQuery({
    queryKey: [featureKey, 'detail', documentId ?? 'none'],
    queryFn: () => api.getDocumentDetail(documentId as string),
    enabled: Boolean(documentId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useDocumentComments = (documentId?: string, enabled = true) =>
  useQuery({
    queryKey: [featureKey, 'comments', documentId ?? 'none'],
    queryFn: () => api.listDocumentComments(documentId as string),
    enabled: Boolean(documentId) && enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useCreateDocumentComment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      content,
      replyToId,
    }: {
      documentId: string;
      content: string;
      replyToId?: string | null;
    }) => api.createDocumentComment(documentId, content, replyToId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: [featureKey, 'comments', variables.documentId] });
      queryClient.invalidateQueries({ queryKey: [featureKey, 'detail', variables.documentId] });
    },
  });
};
