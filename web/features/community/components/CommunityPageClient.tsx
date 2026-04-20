/**
 * 赛博社区页面 —— 帖子列表 + 分类Tab + 搜索 + 发布
 *
 * 布局参考目标站：左侧帖子内容（作者头像 + 徽章 + 标题 + 摘要），
 * 右侧互动指标（浏览/评论/点赞），顶部 Segmented 切换 全部/物价/热门。
 *
 * 数据流：
 *  - useCommunityPosts()       获取帖子列表
 *  - useCommunityPostDetail()  获取帖子详情（抽屉展示）
 *  - useCreateCommunityPost()  发布新帖子（Modal 表单）
 */
'use client';

import { useMemo, useState } from 'react';
import {
  Avatar,
  Button,
  Drawer,
  Empty,
  Input,
  Modal,
  Segmented,
  Skeleton,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  CommentOutlined,
  EyeOutlined,
  LikeOutlined,
  UserOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';

import {
  useCommunityPostDetail,
  useCommunityPosts,
  useCreateCommunityPost,
} from '@/features/community/hooks';
import type { CommunityPost } from '@/types/community';

/** 帖子分类 Tab 枚举：全部 / 物价 / 热门 */
type TabKey = 'all' | 'recommend' | 'hot';

/**
 * 单条帖子卡片
 * - 左侧：作者头像 + 名称 + 等级徽章 + 标题 + 摘要
 * - 右侧：浏览量 / 评论数 / 点赞数
 */
function PostCard({ item, onDetail }: { item: CommunityPost; onDetail: (id: string) => void }) {
  return (
    <div
      onClick={() => onDetail(item.post_id)}
      className="cursor-pointer border-b border-slate-100 px-4 py-5 transition-colors hover:bg-slate-50"
    >
      <div className="flex gap-4">
        {/* Left: content */}
        <div className="min-w-0 flex-1">
          {/* Author */}
          <div className="mb-2 flex items-center gap-2">
            <Avatar size={24} icon={<UserOutlined />} className="bg-brand-400 shrink-0" />
            <span className="text-sm font-medium text-slate-700">{item.author}</span>
            <Tag color="purple" className="!text-xs !m-0">M</Tag>
          </div>

          {/* Title */}
          <Typography.Title level={5} className="!mb-1 !text-base hover:text-brand-500">
            {item.title}
          </Typography.Title>

          {/* Excerpt */}
          <Typography.Paragraph className="!mb-0 !text-sm !text-slate-500" ellipsis={{ rows: 2 }}>
            {item.excerpt}
          </Typography.Paragraph>
        </div>

        {/* Right: stats —— 移动端隐藏，改为底部展示 */}
        <div className="hidden sm:flex shrink-0 items-start gap-4 pt-8 text-xs text-slate-400">
          <span className="flex items-center gap-1">
            <EyeOutlined /> {item.likes * 12 + item.comments * 5}
          </span>
          <span className="flex items-center gap-1">
            <CommentOutlined /> {item.comments}
          </span>
          <span className="flex items-center gap-1">
            <LikeOutlined /> {item.likes}
          </span>
        </div>
      </div>
      {/* 移动端底部 stats */}
      <div className="flex sm:hidden items-center gap-4 mt-2 text-xs text-slate-400">
        <span className="flex items-center gap-1">
          <EyeOutlined /> {item.likes * 12 + item.comments * 5}
        </span>
        <span className="flex items-center gap-1">
          <CommentOutlined /> {item.comments}
        </span>
        <span className="flex items-center gap-1">
          <LikeOutlined /> {item.likes}
        </span>
      </div>
    </div>
  );
}

/**
 * 赛博社区主组件
 * 功能：Tab 分类筛选 + 关键词搜索 + 帖子列表 + 详情抽屉 + 发帖弹窗
 */
export function CommunityPageClient() {
  const [messageApi, messageContext] = message.useMessage();

  // ── 筛选状态 ──
  const [tab, setTab] = useState<TabKey>('all');       // 当前选中的分类 Tab
  const [keyword, setKeyword] = useState('');           // 搜索关键词

  // ── 详情 & 发帖状态 ──
  const [detailId, setDetailId] = useState<string>();   // 当前查看的帖子 ID（控制抽屉）
  const [createOpen, setCreateOpen] = useState(false);  // 发帖弹窗是否打开
  const [title, setTitle] = useState('');               // 新帖标题
  const [content, setContent] = useState('');           // 新帖正文
  const [tags, setTags] = useState('');                 // 新帖标签（逗号分隔）

  const postsQuery = useCommunityPosts();
  const detailQuery = useCommunityPostDetail(detailId);
  const createMutation = useCreateCommunityPost();

  // 根据关键词 & Tab 对帖子列表做前端过滤 + 排序
  const filteredPosts = useMemo(() => {
    let posts = postsQuery.data ?? [];
    // 关键词模糊匹配标题 / 摘要
    const q = keyword.trim().toLowerCase();
    if (q) {
      posts = posts.filter(
        (item) => item.title.toLowerCase().includes(q) || item.excerpt.toLowerCase().includes(q)
      );
    }
    // "热门" Tab 按点赞数降序
    if (tab === 'hot') {
      posts = [...posts].sort((a, b) => b.likes - a.likes);
    }
    return posts;
  }, [keyword, postsQuery.data, tab]);

  /** 提交新帖子，成功后关闭弹窗并重置表单 */
  const createPost = async () => {
    if (!title.trim() || !content.trim()) {
      messageApi.warning('标题和内容不能为空');
      return;
    }
    try {
      await createMutation.mutateAsync({
        title: title.trim(),
        content: content.trim(),
        tags: tags.split(',').map((s) => s.trim()).filter(Boolean),
      });
      messageApi.success('发帖成功');
      setCreateOpen(false);
      setTitle('');
      setContent('');
      setTags('');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '发帖失败');
    }
  };

  return (
    <div>
      {messageContext}

      {/* Top bar: tabs + search + publish —— 移动端上下堆叠 */}
      <div className="mb-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Segmented
            value={tab}
            options={[
              { label: '全部', value: 'all' },
              { label: '物价', value: 'recommend' },
              { label: '热门', value: 'hot' },
            ]}
            onChange={(v) => setTab(v as TabKey)}
          />
          <Button type="primary" onClick={() => setCreateOpen(true)}>
            + 发布
          </Button>
        </div>
        <Input.Search
          allowClear
          placeholder="搜索帖子"
          className="w-full sm:!w-56"
          onSearch={(v) => setKeyword(v)}
        />
      </div>

      {/* Post list */}
      <div className="rounded-lg bg-white">
        {postsQuery.isLoading && <Skeleton active className="p-6" paragraph={{ rows: 8 }} />}

        {!postsQuery.isLoading && postsQuery.isError && (
          <div className="py-24">
            <Empty description="社区加载失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
        )}

        {!postsQuery.isLoading && !postsQuery.isError && filteredPosts.length === 0 && (
          <div className="py-24">
            <Empty description="暂无帖子" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
        )}

        {!postsQuery.isLoading &&
          filteredPosts.map((item) => (
            <PostCard key={item.post_id} item={item} onDetail={setDetailId} />
          ))}
      </div>

      {/* Detail Drawer */}
      <Drawer
        title="帖子详情"
        open={Boolean(detailId)}
        onClose={() => setDetailId(undefined)}
        styles={{ wrapper: { width: 'min(760px, 100vw)' } }}
        destroyOnHidden
      >
        {detailQuery.isLoading && <Skeleton active paragraph={{ rows: 8 }} />}
        {!detailQuery.isLoading && detailQuery.data && (
          <div className="space-y-4">
            <div>
              <Typography.Title level={4} className="!mb-1">
                {detailQuery.data.title}
              </Typography.Title>
              <Typography.Text type="secondary">
                {detailQuery.data.author} · {dayjs(detailQuery.data.created_at).format('YYYY-MM-DD HH:mm')}
              </Typography.Text>
            </div>
            <Space wrap>
              {detailQuery.data.tags.map((t) => (
                <Tag key={t} color="purple">{t}</Tag>
              ))}
            </Space>
            <Typography.Paragraph className="!mb-0 whitespace-pre-wrap">
              {detailQuery.data.content}
            </Typography.Paragraph>
          </div>
        )}
      </Drawer>

      {/* Create Modal */}
      <Modal
        title="发布帖子"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={createPost}
        confirmLoading={createMutation.isPending}
      >
        <Space direction="vertical" className="w-full" size={12}>
          <Input value={title} placeholder="标题" onChange={(e) => setTitle(e.target.value)} />
          <Input.TextArea
            rows={6}
            value={content}
            placeholder="正文内容"
            onChange={(e) => setContent(e.target.value)}
          />
          <Input
            value={tags}
            placeholder="标签，逗号分隔，例如：AI,复盘,策略"
            onChange={(e) => setTags(e.target.value)}
          />
        </Space>
      </Modal>
    </div>
  );
}

