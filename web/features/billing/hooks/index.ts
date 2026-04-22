import { useQuery } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'billing';

export const useMembership = () =>
  useQuery({
    queryKey: [featureKey, 'membership'],
    queryFn: api.getMembership,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useBatteryLedger = (limit = 50) =>
  useQuery({
    queryKey: [featureKey, 'ledger', limit],
    queryFn: () => api.listBatteryLedger(limit),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

export const useBatteryPackages = () =>
  useQuery({
    queryKey: [featureKey, 'packages'],
    queryFn: api.listBatteryPackages,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });

