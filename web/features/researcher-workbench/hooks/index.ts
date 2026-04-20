import { useQuery } from '@tanstack/react-query';

import { getHiredResearchers, getHotDocuments, getPublicRank, getWorkbenchOverview } from '../api';
import { RankSortBy } from '@/types/researcher-workbench';

const featureKey = 'researcher-workbench';

export const useWorkbenchOverview = (sortBy: RankSortBy = 'today') => {
  return useQuery({
    queryKey: [featureKey, 'overview', sortBy],
    queryFn: () => getWorkbenchOverview(sortBy),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

export const useHiredResearchers = () => {
  return useQuery({
    queryKey: [featureKey, 'hired'],
    queryFn: getHiredResearchers,
    staleTime: 30_000,               // 30秒内复用缓存，不重复请求
    refetchOnWindowFocus: false,
  });
};

export const useHotDocuments = () => {
  return useQuery({
    queryKey: [featureKey, 'hot-documents'],
    queryFn: getHotDocuments,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

export const usePublicRank = (sortBy: RankSortBy) => {
  return useQuery({
    queryKey: [featureKey, 'public-rank', sortBy],
    queryFn: () => getPublicRank(sortBy),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};
