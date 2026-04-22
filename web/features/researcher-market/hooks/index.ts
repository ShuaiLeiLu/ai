import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'researcher-market';

export const useMarketResearchers = (params?: api.MarketQueryParams) => {
  return useQuery({
    queryKey: [featureKey, 'market', params ?? {}],
    queryFn: () => api.getMarketResearchers(params),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

export const useMarketResearcherDetail = (researcherId?: string, enabled = true) => {
  return useQuery({
    queryKey: [featureKey, 'detail', researcherId ?? 'none'],
    queryFn: () => api.getMarketResearcherDetail(researcherId as string),
    enabled: Boolean(researcherId) && enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

export const useMineResearchers = () => {
  return useQuery({
    queryKey: [featureKey, 'mine'],
    queryFn: api.getMyResearchers,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

function useMarketMutation<TArgs>(mutationFn: (args: TArgs) => Promise<void>) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, TArgs>({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [featureKey] });
    }
  });
}

export const useHireResearcher = () => useMarketMutation(api.hireResearcher);
export const useDismissResearcher = () => useMarketMutation(api.dismissResearcher);
export const useDuplicateResearcher = () => useMarketMutation(api.duplicateResearcher);
export const usePublishResearcher = () => useMarketMutation(api.publishResearcher);
export const useUnpublishResearcher = () => useMarketMutation(api.unpublishResearcher);
