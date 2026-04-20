import type { Metadata } from 'next';

import { DocumentsCenterPageClient } from '@/features/documents/components/DocumentsCenterPageClient';

export const metadata: Metadata = {
  title: '研究文档中心'
};

export default function DocumentsPage() {
  return <DocumentsCenterPageClient />;
}

