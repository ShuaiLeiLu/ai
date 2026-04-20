import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import { DocumentDetail, DocumentSummary, DocumentType } from '@/types/documents';

const API_BASE = '/documents';

export interface ListDocumentsParams {
  doc_type?: DocumentType;
}

export const listDocuments = async (params?: ListDocumentsParams): Promise<DocumentSummary[]> => {
  const query = new URLSearchParams();
  if (params?.doc_type) query.set('doc_type', params.doc_type);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await http<ApiResponse<ListResponse<DocumentSummary>>>(`${API_BASE}${suffix}`);
  return response.data.items;
};

export const listHotDocuments = async (limit = 6): Promise<DocumentSummary[]> => {
  const response = await http<ApiResponse<ListResponse<DocumentSummary>>>(`${API_BASE}/hot?limit=${limit}`);
  return response.data.items;
};

export const getDocumentDetail = async (documentId: string): Promise<DocumentDetail> => {
  const response = await http<ApiResponse<DocumentDetail>>(`${API_BASE}/${documentId}`);
  return response.data;
};

