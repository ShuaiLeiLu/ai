import { useQuery } from '@tanstack/react-query';

import * as api from '../api';

const featureKey = 'ecosystem';

export const useKnowledgeBases = () =>
  useQuery({
    queryKey: [featureKey, 'knowledge-bases'],
    queryFn: api.listKnowledgeBases
  });

export const useSkills = (installed?: boolean) =>
  useQuery({
    queryKey: [featureKey, 'skills', installed ?? 'all'],
    queryFn: () => api.listSkills(installed)
  });

export const useMcpServers = () =>
  useQuery({
    queryKey: [featureKey, 'mcp-servers'],
    queryFn: api.listMcpServers
  });

