import type { Metadata } from 'next';

import { TradingPageClient } from '@/features/trading/components/TradingPageClient';

export const metadata: Metadata = {
  title: '模拟交易'
};

export default function TradingPage() {
  return <TradingPageClient />;
}

