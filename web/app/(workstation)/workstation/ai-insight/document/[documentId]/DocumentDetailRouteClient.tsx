'use client';

import { useRouter } from 'next/navigation';

import { DocumentDetailDialog } from '@/features/documents/components/DocumentDetailDialog';
import { routes } from '@/lib/constants/routes';

export function DocumentDetailRouteClient({ documentId }: { documentId: string }) {
  const router = useRouter();
  return (
    <DocumentDetailDialog
      documentId={documentId}
      open
      onClose={() => router.push(routes.aiResearcher)}
    />
  );
}
