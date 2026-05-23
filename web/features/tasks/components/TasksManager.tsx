'use client';

/**
 * 任务编排（自驱任务）页面
 *
 * 视觉骨架：
 *   ① SectionHeading —— 标题 + 概览统计 + 右侧创建按钮
 *   ② StatCard ×4 —— 今日已完成 / 进行中 / 失败重试 / 平均耗时
 *   ③ 任务卡片 3 列网格 —— 每张任务一张卡，按状态着色
 *
 * 数据流保持不变：useGetTasks / useCreateTask / useUpdateTask /
 * useActivateTask / usePauseTask / useDeleteTask / useRunTaskOnce + TaskForm + TaskRunsDrawer。
 */

import { useMemo, useState } from 'react';
import { App, Button, Empty, Popconfirm, Skeleton } from 'antd';
import {
  DeleteOutlined,
  EditOutlined,
  HistoryOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  SyncOutlined
} from '@ant-design/icons';

import { SectionHeading } from '@/components/ui/section-heading';
import { StatCard } from '@/components/ui/stat-card';
import {
  useActivateTask,
  useCreateTask,
  useDeleteTask,
  useGetTasks,
  usePauseTask,
  useRunTaskOnce,
  useUpdateTask
} from '@/features/tasks/hooks';
import {
  TaskCreatePayload,
  TaskLifecycleStatus,
  TaskRunStatus,
  TaskSummary
} from '@/types/tasks';
import { TaskForm } from './TaskForm';
import { TaskRunsDrawer } from './TaskRunsDrawer';

/** 任务的"视觉态"：用于决定色带、徽章等。 */
type VisualTone = 'running' | 'success' | 'failed' | 'paused' | 'pending';

function resolveTone(task: TaskSummary): VisualTone {
  if (task.lifecycle_status === 'PAUSED' || task.lifecycle_status === 'DRAFT') return 'paused';
  if (task.last_run_status === 'RUNNING') return 'running';
  if (task.last_run_status === 'FAILED') return 'failed';
  if (task.last_run_status === 'SUCCESS') return 'success';
  return 'pending';
}

const scheduleTypeLabel: Record<TaskSummary['schedule_type'], string> = {
  one_time: '一次性',
  interval: '间隔',
  cron: 'Cron'
};

/** 顶部色带样式：根据视觉态返回 linear-gradient 类。 */
const toneAccent: Record<VisualTone, string> = {
  running: 'bg-gradient-to-br from-brand-50 to-transparent',
  success: 'bg-gradient-to-br from-up-50 to-transparent',
  failed: 'bg-gradient-to-br from-down-50 to-transparent',
  paused: 'bg-gradient-to-br from-ink-50 to-transparent',
  pending: 'bg-gradient-to-br from-gold-50 to-transparent'
};

const toneTopBorder: Record<VisualTone, string> = {
  running: 'border-t-brand-500',
  success: 'border-t-up-500',
  failed: 'border-t-down-500',
  paused: 'border-t-ink-200',
  pending: 'border-t-gold-500'
};

/** 状态徽章 chip —— 圆角、配色与令牌对齐。 */
function StatusBadge({ tone, label }: { tone: VisualTone; label: string }) {
  const cls: Record<VisualTone, string> = {
    running: 'bg-brand-50 text-brand-700',
    success: 'bg-up-50 text-up-600',
    failed: 'bg-down-50 text-down-600',
    paused: 'bg-ink-50 text-ink-400',
    pending: 'bg-gold-50 text-gold-600'
  };
  return (
    <span
      className={[
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium',
        cls[tone]
      ].join(' ')}
    >
      {tone === 'running' && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" />
      )}
      {label}
    </span>
  );
}

/** 进度条 —— 简版（基于本地任意运行进度估算的视觉占位）。 */
function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-ink-50">
      <div
        className="h-full rounded-full bg-brand-500 transition-all"
        style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
      />
    </div>
  );
}

