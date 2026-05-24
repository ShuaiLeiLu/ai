import type { Metadata } from 'next';
import Link from 'next/link';

import { routes } from '@/lib/constants/routes';

import { DocumentDetailRouteClient } from './DocumentDetailRouteClient';

export const metadata: Metadata = {
  title: '研报详情',
};

export default function AiInsightDocumentPage({
  params,
}: {
  params: { documentId: string };
}) {
  return (
    <div className="min-h-[72vh]">
      <Link
        href={routes.aiResearcher}
        className="inline-flex rounded-full border border-ink-50 bg-white px-4 py-2 text-[13px] font-semibold text-brand-700 shadow-sm hover:border-brand-200 hover:bg-brand-50"
      >
        返回 AI 研究员
      </Link>
      <DocumentDetailRouteClient documentId={params.documentId} />
    </div>
  );
}
