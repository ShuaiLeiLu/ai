/**
 * 创建研究员 / 我的研究员页面
 *
 * 属于“极睿实验室”子页面之一，路由：/workstation/my-researchers
 * - 空态：虚线框 + “创建研究员” 按钮
 * - 有数据：研究员卡片网格（头像 + 名称 + 状态标签 + 简介 + 版本/时间）
 *
 * 数据流：useMineResearchers() hook 拉取当前用户拥有的研究员列表
 */
'use client';

import { Button, Empty, Spin, Tag, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

import { useMineResearchers } from '@/features/researcher-market/hooks';
import type { ResearcherMineItem } from '@/types/researcher';

/** 根据发布状态返回对应颜色的 Tag（已发布/已下架/草稿） */
function statusTag(item: ResearcherMineItem) {
  if (item.publish_status === 'published') return <Tag color="green">已发布</Tag>;
  if (item.publish_status === 'unpublished') return <Tag color="orange">已下架</Tag>;
  return <Tag>草稿</Tag>;
}

export function MyResearchersPageClient() {
  const { data, isLoading } = useMineResearchers();
  const isEmpty = !isLoading && (!data || data.length === 0);

  return (
    <div>
      {/* Header —— 移动端上下堆叠 */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Typography.Title level={4} className="!mb-1">
            创建研究员
          </Typography.Title>
          <Typography.Text type="secondary">
            创建和管理你的AI研究员，编辑其技能、知识库与提示词配置
          </Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />}>
          创建研究员
        </Button>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {isEmpty && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white py-24">
          <Empty
            description={
              <span className="text-slate-400">
                点击上方按钮创建你的第一个AI研究员
              </span>
            }
          />
          <Button type="primary" className="mt-4" icon={<PlusOutlined />}>
            创建研究员
          </Button>
        </div>
      )}

      {!isLoading && data && data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.map((item) => (
            <div
              key={item.id}
              className="rounded-lg border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md"
            >
              <div className="mb-3 flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-600 font-bold">
                  {item.name.charAt(0)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{item.name}</span>
                    {statusTag(item)}
                  </div>
                  <div className="text-xs text-slate-400">{item.level}</div>
                </div>
              </div>
              <Typography.Paragraph
                className="!mb-3 !text-sm !text-slate-500"
                ellipsis={{ rows: 2 }}
              >
                {item.introduction}
              </Typography.Paragraph>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>{item.version}</span>
                <span>{new Date(item.updated_at).toLocaleDateString('zh-CN')}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
