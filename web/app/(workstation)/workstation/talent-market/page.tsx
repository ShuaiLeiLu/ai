import type { Metadata } from 'next';

import { TalentMarketPageClient } from '@/features/researcher-market/components/TalentMarketPageClient';

export const metadata: Metadata = {
  title: '人才市场',
};

export default function TalentMarketPage() {
  return <TalentMarketPageClient />;
}
