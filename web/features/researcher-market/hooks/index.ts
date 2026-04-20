import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'researcher-market';

export const useMarketResearchers = (params?: api.MarketQueryParams) => {
  return useQuery({
    queryKey: [featureKey, 'market', params ?? {}],
    queryFn: () => api.getMarketResearchers(params)
  });
};

export const useMarketResearcherDetail = (researcherId?: string, enabled = true) => {
  return useQuery({
    queryKey: [featureKey, 'detail', researcherId ?? 'none'],
    queryFn: () => api.getMarketResearcherDetail(researcherId as string),
    enabled: Boolean(researcherId) && enabled
  });
};

export const useMineResearchers = () => {
  return useQuery({
    queryKey: [featureKey, 'mine'],
    queryFn: api.getMyResearchers
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
