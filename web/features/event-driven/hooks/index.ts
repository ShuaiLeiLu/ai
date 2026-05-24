/** 题材掘金 · React Query hooks */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';

const FEATURE_KEY = 'event-driven';

export const useAccessStatus = () =>
  useQuery({
    queryKey: [FEATURE_KEY, 'access-status'],
    queryFn: api.getAccessStatus,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useThemes = () =>
  useQuery({
    queryKey: [FEATURE_KEY, 'themes'],
    queryFn: api.getThemes,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useThemeDetail = (themeId: string | undefined) =>
  useQuery({
    queryKey: [FEATURE_KEY, 'theme', themeId ?? ''],
    queryFn: () => api.getThemeDetail(themeId as string),
    enabled: Boolean(themeId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useTheySay = () =>
  useQuery({
    queryKey: [FEATURE_KEY, 'they-say'],
    queryFn: api.getTheySay,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

export const useUnlockToday = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.unlockToday,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [FEATURE_KEY, 'access-status'] });
    },
  });
};
