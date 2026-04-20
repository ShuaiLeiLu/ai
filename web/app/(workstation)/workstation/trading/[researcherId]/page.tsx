'use client';

import { useParams } from 'next/navigation';

import { TradingDetailClient } from '@/features/trading/components/TradingDetailClient';

export default function TradingDetailPage() {
  const params = useParams<{ researcherId: string }>();
  return <TradingDetailClient researcherId={params.researcherId} />;
}
