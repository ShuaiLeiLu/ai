import type { Metadata } from 'next';

import { MyResearchersPageClient } from '@/features/researcher-market/components/MyResearchersPageClient';

export const metadata: Metadata = {
  title: '创建研究员',
};

export default function MyResearchersPage() {
  return <MyResearchersPageClient />;
}
