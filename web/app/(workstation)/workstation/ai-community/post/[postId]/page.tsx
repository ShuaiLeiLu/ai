import type { Metadata } from 'next';

import { CommunityPostDetailPageClient } from '@/features/community/components/CommunityPageClient';

export const metadata: Metadata = {
  title: '帖子详情',
};

export default function AiCommunityPostPage({
  params,
}: {
  params: { postId: string };
}) {
  return <CommunityPostDetailPageClient postId={params.postId} />;
}
