import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../api';
import { TaskCreatePayload, TaskRunRecord, TaskSummary, TaskUpdatePayload } from '@/types/tasks';

const FEATURE_KEY = 'tasks';

export const useGetTasks = (filters?: api.TaskQueryFilters) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'list', filters ?? {}],
    queryFn: () => api.getTasks(filters),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
};

export const useCreateTask = () => {
  const queryClient = useQueryClient();
  return useMutation<TaskSummary, Error, TaskCreatePayload>({
    mutationFn: api.createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEATURE_KEY] });
    }
  });
};

export const useUpdateTask = () => {
  const queryClient = useQueryClient();
  return useMutation<TaskSummary, Error, { taskId: string; payload: TaskUpdatePayload }>({
    mutationFn: ({ taskId, payload }) => api.updateTask(taskId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEATURE_KEY] });
    }
  });
};

export const useDeleteTask = () => {
  const queryClient = useQueryClient();
  return useMutation<TaskSummary, Error, string>({
    mutationFn: api.deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEATURE_KEY] });
    }
  });
};

export const useActivateTask = () => {
  const queryClient = useQueryClient();
  return useMutation<TaskSummary, Error, string>({
    mutationFn: api.activateTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEATURE_KEY] });
    }
  });
};

export const usePauseTask = () => {
  const queryClient = useQueryClient();
  return useMutation<TaskSummary, Error, string>({
    mutationFn: api.pauseTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEATURE_KEY] });
    }
  });
};

export const useRunTaskOnce = () => {
  const queryClient = useQueryClient();
  return useMutation<TaskRunRecord, Error, string>({
    mutationFn: api.runTaskOnce,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FEATURE_KEY] });
    }
  });
};

export const useGetTaskRuns = (taskId?: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'runs', taskId ?? 'all'],
    queryFn: () => api.getTaskRuns(taskId),
    enabled: options?.enabled ?? true
  });
};

export const useGetTaskRunsByTask = (taskId: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'task-runs', taskId],
    queryFn: () => api.getTaskRunsByTask(taskId),
    enabled: options?.enabled ?? false
  });
};

export const useGetTaskRunLogs = (runId: string, options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: [FEATURE_KEY, 'logs', runId],
    queryFn: () => api.getTaskRunLogs(runId),
    enabled: options?.enabled ?? false
  });
};
