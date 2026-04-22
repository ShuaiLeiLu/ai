import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';
import { ResearcherCreatePayload, ResearcherTestChatRequest, ResearcherUpdatePayload } from '@/types/researcher';

const featureKey = 'researcher-editor';
const marketFeatureKey = 'researcher-market';

export const useResearcherDetail = (researcherId?: string) => {
  return useQuery({
    queryKey: [featureKey, 'detail', researcherId ?? 'new'],
    queryFn: () => api.getResearcherDetail(researcherId as string),
    enabled: Boolean(researcherId),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

export const useSkillOptions = () => {
  return useQuery({
    queryKey: [featureKey, 'options', 'skills'],
    queryFn: api.listSkillOptions,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
};

export const useKnowledgeBaseOptions = () => {
  return useQuery({
    queryKey: [featureKey, 'options', 'knowledge-bases'],
    queryFn: api.listKnowledgeBaseOptions,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
};

export const useMcpServerOptions = () => {
  return useQuery({
    queryKey: [featureKey, 'options', 'mcp-servers'],
    queryFn: api.listMcpServerOptions,
    staleTime: 120_000,
    refetchOnWindowFocus: false,
  });
};

export const useCreateResearcher = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ResearcherCreatePayload) => api.createResearcher(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [featureKey] });
      queryClient.invalidateQueries({ queryKey: [marketFeatureKey] });
    }
  });
};

export const useUpdateResearcher = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ researcherId, payload }: { researcherId: string; payload: ResearcherUpdatePayload }) =>
      api.updateResearcher(researcherId, payload),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: [featureKey, 'detail', vars.researcherId] });
      queryClient.invalidateQueries({ queryKey: [marketFeatureKey] });
    }
  });
};

export const useTestChatWithResearcher = () => {
  return useMutation({
    mutationFn: ({ researcherId, payload }: { researcherId: string; payload: ResearcherTestChatRequest }) =>
      api.testChatWithResearcher(researcherId, payload)
  });
};
