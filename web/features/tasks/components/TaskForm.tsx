'use client';

import { useEffect } from 'react';
import { Alert, Form, Input, InputNumber, Modal, Radio, Switch, Typography } from 'antd';

import { TaskCreatePayload, TaskScheduleType, TaskSummary } from '@/types/tasks';

interface TaskFormProps {
  open: boolean;
  onCancel: () => void;
  onOk: (values: TaskCreatePayload) => void;
  confirmLoading: boolean;
  initialValues?: TaskSummary | null;
}

const { TextArea } = Input;

const DYNAMIC_VARS_HINT =
  '可用动态变量：{{date}}、{{lastDate}}、{{nextDate}}、{{lastTradeDate}}、{{nextTradeDate}}';

function schedulePreset(task?: TaskSummary | null): {
  one_time_at?: string;
  interval_minutes?: number;
  cron_expr?: string;
} {
  const config = task?.schedule_config ?? {};
  return {
    one_time_at: typeof config.run_at === 'string' ? config.run_at : undefined,
    interval_minutes: typeof config.minutes === 'number' ? config.minutes : undefined,
    cron_expr: typeof config.expr === 'string' ? config.expr : undefined
  };
}

export function TaskForm({ open, onCancel, onOk, confirmLoading, initialValues }: TaskFormProps) {
  const [form] = Form.useForm();
  const scheduleType = Form.useWatch('schedule_type', form) as TaskScheduleType | undefined;

  useEffect(() => {
    if (!open) return;
    if (!initialValues) {
      form.resetFields();
      form.setFieldsValue({
        schedule_type: 'cron',
        researcher_id: 'r_alpha',
        trade_day_only: true,
        force_output_document: false
      });
      return;
    }
    form.setFieldsValue({
      ...initialValues,
      ...schedulePreset(initialValues)
    });
  }, [open, initialValues, form]);

  const handleSubmit = async () => {
    const values = await form.validateFields();

    let schedule_config: Record<string, unknown> = {};
    if (values.schedule_type === 'one_time') {
      schedule_config = { run_at: values.one_time_at || '' };
    } else if (values.schedule_type === 'interval') {
      schedule_config = { minutes: Number(values.interval_minutes || 0) };
    } else {
      schedule_config = { expr: values.cron_expr || '' };
    }

    const payload: TaskCreatePayload = {
      title: values.title,
      researcher_id: values.researcher_id,
      schedule_type: values.schedule_type,
      schedule_config,
      trade_day_only: Boolean(values.trade_day_only),
      force_output_document: Boolean(values.force_output_document),
      description: values.description ?? '',
      prompt_template: values.prompt_template ?? ''
    };
    onOk(payload);
  };

  return (
    <Modal
      title={initialValues ? '编辑任务' : '创建任务'}
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={confirmLoading}
      width={760}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item name="title" label="任务标题" rules={[{ required: true, message: '请输入任务标题' }]}>
          <Input />
        </Form.Item>

        <Form.Item
          name="researcher_id"
          label="研究员ID"
          rules={[{ required: true, message: '请输入研究员ID' }]}
        >
          <Input placeholder="例如 r_alpha" />
        </Form.Item>

        <Form.Item name="schedule_type" label="调度类型" rules={[{ required: true }]}> 
          <Radio.Group>
            <Radio.Button value="one_time">一次性定时</Radio.Button>
            <Radio.Button value="interval">固定间隔</Radio.Button>
            <Radio.Button value="cron">Cron</Radio.Button>
          </Radio.Group>
        </Form.Item>

        {scheduleType === 'one_time' ? (
          <Form.Item
            name="one_time_at"
            label="执行时间"
            rules={[{ required: true, message: '请输入执行时间字符串' }]}
          >
            <Input placeholder="例如 2026-04-20 09:00" />
          </Form.Item>
        ) : null}

        {scheduleType === 'interval' ? (
          <Form.Item
            name="interval_minutes"
            label="间隔分钟"
            rules={[{ required: true, message: '请输入间隔分钟' }]}
          >
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
        ) : null}

        {scheduleType === 'cron' ? (
          <Form.Item name="cron_expr" label="Cron表达式" rules={[{ required: true, message: '请输入Cron表达式' }]}>
            <Input placeholder="例如 0 8 * * 1-5" />
          </Form.Item>
        ) : null}

        <Form.Item name="description" label="任务描述">
          <TextArea rows={2} />
        </Form.Item>

        <Form.Item
          name="prompt_template"
          label="提示词模板"
          rules={[{ required: true, message: '请输入提示词模板' }]}
        >
          <TextArea rows={6} />
        </Form.Item>

        <Alert message={DYNAMIC_VARS_HINT} type="info" showIcon className="mb-4" />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Form.Item name="trade_day_only" label="仅交易日执行" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="force_output_document" label="强制输出文档" valuePropName="checked">
            <Switch />
          </Form.Item>
        </div>

        <Typography.Text type="secondary" className="text-xs">
          失败模拟：在提示词中加入 `[FAIL]` 可触发后端模拟失败路径。
        </Typography.Text>
      </Form>
    </Modal>
  );
}
