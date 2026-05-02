import { http } from '@/lib/request/http-client';
import { ApiResponse, ListResponse } from '@/types/api';
import {
  TaskCreatePayload,
  TaskLifecycleStatus,
  TaskRunLog,
  TaskRunRecord,
  TaskScheduleType,
  TaskSummary,
  TaskUpdatePayload
} from '@/types/tasks';

const TASKS_API_BASE = '/tasks';

export interface TaskQueryFilters {
  status?: TaskLifecycleStatus;
  schedule_type?: TaskScheduleType;
}

function queryString(filters?: TaskQueryFilters): string {
  if (!filters) return '';
  const search = new URLSearchParams();
  if (filters.status) search.set('status', filters.status);
  if (filters.schedule_type) search.set('schedule_type', filters.schedule_type);
  const text = search.toString();
  return text ? `?${text}` : '';
}

export const getTasks = (filters?: TaskQueryFilters): Promise<TaskSummary[]> => {
  return http<ApiResponse<ListResponse<TaskSummary>>>(`${TASKS_API_BASE}${queryString(filters)}`).then(
    (res) => res.data.items
  );
};

export const createTask = (payload: TaskCreatePayload): Promise<TaskSummary> => {
  return http<ApiResponse<TaskSummary>>(TASKS_API_BASE, {
    method: 'POST',
    body: JSON.stringify(payload)
  }).then((res) => res.data);
};

export const updateTask = (taskId: string, payload: TaskUpdatePayload): Promise<TaskSummary> => {
  return http<ApiResponse<TaskSummary>>(`${TASKS_API_BASE}/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  }).then((res) => res.data);
};

export const deleteTask = (taskId: string): Promise<TaskSummary> => {
  return http<ApiResponse<TaskSummary>>(`${TASKS_API_BASE}/${taskId}`, {
    method: 'DELETE'
  }).then((res) => res.data);
};

export const activateTask = (taskId: string): Promise<TaskSummary> => {
  return http<ApiResponse<TaskSummary>>(`${TASKS_API_BASE}/${taskId}/activate`, {
    method: 'POST'
  }).then((res) => res.data);
};

export const pauseTask = (taskId: string): Promise<TaskSummary> => {
  return http<ApiResponse<TaskSummary>>(`${TASKS_API_BASE}/${taskId}/pause`, {
    method: 'POST'
  }).then((res) => res.data);
};

export const runTaskOnce = (taskId: string): Promise<TaskRunRecord> => {
  return http<ApiResponse<TaskRunRecord>>(`${TASKS_API_BASE}/${taskId}/run`, {
    method: 'POST'
  }).then((res) => res.data);
};

export const getTaskRuns = (taskId?: string): Promise<TaskRunRecord[]> => {
  const suffix = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
  return http<ApiResponse<ListResponse<TaskRunRecord>>>(`${TASKS_API_BASE}/runs${suffix}`).then(
    (res) => res.data.items
  );
};

export const getTaskRunsByTask = (taskId: string): Promise<TaskRunRecord[]> => {
  return http<ApiResponse<ListResponse<TaskRunRecord>>>(`${TASKS_API_BASE}/${taskId}/runs`).then(
    (res) => res.data.items
  );
};

export const getTaskRunLogs = (runId: string): Promise<TaskRunLog[]> => {
  return http<ApiResponse<ListResponse<TaskRunLog>>>(`${TASKS_API_BASE}/runs/${runId}/logs`).then(
    (res) => res.data.items
  );
};
