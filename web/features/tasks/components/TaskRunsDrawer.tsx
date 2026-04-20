'use client';

import { useState } from 'react';
import { Button, Drawer, Empty, List, Skeleton, Tag } from 'antd';

import { useGetTaskRunsByTask } from '@/features/tasks/hooks';
import { TaskRunRecord, TaskSummary } from '@/types/tasks';
import { TaskRunLogsModal } from './TaskRunLogsModal';

interface TaskRunsDrawerProps {
  open: boolean;
  onClose: () => void;
  task: TaskSummary | null;
}

function formatDate(value: string | null): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN');
}

export function TaskRunsDrawer({ open, onClose, task }: TaskRunsDrawerProps) {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data, isLoading } = useGetTaskRunsByTask(task?.task_id ?? '', {
    enabled: Boolean(task && open)
  });

  return (
    <>
      <Drawer
        title={task ? `执行历史 · ${task.title}` : '执行历史'}
        styles={{ wrapper: { width: 700 } }}
        open={open}
        onClose={onClose}
        destroyOnHidden
      >
        {isLoading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}

        {!isLoading && (!data || data.length === 0) ? (
          <Empty description="暂无执行记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : null}

        {!isLoading && data && data.length > 0 ? (
          <List
            dataSource={data}
            renderItem={(run: TaskRunRecord) => (
              <List.Item
                actions={[
                  <Button key={run.run_id} size="small" onClick={() => setSelectedRunId(run.run_id)}>
                    查看日志
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={
                    <div className="flex items-center gap-2">
                      <Tag color={run.status === 'FAILED' ? 'error' : 'blue'}>{run.status}</Tag>
                      <span>{run.run_id}</span>
                    </div>
                  }
                  description={
                    <div className="space-y-1 text-xs text-slate-500">
                      <div>触发：{formatDate(run.trigger_time)}</div>
                      <div>开始：{formatDate(run.start_time)}</div>
                      <div>结束：{formatDate(run.end_time)}</div>
                      <div>输出类型：{run.result_type}</div>
                      {run.error_message ? <div className="text-rose-500">错误：{run.error_message}</div> : null}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        ) : null}
      </Drawer>

      <TaskRunLogsModal
        open={Boolean(selectedRunId)}
        onClose={() => setSelectedRunId(null)}
        runId={selectedRunId}
      />
    </>
  );
}
