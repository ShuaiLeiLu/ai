import type { Metadata } from 'next';

import { SkillMarketPageClient } from '@/features/ecosystem/components/SkillMarketPageClient';

export const metadata: Metadata = {
  title: '技能市场',
};

export default function SkillMarketPage() {
  return <SkillMarketPageClient />;
}
