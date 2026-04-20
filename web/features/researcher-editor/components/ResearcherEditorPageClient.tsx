'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { Route } from 'next';
import {
  Alert,
  Button,
  Card,
  Divider,
  Empty,
  Input,
  Select,
  Skeleton,
  Space,
  Tag,
  Typography,
  message
} from 'antd';
import { PlusOutlined, SaveOutlined, SendOutlined } from '@ant-design/icons';

import {
  useCreateResearcher,
  useKnowledgeBaseOptions,
  useMcpServerOptions,
  useResearcherDetail,
  useSkillOptions,
  useTestChatWithResearcher,
  useUpdateResearcher
} from '@/features/researcher-editor/hooks';
import { usePublishResearcher, useUnpublishResearcher } from '@/features/researcher-market/hooks';
import { routes } from '@/lib/constants/routes';
import { ResearcherCreatePayload, ResearcherUpdatePayload, ResearcherVisibility } from '@/types/researcher';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  time: string;
}

interface EditorFormState {
  name: string;
  title: string;
  style: string;
  description: string;
  prompt: string;
  visibility: ResearcherVisibility;
  skills: string[];
  knowledge_bases: string[];
  mcp_servers: string[];
  self_drive_tasks: string[];
}

const initialFormState: EditorFormState = {
  name: '',
  title: '自定义研究员',
  style: '均衡',
  description: '',
  prompt: '',
  visibility: 'draft',
  skills: [],
  knowledge_bases: [],
  mcp_servers: [],
  self_drive_tasks: []
};

