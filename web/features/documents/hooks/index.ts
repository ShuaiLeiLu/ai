import { useQuery } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'documents';

export const useDocuments = (params?: api.ListDocumentsParams) =>
  useQuery({
    queryKey: [featureKey, 'list', params ?? {}],
    queryFn: () => api.listDocuments(params)
  });

export const useHotDocuments = (limit = 6) =>
  useQuery({
    queryKey: [featureKey, 'hot', limit],
    queryFn: () => api.listHotDocuments(limit)
  });

export const useDocumentDetail = (documentId?: string) =>
  useQuery({
    queryKey: [featureKey, 'detail', documentId ?? 'none'],
    queryFn: () => api.getDocumentDetail(documentId as string),
    enabled: Boolean(documentId)
  });

