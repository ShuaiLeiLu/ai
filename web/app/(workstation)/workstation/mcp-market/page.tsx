import type { Metadata } from 'next';

import { McpMarketPageClient } from '@/features/ecosystem/components/McpMarketPageClient';

export const metadata: Metadata = {
  title: 'MCP市场',
};

export default function McpMarketPage() {
  return <McpMarketPageClient />;
}
