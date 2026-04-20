export type TaskScheduleType = 'one_time' | 'interval' | 'cron';

export type TaskStatus =
  | 'DRAFT'
  | 'ACTIVE'
  | 'RUNNING'
  | 'SUCCESS'
  | 'FAILED'
  | 'PAUSED'
  | 'DELETED';

export type RunResultType = 'none' | 'document' | 'message';
export type RunLogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

export interface TaskSummary {
  task_id: string;
  title: string;
  researcher_id: string;
  schedule_type: TaskScheduleType;
  schedule_config: Record<string, unknown>;
  trade_day_only: boolean;
  force_output_document: boolean;
  description: string;
  prompt_template: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  dynamic_variable_hints: string[];
}

export interface TaskCreatePayload {
  title: string;
  researcher_id: string;
  schedule_type: TaskScheduleType;
  schedule_config: Record<string, unknown>;
  trade_day_only: boolean;
  force_output_document: boolean;
  description: string;
  prompt_template: string;
}

export type TaskUpdatePayload = Partial<TaskCreatePayload>;

export interface TaskRunRecord {
  run_id: string;
  task_id: string;
  trigger_time: string;
  start_time: string;
  end_time: string | null;
  status: TaskStatus;
  result_type: RunResultType;
  error_message: string | null;
}

export interface TaskRunLog {
  log_id: string;
  run_id: string;
  level: RunLogLevel;
  content: string;
  create_time: string;
}
