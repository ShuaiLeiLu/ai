import type { Metadata } from 'next';

import { BillingPageClient } from '@/features/billing/components/BillingPageClient';

export const metadata: Metadata = {
  title: '账户中心'
};

export default function BillingPage() {
  return <BillingPageClient />;
}

