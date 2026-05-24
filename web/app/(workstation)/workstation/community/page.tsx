import { redirect } from 'next/navigation';

import { routes } from '@/lib/constants/routes';

export default function CommunityPage() {
  redirect(routes.community);
}
