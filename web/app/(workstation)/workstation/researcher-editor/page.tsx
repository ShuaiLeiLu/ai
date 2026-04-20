import type { Metadata } from 'next';

import { ResearcherEditorPageClient } from '@/features/researcher-editor/components/ResearcherEditorPageClient';

export const metadata: Metadata = {
  title: '研究员编辑器'
};

export default function ResearcherEditorPage() {
  return <ResearcherEditorPageClient />;
}
