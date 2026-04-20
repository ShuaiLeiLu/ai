'use client';

import { Alert, Empty, Modal, Skeleton } from 'antd';

import { useGetTaskRunLogs } from '@/features/tasks/hooks';

interface TaskRunLogsModalProps {
  open: boolean;
  onClose: () => void;
  runId: string | null;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN');
}

export function TaskRunLogsModal({ open, onClose, runId }: TaskRunLogsModalProps) {
  const { data, isLoading, isError, error } = useGetTaskRunLogs(runId ?? '', {
    enabled: Boolean(runId && open)
  });

  return (
    <Modal title="执行日志" open={open} onCancel={onClose} onOk={onClose} width={860} destroyOnHidden>
      {isLoading ? <Skeleton active paragraph={{ rows: 7 }} /> : null}

      {!isLoading && isError ? (
        <Alert
          type="error"
          showIcon
          message="日志加载失败"
          description={error instanceof Error ? error.message : '未知错误'}
        />
      ) : null}

      {!isLoading && !isError && (!data || data.length === 0) ? (
        <Empty description="暂无日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : null}

      {!isLoading && !isError && data && data.length > 0 ? (
        <div className="max-h-[56vh] space-y-2 overflow-y-auto">
          {data.map((log) => (
            <div key={log.log_id} className="rounded border border-slate-200 p-2 text-xs">
              <div className="mb-1 text-slate-500">
                [{log.level}] {formatDate(log.create_time)}
              </div>
              <pre className="whitespace-pre-wrap break-all text-slate-700">{log.content}</pre>
            </div>
          ))}
        </div>
      ) : null}
    </Modal>
  );
}
