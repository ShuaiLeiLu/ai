import type { Metadata } from 'next';

import { KnowledgeBasePageClient } from '@/features/ecosystem/components/KnowledgeBasePageClient';

export const metadata: Metadata = {
  title: '我的知识库',
};

export default function KnowledgeBasePage() {
  return <KnowledgeBasePageClient />;
}
