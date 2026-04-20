/**
 * 我的知识库页面
 *
 * 属于“赛博实验室”子页面之一，路由：/workstation/knowledge-base
 * - 空态：虚线框 + “创建知识库” 按钮
 * - 有数据：Ant Design Table 展示知识库列表（名称 / 文档数 / 更新时间）
 *
 * 数据流：useKnowledgeBases() hook 拉取后端接口
 */
'use client';

import { Button, Empty, Table, Tag, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { useKnowledgeBases } from '@/features/ecosystem/hooks';
import type { KnowledgeBaseItem } from '@/types/ecosystem';

/** 知识库表格列定义 */
const columns: ColumnsType<KnowledgeBaseItem> = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '文档数', dataIndex: 'document_count', key: 'document_count', width: 100 },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    key: 'updated_at',
    width: 180,
    render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
  },
];

export function KnowledgeBasePageClient() {
  const { data, isLoading } = useKnowledgeBases();
  const isEmpty = !isLoading && (!data || data.length === 0);

  return (
    <div>
      {/* Header —— 移动端上下堆叠 */}
      <div className="mb-6 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Typography.Title level={4} className="!mb-1">
              我的知识库
            </Typography.Title>
            <Typography.Text type="secondary">
              创建和管理你专属的知识库，供AI研究员检索使用
            </Typography.Text>
          </div>
          <Button type="primary" icon={<PlusOutlined />}>
            创建知识库
          </Button>
        </div>
      </div>

      {/* Content */}
      {isEmpty ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white py-24">
          <Empty
            description={
              <span className="text-slate-400">
                点击上方按钮创建你的第一个知识库
              </span>
            }
          />
          <Button type="primary" className="mt-4" icon={<PlusOutlined />}>
            创建知识库
          </Button>
        </div>
      ) : (
        <div className="rounded-lg bg-white p-4">
          <Table
            rowKey="kb_id"
            columns={columns}
            dataSource={data ?? []}
            loading={isLoading}
            pagination={false}
            scroll={{ x: 480 }}
          />
        </div>
      )}
    </div>
  );
}