/** 日期/相对时间，简短显示。 */
function formatDate(value: string | null): string {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/** 调度配置 → 人话描述（不能识别就退回为类型名）。 */
function scheduleDescription(task: TaskSummary): string {
  const base = scheduleTypeLabel[task.schedule_type];
  const cfg = task.schedule_config || {};
  if (task.schedule_type === 'cron' && typeof cfg.cron === 'string') {
    return `${base} · ${cfg.cron}`;
  }
  if (task.schedule_type === 'interval' && typeof cfg.interval_seconds === 'number') {
    const sec = cfg.interval_seconds as number;
    if (sec >= 3600) return `${base} · 每 ${Math.round(sec / 3600)}h`;
    if (sec >= 60) return `${base} · 每 ${Math.round(sec / 60)}min`;
    return `${base} · 每 ${sec}s`;
  }
  return base;
}

/** 按运行状态映射徽章文案。 */
function statusLabel(task: TaskSummary): string {
  if (task.lifecycle_status === 'PAUSED') return '已暂停';
  if (task.lifecycle_status === 'DRAFT') return '草稿';
  switch (task.last_run_status) {
    case 'RUNNING':
      return '运行中';
    case 'SUCCESS':
      return '已完成';
    case 'FAILED':
      return '失败';
    case 'SKIPPED':
      return '已跳过';
    case 'CANCELED':
      return '已取消';
    case 'PENDING':
      return '等待中';
    default:
      return '待执行';
  }
}

interface TaskCardProps {
  task: TaskSummary;
  onActivate: (taskId: string) => void;
  onPause: (taskId: string) => void;
  onRunOnce: (taskId: string) => void;
  onEdit: (task: TaskSummary) => void;
  onDelete: (taskId: string) => void;
  onShowRuns: (task: TaskSummary) => void;
}

/** 单张任务卡 —— 顶部色带 + 元信息 + 进度 + 操作链接。 */
function TaskCard({
  task,
  onActivate,
  onPause,
  onRunOnce,
  onEdit,
  onDelete,
  onShowRuns
}: TaskCardProps) {
  const tone = resolveTone(task);
  const isRunning = tone === 'running';
  const isPaused = tone === 'paused';
  const isFailed = tone === 'failed';

  return (
    <div
      className={[
        'flex flex-col rounded-2xl border border-ink-50 border-t-[3px] bg-white shadow-card overflow-hidden',
        toneTopBorder[tone]
      ].join(' ')}
    >
      {/* 顶部色带 header */}
      <div className={['px-5 py-3.5', toneAccent[tone]].join(' ')}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-[14.5px] font-semibold text-ink-900">{task.title}</h3>
            <div className="mt-0.5 truncate text-[11.5px] text-ink-400">
              {scheduleDescription(task)}
            </div>
          </div>
          <StatusBadge tone={tone} label={statusLabel(task)} />
        </div>
      </div>

      {/* body */}
      <div className="flex flex-1 flex-col gap-3 px-5 py-4">
        {/* 元信息 */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11.5px] text-ink-500">
          <div className="flex items-center gap-1">
            <span className="text-ink-400">交易日限制</span>
            <span className="text-ink-700">{task.trade_day_only ? '是' : '否'}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-ink-400">强制出文档</span>
            <span className="text-ink-700">{task.force_output_document ? '是' : '否'}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-ink-400">最近</span>
            <span className="tnum text-ink-700">{formatDate(task.last_run_at)}</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-ink-400">下次</span>
            <span className="tnum text-ink-700">{formatDate(task.next_run_at)}</span>
          </div>
        </div>

        {/* 进度条（运行中） */}
        {isRunning && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[11px] text-ink-400">
              <span>正在执行</span>
              <span className="tnum text-brand-600">进行中</span>
            </div>
            <ProgressBar percent={66} />
          </div>
        )}

        {/* 描述 */}
        {task.description && (
          <p className="line-clamp-2 text-[12.5px] leading-relaxed text-ink-500">{task.description}</p>
        )}

        {/* 失败提示 */}
        {isFailed && (
          <div className="rounded-lg bg-down-50 px-3 py-2 text-[11.5px] text-down-700">
            最近一次执行失败 · 建议查看执行历史定位原因
          </div>
        )}

        {/* footer 操作行 */}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-ink-25 pt-3 text-[12px]">
          <div className="flex items-center gap-2 text-ink-400">
            <span className="tnum">{formatDate(task.next_run_at)}</span>
          </div>
          <div className="flex flex-wrap items-center gap-1">
            {isFailed && (
              <Button
                type="link"
                size="small"
                className="!h-auto !px-1 !text-down-600 hover:!text-down-700"
                icon={<SyncOutlined />}
                onClick={() => onRunOnce(task.task_id)}
              >
                立即处理
              </Button>
            )}
            {isPaused ? (
              <Button
                type="link"
                size="small"
                className="!h-auto !px-1 !text-brand-600 hover:!text-brand-700"
                icon={<PlayCircleOutlined />}
                onClick={() => onActivate(task.task_id)}
              >
                重新启用
              </Button>
            ) : (
              <Button
                type="link"
                size="small"
                className="!h-auto !px-1 !text-ink-500 hover:!text-brand-600"
                icon={<PauseCircleOutlined />}
                onClick={() => onPause(task.task_id)}
              >
                暂停
              </Button>
            )}
            {!isFailed && !isPaused && (
              <Button
                type="link"
                size="small"
                className="!h-auto !px-1 !text-ink-500 hover:!text-brand-600"
                icon={<SyncOutlined />}
                onClick={() => onRunOnce(task.task_id)}
              >
                执行
              </Button>
            )}
            <Button
              type="link"
              size="small"
              className="!h-auto !px-1 !text-ink-500 hover:!text-brand-600"
              icon={<EditOutlined />}
              onClick={() => onEdit(task)}
            >
              编辑
            </Button>
            <Button
              type="link"
              size="small"
              className="!h-auto !px-1 !text-ink-500 hover:!text-brand-600"
              icon={<HistoryOutlined />}
              onClick={() => onShowRuns(task)}
            >
              详情
            </Button>
            <Popconfirm title="确认删除该任务？" onConfirm={() => onDelete(task.task_id)}>
              <Button
                type="link"
                size="small"
                danger
                className="!h-auto !px-1"
                icon={<DeleteOutlined />}
              />
            </Popconfirm>
          </div>
        </div>
      </div>
    </div>
  );
}

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

  const handleActivate = (taskId: string) =>
    activateMutation.mutate(taskId, {
      onSuccess: () => message.success('任务已启用'),
      onError: (error) => message.error(error.message || '任务启用失败')
    });

  const handlePause = (taskId: string) =>
    pauseMutation.mutate(taskId, {
      onSuccess: () => message.success('任务已暂停'),
      onError: (error) => message.error(error.message || '任务暂停失败')
    });

  const handleRunOnce = (taskId: string) =>
    runMutation.mutate(taskId, {
      onSuccess: () => message.success('任务执行已触发'),
      onError: (error) => message.error(error.message || '任务执行失败')
    });

  const handleDelete = (taskId: string) =>
    deleteMutation.mutate(taskId, {
      onSuccess: () => message.success('任务已删除'),
      onError: (error) => message.error(error.message || '任务删除失败')
    });

  const handleShowRuns = (task: TaskSummary) => {
    setSelectedTask(task);
    setDrawerOpen(true);
  };

  const rows = useMemo(() => tasksQuery.data ?? [], [tasksQuery.data]);

  // 顶部统计：基于当日 lifecycle/last_run_status 推算
  const stats = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayMs = today.getTime();

    let active = 0;
    let doneToday = 0;
    let running = 0;
    let failed = 0;
    for (const t of rows) {
      const status: TaskLifecycleStatus = t.lifecycle_status;
      if (status === 'ACTIVE') active += 1;
      const lastRunMs = t.last_run_at ? new Date(t.last_run_at).getTime() : NaN;
      const isToday = !Number.isNaN(lastRunMs) && lastRunMs >= todayMs;
      const lastStatus: TaskRunStatus | null = t.last_run_status;
      if (isToday && lastStatus === 'SUCCESS') doneToday += 1;
      if (lastStatus === 'RUNNING') running += 1;
      if (lastStatus === 'FAILED') failed += 1;
    }
    return { active, doneToday, running, failed };
  }, [rows]);

  return (
    <div className="space-y-4 sm:space-y-5">
      <SectionHeading
        title="任务编排"
        subtitle={`${stats.active} 个活跃 · ${stats.doneToday} 项今日已完成 · ${stats.failed} 个失败需处理`}
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} disabled={busy}>
            创建任务
          </Button>
        }
      />

      {/* 顶部 4 列统计 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="今日已完成" value={stats.doneToday} direction="up" />
        <StatCard
          label="进行中"
          value={stats.running}
          direction={stats.running > 0 ? 'flat' : 'flat'}
          hint={stats.running > 0 ? '运行中任务实时刷新' : '当前无运行中任务'}
        />
        <StatCard
          label="失败重试"
          value={stats.failed}
          direction={stats.failed > 0 ? 'down' : 'flat'}
          hint={stats.failed > 0 ? '需要人工介入' : '无失败'}
        />
        <StatCard label="平均耗时" value="--" unit="s" hint="近 7 日均值" />
      </div>

      {tasksQuery.isLoading ? (
        <div className="rounded-2xl border border-ink-50 bg-white p-6 shadow-card">
          <Skeleton active paragraph={{ rows: 6 }} />
        </div>
      ) : null}

      {!tasksQuery.isLoading && tasksQuery.isError ? (
        <div className="rounded-2xl border border-ink-50 bg-white p-10 shadow-card">
          <Empty description="任务列表加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </div>
      ) : null}

      {!tasksQuery.isLoading && !tasksQuery.isError ? (
        rows.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ink-100 bg-white/60 p-10 text-center">
            <Empty
              description={<span className="text-ink-400 text-sm">还没有任务，点击右上角创建第一条自驱任务</span>}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                onActivate={handleActivate}
                onPause={handlePause}
                onRunOnce={handleRunOnce}
                onEdit={openEdit}
                onDelete={handleDelete}
                onShowRuns={handleShowRuns}
              />
            ))}
          </div>
        )
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
    </div>
  );
}
