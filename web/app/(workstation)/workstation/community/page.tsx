import type { Metadata } from 'next';

import { CommunityPageClient } from '@/features/community/components/CommunityPageClient';

export const metadata: Metadata = {
  title: '赛博社区'
};

export default function CommunityPage() {
  return <CommunityPageClient />;
}

