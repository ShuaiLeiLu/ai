'use client';

import { useQuery } from '@tanstack/react-query';

import { getHealth } from '@/features/health/api/get-health';

export function useHealthQuery() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: getHealth,
    staleTime: 30_000
  });
}
