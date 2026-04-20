export type DocumentType = 'market' | 'stock' | 'industry' | 'topic';

export interface DocumentSummary {
  document_id: string;
  title: string;
  researcher_name: string;
  document_type: DocumentType;
  symbol: string | null;
  view_count: number;
  like_count: number;
  created_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  content_markdown: string;
  tags: string[];
}

