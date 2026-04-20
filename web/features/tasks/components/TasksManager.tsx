'use client';

import { useMemo, useState } from 'react';
import { App, Button, Card, Empty, Skeleton, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

import {
  useActivateTask,
  useCreateTask,
  useDeleteTask,
  useGetTasks,
  usePauseTask,
  useRunTaskOnce,
  useUpdateTask
} from '@/features/tasks/hooks';
import { TaskCreatePayload, TaskSummary } from '@/types/tasks';
import { TaskForm } from './TaskForm';
import { TaskRunsDrawer } from './TaskRunsDrawer';
import { TasksTable } from './TasksTable';

export function TasksManager() {
  const { message } = App.useApp();
  const [formOpen, setFormOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskSummary | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskSummary | null>(null);

  const tasksQuery = useGetTasks();
  const createMutation = useCreateTask();
  const updateMutation = useUpdateTask();
  const deleteMutation = useDeleteTask();
  const activateMutation = useActivateTask();
  const pauseMutation = usePauseTask();
  const runMutation = useRunTaskOnce();

  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    activateMutation.isPending ||
    pauseMutation.isPending ||
    runMutation.isPending;

  const openCreate = () => {
    setEditingTask(null);
    setFormOpen(true);
  };

  const openEdit = (task: TaskSummary) => {
    setEditingTask(task);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingTask(null);
  };

  const handleSubmit = (payload: TaskCreatePayload) => {
    if (editingTask) {
      updateMutation.mutate(
        { taskId: editingTask.task_id, payload },
        {
          onSuccess: () => {
            message.success('任务更新成功');
            closeForm();
          },
          onError: (error) => message.error(error.message || '任务更新失败')
        }
      );
      return;
    }

    createMutation.mutate(payload, {
      onSuccess: () => {
        message.success('任务创建成功');
        closeForm();
      },
      onError: (error) => message.error(error.message || '任务创建失败')
    });
  };

  const rows = useMemo(() => tasksQuery.data ?? [], [tasksQuery.data]);

  return (
    <Card
      title="任务编排与自驱任务"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          创建任务
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        支持一次性、间隔、Cron 调度，支持交易日限制、强制文档输出与执行历史回溯。
      </Typography.Paragraph>

      {tasksQuery.isLoading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}

      {!tasksQuery.isLoading && tasksQuery.isError ? (
        <Empty description="任务列表加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : null}

      {!tasksQuery.isLoading && !tasksQuery.isError ? (
        <TasksTable
          tasks={rows}
          loading={busy}
          onActivate={(taskId) =>
            activateMutation.mutate(taskId, {
              onSuccess: () => message.success('任务已启用'),
              onError: (error) => message.error(error.message || '任务启用失败')
            })
          }
          onPause={(taskId) =>
            pauseMutation.mutate(taskId, {
              onSuccess: () => message.success('任务已暂停'),
              onError: (error) => message.error(error.message || '任务暂停失败')
            })
          }
          onRunOnce={(taskId) =>
            runMutation.mutate(taskId, {
              onSuccess: () => message.success('任务执行已触发'),
              onError: (error) => message.error(error.message || '任务执行失败')
            })
          }
          onEdit={openEdit}
          onDelete={(taskId) =>
            deleteMutation.mutate(taskId, {
              onSuccess: () => message.success('任务已删除'),
              onError: (error) => message.error(error.message || '任务删除失败')
            })
          }
          onShowRuns={(task) => {
            setSelectedTask(task);
            setDrawerOpen(true);
          }}
        />
      ) : null}

      <TaskForm
        open={formOpen}
        onCancel={closeForm}
        onOk={handleSubmit}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        initialValues={editingTask}
      />

      <TaskRunsDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedTask(null);
        }}
        task={selectedTask}
      />
    </Card>
  );
}
