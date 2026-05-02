'use client';

import { useMemo } from 'react';
import { Button, Popconfirm, Space, Table, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  DeleteOutlined,
  FileTextOutlined,
  EditOutlined,
  HistoryOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  SyncOutlined
} from '@ant-design/icons';

import { TaskLifecycleStatus, TaskRunStatus, TaskSummary } from '@/types/tasks';

interface TasksTableProps {
  tasks: TaskSummary[];
  loading: boolean;
  onActivate: (taskId: string) => void;
  onPause: (taskId: string) => void;
  onRunOnce: (taskId: string) => void;
  onEdit: (task: TaskSummary) => void;
  onDelete: (taskId: string) => void;
  onShowRuns: (task: TaskSummary) => void;
}

const scheduleTypeLabel: Record<TaskSummary['schedule_type'], string> = {
  one_time: '一次性',
  interval: '间隔',
  cron: 'Cron'
};

const lifecycleStatusColor: Record<TaskLifecycleStatus, string> = {
  DRAFT: 'default',
  ACTIVE: 'blue',
  PAUSED: 'warning',
  DELETED: 'default'
};

const runStatusColor: Record<TaskRunStatus, string> = {
  PENDING: 'default',
  RUNNING: 'processing',
  SUCCESS: 'success',
  FAILED: 'error',
  SKIPPED: 'warning',
  CANCELED: 'default'
};

function formatDate(value: string | null): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN');
}

export function TasksTable({
  tasks,
  loading,
  onActivate,
  onPause,
  onRunOnce,
  onEdit,
  onDelete,
  onShowRuns
}: TasksTableProps) {
  const columns = useMemo<ColumnsType<TaskSummary>>(
    () => [
      {
        title: '任务标题',
        dataIndex: 'title',
        key: 'title',
        width: 220
      },
      {
        title: '调度',
        dataIndex: 'schedule_type',
        key: 'schedule_type',
        width: 100,
        render: (value: TaskSummary['schedule_type']) => scheduleTypeLabel[value]
      },
      {
        title: '状态',
        dataIndex: 'lifecycle_status',
        key: 'lifecycle_status',
        width: 110,
        render: (status: TaskLifecycleStatus) => <Tag color={lifecycleStatusColor[status]}>{status}</Tag>
      },
      {
        title: '下次执行',
        dataIndex: 'next_run_at',
        key: 'next_run_at',
        width: 170,
        render: (value: string | null) => formatDate(value)
      },
      {
        title: '最近结果',
        dataIndex: 'last_run_status',
        key: 'last_run_status',
        width: 110,
        render: (status: TaskRunStatus | null) => status ? <Tag color={runStatusColor[status]}>{status}</Tag> : '-'
      },
      {
        title: '最近执行',
        dataIndex: 'last_run_at',
        key: 'last_run_at',
        width: 170,
        render: (value: string | null) => formatDate(value)
      },
      {
        title: '操作',
        key: 'actions',
        width: 320,
        render: (_, task) => (
          <Space size={4}>
            {task.status === 'PAUSED' || task.status === 'DRAFT' ? (
              <Button size="small" icon={<PlayCircleOutlined />} onClick={() => onActivate(task.task_id)}>
                启用
              </Button>
            ) : (
              <Button size="small" icon={<PauseCircleOutlined />} onClick={() => onPause(task.task_id)}>
                暂停
              </Button>
            )}
            <Button size="small" icon={<SyncOutlined />} onClick={() => onRunOnce(task.task_id)}>
              执行
            </Button>
            <Tooltip title="编辑">
              <Button size="small" icon={<EditOutlined />} onClick={() => onEdit(task)} />
            </Tooltip>
            <Tooltip title="执行历史">
              <Button size="small" icon={<HistoryOutlined />} onClick={() => onShowRuns(task)} />
            </Tooltip>
            <Tooltip title="查看文档列表">
              <Button size="small" icon={<FileTextOutlined />} href="/workstation/documents" />
            </Tooltip>
            <Popconfirm title="确认删除该任务？" onConfirm={() => onDelete(task.task_id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        )
      }
    ],
    [onActivate, onDelete, onEdit, onPause, onRunOnce, onShowRuns]
  );

  return (
    <Table
      rowKey="task_id"
      columns={columns}
      dataSource={tasks}
      loading={loading}
      pagination={{ pageSize: 10 }}
      scroll={{ x: 1080 }}
    />
  );
}
