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
  is_vip_only: boolean;
  can_view_full: boolean;
  vip_message?: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  content_markdown: string;
  tags: string[];
  workflow_nodes: DocumentWorkflowNode[];
}

export interface DocumentWorkflowNode {
  label: string;
  caption: string;
  state: 'done' | 'active' | 'pending';
}

export interface DocumentComment {
  comment_id: string;
  author: string;
  author_type: 'user' | 'ai_researcher' | string;
  content: string;
  likes: number;
  created_at: string;
  reply_to_id?: string | null;
  reply_to_author?: string | null;
}
