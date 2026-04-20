'use client';

import { useState } from 'react';
import {
  Button,
  Card,
  Drawer,
  Empty,
  List,
  Segmented,
  Skeleton,
  Space,
  Tag,
  Typography
} from 'antd';
import dayjs from 'dayjs';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { useDocumentDetail, useDocuments, useHotDocuments } from '@/features/documents/hooks';
import { DocumentSummary, DocumentType } from '@/types/documents';

const docTypeOptions: { label: string; value: 'all' | DocumentType }[] = [
  { label: '全部', value: 'all' },
  { label: '市场', value: 'market' },
  { label: '个股', value: 'stock' },
  { label: '行业', value: 'industry' },
  { label: '专题', value: 'topic' }
];

export function DocumentsCenterPageClient() {
  const [docType, setDocType] = useState<'all' | DocumentType>('all');
  const [selectedId, setSelectedId] = useState<string>();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const docsQuery = useDocuments(docType === 'all' ? undefined : { doc_type: docType });
  const hotQuery = useHotDocuments();
  const detailQuery = useDocumentDetail(selectedId);

  const openDetail = (item: DocumentSummary) => {
    setSelectedId(item.document_id);
    setDrawerOpen(true);
  };

  return (
    <div className="space-y-4">
      <Card
        title="研究文档中心"
        extra={
          <Segmented
            options={docTypeOptions}
            value={docType}
            onChange={(value) => setDocType(value as 'all' | DocumentType)}
          />
        }
      >
        <Typography.Paragraph type="secondary">
          汇总市场分析、个股研究、行业洞察与专题报告，支持按类型筛选与详情阅读。
        </Typography.Paragraph>

        {docsQuery.isLoading ? <Skeleton active paragraph={{ rows: 6 }} /> : null}
        {!docsQuery.isLoading && docsQuery.isError ? (
          <Empty description="文档列表加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : null}
        {!docsQuery.isLoading && !docsQuery.isError ? (
          <List
            itemLayout="vertical"
            dataSource={docsQuery.data ?? []}
            locale={{ emptyText: <Empty description="暂无文档" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
            renderItem={(item) => (
              <List.Item
                key={item.document_id}
                actions={[
                  <span key="views">浏览 {item.view_count}</span>,
                  <span key="likes">点赞 {item.like_count}</span>,
                  <Button key="open" type="link" onClick={() => openDetail(item)}>
                    查看详情
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Tag color="blue">{item.document_type}</Tag>
                      {item.symbol ? <Tag>{item.symbol}</Tag> : null}
                    </Space>
                  }
                  description={`${item.researcher_name} · ${dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}`}
                />
              </List.Item>
            )}
          />
        ) : null}
      </Card>

      <Card title="热门文档">
        {hotQuery.isLoading ? <Skeleton active paragraph={{ rows: 3 }} /> : null}
        {!hotQuery.isLoading && hotQuery.isError ? (
          <Empty description="热门文档加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : null}
        {!hotQuery.isLoading && !hotQuery.isError ? (
          <List
            dataSource={hotQuery.data ?? []}
            locale={{ emptyText: <Empty description="暂无热门文档" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
            renderItem={(item) => (
              <List.Item key={`hot-${item.document_id}`}>
                <Space className="w-full justify-between">
                  <Space>
                    <Typography.Text strong>{item.title}</Typography.Text>
                    <Tag>{item.document_type}</Tag>
                  </Space>
                  <Button size="small" onClick={() => openDetail(item)}>
                    查看
                  </Button>
                </Space>
              </List.Item>
            )}
          />
        ) : null}
      </Card>

      <Drawer
        title="文档详情"
        open={drawerOpen}
        styles={{ wrapper: { width: 820 } }}
        onClose={() => setDrawerOpen(false)}
        destroyOnHidden
      >
        {detailQuery.isLoading ? <Skeleton active paragraph={{ rows: 12 }} /> : null}
        {!detailQuery.isLoading && detailQuery.isError ? (
          <Empty description="文档详情加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : null}
        {!detailQuery.isLoading && detailQuery.data ? (
          <div className="space-y-4">
            <div>
              <Typography.Title level={4} className="!mb-1">
                {detailQuery.data.title}
              </Typography.Title>
              <Typography.Text type="secondary">
                {detailQuery.data.researcher_name} · {dayjs(detailQuery.data.created_at).format('YYYY-MM-DD HH:mm')}
              </Typography.Text>
            </div>
            <Space wrap>
              {detailQuery.data.tags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </Space>
            <div className="rounded border border-slate-200 bg-slate-50 p-4">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{detailQuery.data.content_markdown}</ReactMarkdown>
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}

