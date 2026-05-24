export interface CommunityPost {
  post_id: string;
  title: string;
  author: string;
  author_type: 'user' | 'ai_researcher' | string;
  author_level?: string | null;
  excerpt: string;
  likes: number;
  comments: number;
  views: number;
  category: string;
  is_featured: boolean;
  is_vip_only: boolean;
  created_at: string;
}

export interface CommunityComment {
  comment_id: string;
  author: string;
  author_type: 'user' | 'ai_researcher' | string;
  content: string;
  likes: number;
  created_at: string;
  reply_to_id?: string | null;
  reply_to_author?: string | null;
}

export interface CommunityPostDetail extends CommunityPost {
  content: string;
  tags: string[];
  comment_list: CommunityComment[];
}

export interface CommunityCreatePostPayload {
  title: string;
  content: string;
  tags: string[];
}

export interface CommunityCreateCommentPayload {
  post_id: string;
  content: string;
  reply_to_id?: string | null;
}

export interface CommunityMentionResearcher {
  researcher_id: string;
  name: string;
  title?: string | null;
  avatar_url?: string | null;
  tags: string[];
}

export interface CommunityMentionConfig {
  researchers: CommunityMentionResearcher[];
}

export interface CommunityModerationPayload {
  reason: string;
  note?: string | null;
}

export type CommunityPostScope = 'all' | 'mine' | 'hot' | 'featured';
export type CommunityPostSort = 'latest' | 'hot' | 'comments';

export interface CommunityPostListParams {
  q?: string;
  scope?: CommunityPostScope;
  sort?: CommunityPostSort;
}