export function ResearcherEditorPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [messageApi, messageContext] = message.useMessage();
  const [form, setForm] = useState<EditorFormState>(initialFormState);
  const [taskDraft, setTaskDraft] = useState('');
  const [testQuestion, setTestQuestion] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [dirty, setDirty] = useState(false);
  const [loadedId, setLoadedId] = useState<string>();

  const researcherId = searchParams.get('id') ?? undefined;
  const isEditing = Boolean(researcherId);

  const detailQuery = useResearcherDetail(researcherId);
  const skillsQuery = useSkillOptions();
  const knowledgeBasesQuery = useKnowledgeBaseOptions();
  const mcpServersQuery = useMcpServerOptions();
  const createMutation = useCreateResearcher();
  const updateMutation = useUpdateResearcher();
  const publishMutation = usePublishResearcher();
  const unpublishMutation = useUnpublishResearcher();
  const testChatMutation = useTestChatWithResearcher();

  useEffect(() => {
    if (!detailQuery.data || loadedId === detailQuery.data.researcher_id) return;
    setForm({
      name: detailQuery.data.name,
      title: detailQuery.data.title,
      style: detailQuery.data.style,
      description: detailQuery.data.description,
      prompt: detailQuery.data.prompt,
      visibility: detailQuery.data.visibility,
      skills: detailQuery.data.skills,
      knowledge_bases: detailQuery.data.knowledge_bases,
      mcp_servers: detailQuery.data.mcp_servers,
      self_drive_tasks: detailQuery.data.self_drive_tasks
    });
    setLoadedId(detailQuery.data.researcher_id);
    setDirty(false);
  }, [detailQuery.data, loadedId]);

  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  const optionLoading = skillsQuery.isLoading || knowledgeBasesQuery.isLoading || mcpServersQuery.isLoading;
  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    publishMutation.isPending ||
    unpublishMutation.isPending ||
    testChatMutation.isPending;

  const skillOptions = useMemo(
    () => (skillsQuery.data ?? []).map((item) => ({ label: item.name, value: item.id })),
    [skillsQuery.data]
  );
  const knowledgeBaseOptions = useMemo(
    () => (knowledgeBasesQuery.data ?? []).map((item) => ({ label: item.name, value: item.id })),
    [knowledgeBasesQuery.data]
  );
  const mcpOptions = useMemo(
    () => (mcpServersQuery.data ?? []).map((item) => ({ label: item.name, value: item.id })),
    [mcpServersQuery.data]
  );

  const setField = <K extends keyof EditorFormState>(key: K, value: EditorFormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const validateBase = (): boolean => {
    if (!form.name.trim()) {
      messageApi.warning('研究员名称不能为空');
      return false;
    }
    if (!form.description.trim()) {
      messageApi.warning('研究员介绍不能为空');
      return false;
    }
    if (!form.prompt.trim()) {
      messageApi.warning('提示词不能为空');
      return false;
    }
    if (form.self_drive_tasks.length > 10) {
      messageApi.warning('自驱任务最多 10 项');
      return false;
    }
    return true;
  };

  const saveResearcher = async () => {
    if (!validateBase()) return;
    try {
      if (!researcherId) {
        const payload: ResearcherCreatePayload = {
          name: form.name.trim(),
          title: form.title.trim(),
          style: form.style.trim(),
          description: form.description.trim(),
          prompt: form.prompt,
          visibility: form.visibility,
          skills: form.skills,
          knowledge_bases: form.knowledge_bases,
          mcp_servers: form.mcp_servers,
          self_drive_tasks: form.self_drive_tasks
        };
        const created = await createMutation.mutateAsync(payload);
        setDirty(false);
        messageApi.success('研究员创建成功');
        router.replace(`${routes.researcherEditor}?id=${created.researcher_id}` as Route);
        return;
      }

      const payload: ResearcherUpdatePayload = {
        title: form.title.trim(),
        style: form.style.trim(),
        description: form.description.trim(),
        prompt: form.prompt,
        visibility: form.visibility,
        skills: form.skills,
        knowledge_bases: form.knowledge_bases,
        mcp_servers: form.mcp_servers,
        self_drive_tasks: form.self_drive_tasks
      };
      await updateMutation.mutateAsync({ researcherId, payload });
      setDirty(false);
      messageApi.success('研究员保存成功');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '保存失败');
    }
  };

  const publishOrUnpublish = async () => {
    if (!researcherId) {
      messageApi.warning('请先保存研究员');
      return;
    }
    try {
      if (form.visibility === 'public') {
        await unpublishMutation.mutateAsync(researcherId);
        setField('visibility', 'private');
        messageApi.success('已下架');
      } else {
        await publishMutation.mutateAsync(researcherId);
        setField('visibility', 'public');
        messageApi.success('发布成功');
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '操作失败');
    }
  };

  const sendTestQuestion = async () => {
    const question = testQuestion.trim();
    if (!question) return;
    if (!researcherId) {
      messageApi.warning('请先保存研究员再测试对话');
      return;
    }

    const now = new Date().toLocaleTimeString();
    setChatMessages((prev) => [...prev, { role: 'user', content: question, time: now }]);
    setTestQuestion('');
    try {
      const result = await testChatMutation.mutateAsync({
        researcherId,
        payload: { question }
      });
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: result.answer,
          time: new Date(result.reply_time).toLocaleTimeString()
        }
      ]);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '测试失败');
    }
  };

  if (isEditing && detailQuery.isLoading) {
    return <Skeleton active paragraph={{ rows: 10 }} />;
  }

  if (isEditing && detailQuery.isError) {
    return <Empty description="研究员详情加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div className="space-y-4">
      {messageContext}
      <Card
        title={isEditing ? '研究员编辑器' : '创建研究员'}
        extra={
          <Space>
            <Button onClick={() => router.push(routes.researcherMarket as Route)}>返回人才市场</Button>
            <Button type="primary" icon={<SaveOutlined />} loading={busy} onClick={saveResearcher}>
              保存
            </Button>
            <Button loading={busy} onClick={publishOrUnpublish}>
              {form.visibility === 'public' ? '下架' : '发布'}
            </Button>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary">
          配置研究员的提示词、能力挂载与自驱任务；保存草稿后可进行测试并发布到人才市场。
        </Typography.Paragraph>

        {dirty ? (
          <Alert
            type="warning"
            showIcon
            className="!mb-4"
            message="存在未保存改动"
            description="你有尚未保存的修改，离开页面可能会丢失。"
          />
        ) : null}

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card size="small" title="基本信息">
            <Space direction="vertical" className="w-full" size={12}>
              <div>
                <Typography.Text>研究员名称</Typography.Text>
                <Input
                  value={form.name}
                  disabled={isEditing}
                  placeholder="请输入研究员名称"
                  onChange={(event) => setField('name', event.target.value)}
                />
              </div>
              <div>
                <Typography.Text>标题</Typography.Text>
                <Input value={form.title} placeholder="如：中线择时专家" onChange={(event) => setField('title', event.target.value)} />
              </div>
              <div>
                <Typography.Text>风格</Typography.Text>
                <Input value={form.style} placeholder="如：技术分析+事件驱动" onChange={(event) => setField('style', event.target.value)} />
              </div>
              <div>
                <Typography.Text>介绍</Typography.Text>
                <Input.TextArea
                  rows={3}
                  value={form.description}
                  placeholder="请输入研究员介绍"
                  onChange={(event) => setField('description', event.target.value)}
                />
              </div>
              <div>
                <Typography.Text>可见性</Typography.Text>
                <Select
                  value={form.visibility}
                  options={[
                    { label: '草稿', value: 'draft' },
                    { label: '私有', value: 'private' },
                    { label: '公开', value: 'public' }
                  ]}
                  onChange={(value) => setField('visibility', value)}
                />
              </div>
            </Space>
          </Card>

          <Card size="small" title="提示词设定">
            <Typography.Text type="secondary" className="!mb-2 block">
              建议包含：研究目标、分析框架、风控要求、输出格式。
            </Typography.Text>
            <Input.TextArea
              rows={16}
              value={form.prompt}
              placeholder="请输入研究员系统提示词"
              onChange={(event) => setField('prompt', event.target.value)}
            />
          </Card>
        </div>

        <Divider />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card size="small" title="技能挂载" loading={optionLoading}>
            <Select
              mode="multiple"
              allowClear
              maxCount={25}
              value={form.skills}
              options={skillOptions}
              placeholder="选择技能"
              style={{ width: '100%' }}
              onChange={(value) => setField('skills', value)}
            />
          </Card>
          <Card size="small" title="知识库挂载" loading={optionLoading}>
            <Select
              mode="multiple"
              allowClear
              value={form.knowledge_bases}
              options={knowledgeBaseOptions}
              placeholder="选择知识库"
              style={{ width: '100%' }}
              onChange={(value) => setField('knowledge_bases', value)}
            />
          </Card>
          <Card size="small" title="MCP 服务挂载" loading={optionLoading}>
            <Select
              mode="multiple"
              allowClear
              value={form.mcp_servers}
              options={mcpOptions}
              placeholder="选择 MCP 服务"
              style={{ width: '100%' }}
              onChange={(value) => setField('mcp_servers', value)}
            />
          </Card>
        </div>

        <Divider />

        <Card size="small" title="自驱任务">
          <Space.Compact className="w-full">
            <Input
              value={taskDraft}
              placeholder="新增自驱任务（例如：盘前检查行业强弱）"
              onChange={(event) => setTaskDraft(event.target.value)}
            />
            <Button
              icon={<PlusOutlined />}
              onClick={() => {
                const value = taskDraft.trim();
                if (!value) return;
                if (form.self_drive_tasks.length >= 10) {
                  messageApi.warning('自驱任务最多 10 项');
                  return;
                }
                setField('self_drive_tasks', [...form.self_drive_tasks, value]);
                setTaskDraft('');
              }}
            >
              添加
            </Button>
          </Space.Compact>
          <div className="mt-3 flex flex-wrap gap-2">
            {form.self_drive_tasks.length === 0 ? (
              <Typography.Text type="secondary">暂无任务</Typography.Text>
            ) : (
              form.self_drive_tasks.map((task, index) => (
                <Tag
                  key={`${task}-${index}`}
                  closable
                  onClose={() =>
                    setField(
                      'self_drive_tasks',
                      form.self_drive_tasks.filter((_, currentIndex) => currentIndex !== index)
                    )
                  }
                >
                  {task}
                </Tag>
              ))
            )}
          </div>
        </Card>

        <Divider />

        <Card size="small" title="测试对话">
          <Space.Compact className="w-full">
            <Input
              value={testQuestion}
              placeholder="输入测试问题，例如：今天盘前如何做仓位规划？"
              onChange={(event) => setTestQuestion(event.target.value)}
              onPressEnter={sendTestQuestion}
            />
            <Button type="primary" icon={<SendOutlined />} loading={testChatMutation.isPending} onClick={sendTestQuestion}>
              发送
            </Button>
          </Space.Compact>

          <div className="mt-3 space-y-3">
            {chatMessages.length === 0 ? (
              <Typography.Text type="secondary">暂无测试记录</Typography.Text>
            ) : (
              chatMessages.map((item, index) => (
                <div
                  key={`${item.role}-${index}-${item.time}`}
                  className={`rounded border p-3 ${item.role === 'assistant' ? 'bg-slate-50' : 'bg-white'}`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <Typography.Text strong>{item.role === 'assistant' ? '研究员' : '你'}</Typography.Text>
                    <Typography.Text type="secondary" className="!text-xs">
                      {item.time}
                    </Typography.Text>
                  </div>
                  <Typography.Paragraph className="!mb-0 whitespace-pre-wrap">{item.content}</Typography.Paragraph>
                </div>
              ))
            )}
          </div>
        </Card>
      </Card>
    </div>
  );
}
