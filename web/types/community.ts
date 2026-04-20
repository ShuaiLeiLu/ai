export interface CommunityPost {
  post_id: string;
  title: string;
  author: string;
  excerpt: string;
  likes: number;
  comments: number;
  created_at: string;
}

export interface CommunityComment {
  comment_id: string;
  author: string;
  content: string;
  created_at: string;
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

