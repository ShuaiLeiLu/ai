/**
 * 极睿社区页面 —— 帖子流 + 侧栏（话题 / 推荐关注）
 *
 * 视觉对照设计稿 13 号"社区"：
 *   主区两列：左 1fr 帖子流 / 右 280px 侧栏
 *   - 顶部 Tab 按钮组：🔥 推荐 / ⏰ 最新 / 🏆 战绩 / 💬 讨论 + 右侧 ✍️ 发帖
 *   - 帖子卡：圆形彩色头像 + 用户名 + 大V badge + 关注按钮，思源宋体标题，
 *            tag chip，战绩晒单帖内嵌 up-50 底色卡，底部互动行
 *
 * 保留：useCommunityPosts / useCommunityPostDetail / useCreateCommunityPost
 *      / Drawer / Modal 抽屉详情逻辑
 */
'use client';

import { useMemo, useState } from 'react';
import {
  Drawer,
  Empty,
  Input,
  Modal,
  Skeleton,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import dayjs from 'dayjs';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import {
  useCommunityPostDetail,
  useCommunityPosts,
  useCreateCommunityPost,
} from '@/features/community/hooks';
import type { CommunityPost } from '@/types/community';

/** 帖子分类 Tab 枚举 */
type TabKey = 'recommend' | 'latest' | 'record' | 'discuss';

const TAB_OPTIONS: { key: TabKey; emoji: string; label: string }[] = [
  { key: 'recommend', emoji: '🔥', label: '推荐' },
  { key: 'latest', emoji: '⏰', label: '最新' },
  { key: 'record', emoji: '🏆', label: '战绩' },
  { key: 'discuss', emoji: '💬', label: '讨论' },
];

/** 头像配色池（从名字首字符 hash → 颜色） */
const AVATAR_COLORS = [
  'bg-brand-600',
  'bg-gold-500',
  'bg-up-500',
  'bg-down-500',
  'bg-brand-400',
];

function avatarColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

/** Badge 工具 —— inline 类（globals.css 未定义 .badge） */
function Badge({
  tone = 'brand',
  children,
}: {
  tone?: 'brand' | 'ink' | 'up' | 'down' | 'gold';
  children: React.ReactNode;
}) {
  const map: Record<string, string> = {
    brand: 'bg-brand-50 text-brand-700',
    ink: 'bg-ink-25 text-ink-600',
    up: 'bg-up-50 text-up-600',
    down: 'bg-down-50 text-down-600',
    gold: 'bg-gold-50 text-gold-600',
  };
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[10.5px] font-medium ${map[tone]}`}
    >
      {children}
    </span>
  );
}

/** 启发式判断：是否战绩晒单帖 */
function isTrackRecord(p: CommunityPost): boolean {
  return /战绩|晒单|跑赢|收益|追平|超额|净值/.test(`${p.title} ${p.excerpt}`);
}

/** 启发式判断：是否大 V */
function isVIP(p: CommunityPost): boolean {
  return p.likes >= 80 || /研究员|分析师|私募|基金/.test(p.author);
}

/** 互动统计行 */
function ActionBar({ item }: { item: CommunityPost }) {
  const shares = Math.max(1, Math.round(item.comments / 4));
  return (
    <div className="mt-3 flex flex-wrap items-center gap-4 border-t border-dashed border-ink-25 pt-2.5 text-[12px] text-ink-400">
      <span className="tnum">👍 {item.likes}</span>
      <span className="tnum">💬 {item.comments}</span>
      <span className="tnum">🔁 {shares}</span>
      <span className="ml-auto cursor-pointer text-brand-600 hover:text-brand-700">
        🧠 AI 提炼要点
      </span>
    </div>
  );
}

/** 单条帖子卡片 */
function PostCard({
  item,
  onDetail,
}: {
  item: CommunityPost;
  onDetail: (id: string) => void;
}) {
  const firstChar = item.author.charAt(0) || 'U';
  const trackRecord = isTrackRecord(item);
  const vip = isVIP(item);

  return (
    <article
      onClick={() => onDetail(item.post_id)}
      className="cursor-pointer rounded-2xl border border-ink-50 bg-white px-5 py-4 shadow-card transition-shadow hover:shadow-md"
    >
      {/* 头部：头像 + 用户名 + badge + 关注按钮 */}
      <div className="mb-2.5 flex items-center gap-2.5">
        <div
          className={[
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[14px] font-bold text-white',
            avatarColor(item.author),
          ].join(' ')}
        >
          {firstChar}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-[13px] font-semibold text-ink-800">
              {item.author}
            </span>
            {vip && <Badge tone="gold">大V</Badge>}
            {!vip && /研究员|分析师/.test(item.author) && (
              <Badge tone="brand">研究员</Badge>
            )}
          </div>
          <div className="mt-0.5 text-[11px] text-ink-400">
            {dayjs(item.created_at).format('MM-DD HH:mm')} · {item.likes * 12} 关注
          </div>
        </div>
        <button
          type="button"
          onClick={(e) => e.stopPropagation()}
          className="rounded-full border border-brand-600 px-3 py-0.5 text-[11.5px] font-medium text-brand-600 hover:bg-brand-50"
        >
          + 关注
        </button>
      </div>

      {/* 标题 */}
      <h3 className="serif mb-1.5 text-[15px] font-bold leading-snug text-ink-900">
        {item.title}
      </h3>

      {/* 摘要 */}
      <p className="line-clamp-3 text-[12.5px] leading-relaxed text-ink-600">
        {item.excerpt}
      </p>

      {/* 标签 chip */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone="brand">#讨论</Badge>
        {trackRecord && <Badge tone="up">#战绩</Badge>}
        {vip && <Badge tone="gold">#大V</Badge>}
      </div>

      {/* 战绩晒单卡 */}
      {trackRecord && (
        <div className="mt-3 rounded-lg bg-up-50 p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <Badge tone="up">🏆 战绩晒单</Badge>
              <div className="mt-1.5 text-[12px] text-ink-700">
                近 30 日实盘收益{' '}
                <span className="tnum text-[15px] font-bold text-up-600">
                  +{(item.likes / 10 + 3.2).toFixed(2)}%
                </span>{' '}
                · 跑赢沪深 300{' '}
                <span className="tnum font-semibold text-up-600">
                  {(item.likes / 20 + 1.5).toFixed(2)}pp
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => e.stopPropagation()}
              className="shrink-0 rounded-full bg-up-500 px-3 py-1.5 text-[11.5px] font-semibold text-white hover:bg-up-600"
            >
              ⚡ 立即订阅
            </button>
          </div>
        </div>
      )}

      {/* 底部互动 */}
      <ActionBar item={item} />
    </article>
  );
}

/** 热门话题 / 推荐关注 mock 数据 */
const HOT_TOPICS = [
  { tag: '#半导体Q2业绩前瞻', count: 328 },
  { tag: '#新能源车销量回暖', count: 256 },
  { tag: '#创新药出海加速', count: 198 },
  { tag: '#红利低波再平衡', count: 152 },
];

const REC_USERS = [
  { name: '老李研究院', desc: '13.2万关注' },
  { name: '价值小马', desc: '8.7万关注' },
  { name: '量化阿熊', desc: '5.1万关注' },
];

/** 极睿社区主组件 */
export function CommunityPageClient() {
  const [messageApi, messageContext] = message.useMessage();

  // ── 筛选状态 ──
  const [tab, setTab] = useState<TabKey>('recommend');
  const [keyword, setKeyword] = useState('');

  // ── 详情 & 发帖 ──
  const [detailId, setDetailId] = useState<string>();
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');

  const postsQuery = useCommunityPosts();
  const detailQuery = useCommunityPostDetail(detailId);
  const createMutation = useCreateCommunityPost();

  // 根据关键词 & Tab 过滤排序
  const filteredPosts = useMemo(() => {
    let posts = postsQuery.data ?? [];
    const q = keyword.trim().toLowerCase();
    if (q) {
      posts = posts.filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          item.excerpt.toLowerCase().includes(q),
      );
    }
    if (tab === 'latest') {
      posts = [...posts].sort(
        (a, b) => dayjs(b.created_at).valueOf() - dayjs(a.created_at).valueOf(),
      );
    } else if (tab === 'record') {
      posts = posts.filter(isTrackRecord);
    } else if (tab === 'discuss') {
      posts = [...posts].sort((a, b) => b.comments - a.comments);
    } else {
      // recommend：点赞降序
      posts = [...posts].sort((a, b) => b.likes - a.likes);
    }
    return posts;
  }, [keyword, postsQuery.data, tab]);

  /** 提交新帖 */
  const createPost = async () => {
    if (!title.trim() || !content.trim()) {
      messageApi.warning('标题和内容不能为空');
      return;
    }
    try {
      await createMutation.mutateAsync({
        title: title.trim(),
        content: content.trim(),
        tags: tags
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
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

      <SectionHeading
        title="极睿社区"
        subtitle="和真实投资者一起讨论 · AI 帮你提炼有用信息"
      />

      {/* 两列布局 */}
      <div className="flex flex-col gap-4 lg:flex-row">
        {/* ───────── 左：帖子流 ───────── */}
        <div className="min-w-0 flex-1">
          {/* Tab 按钮组 + 发帖 */}
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <div className="flex flex-1 flex-wrap items-center gap-1.5">
              {TAB_OPTIONS.map((opt) => {
                const active = tab === opt.key;
                return (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => setTab(opt.key)}
                    className={[
                      'rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
                      active
                        ? 'bg-brand-600 text-white'
                        : 'bg-white text-ink-600 border border-ink-50 hover:border-brand-600 hover:text-brand-600',
                    ].join(' ')}
                  >
                    <span className="mr-1">{opt.emoji}</span>
                    {opt.label}
                  </button>
                );
              })}
            </div>
            <Input.Search
              allowClear
              placeholder="搜索帖子"
              className="w-full sm:!w-48"
              onSearch={(v) => setKeyword(v)}
            />
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="rounded-full bg-gold-500 px-4 py-1.5 text-[12.5px] font-semibold text-white shadow-sm hover:bg-gold-600"
            >
              ✍️ 发帖
            </button>
          </div>

          {/* 帖子列表 */}
          {postsQuery.isLoading && (
            <PageCard density="compact">
              <Skeleton active paragraph={{ rows: 8 }} />
            </PageCard>
          )}

          {!postsQuery.isLoading && postsQuery.isError && (
            <PageCard density="compact">
              <div className="py-16">
                <Empty
                  description="社区加载失败"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              </div>
            </PageCard>
          )}

          {!postsQuery.isLoading &&
            !postsQuery.isError &&
            filteredPosts.length === 0 && (
              <PageCard density="compact">
                <div className="py-16">
                  <Empty
                    description="暂无帖子"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                </div>
              </PageCard>
            )}

          {!postsQuery.isLoading && filteredPosts.length > 0 && (
            <div className="space-y-3">
              {filteredPosts.map((item) => (
                <PostCard
                  key={item.post_id}
                  item={item}
                  onDetail={setDetailId}
                />
              ))}
            </div>
          )}
        </div>

        {/* ───────── 右：侧栏 ───────── */}
        <aside className="lg:w-[280px] lg:shrink-0">
          <PageCard title="热 门 话 题" accent="gold" density="compact">
            <ul className="space-y-2.5">
              {HOT_TOPICS.map((t, i) => (
                <li
                  key={t.tag}
                  className="flex cursor-pointer items-start gap-2 hover:text-brand-600"
                >
                  <span
                    className={[
                      'tnum mt-0.5 w-4 shrink-0 text-[12px] font-semibold',
                      i < 3 ? 'text-down-500' : 'text-ink-400',
                    ].join(' ')}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="serif text-[13px] font-bold text-ink-800">
                      {t.tag}
                    </div>
                    <div className="text-[11px] text-ink-400">
                      {t.count} 讨论
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </PageCard>

          <div className="mt-4">
            <PageCard title="推 荐 关 注" accent="brand" density="compact">
              <ul className="space-y-3">
                {REC_USERS.map((u) => (
                  <li key={u.name} className="flex items-center gap-2.5">
                    <div
                      className={[
                        'flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full text-[12px] font-bold text-white',
                        avatarColor(u.name),
                      ].join(' ')}
                    >
                      {u.name.charAt(0)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[12.5px] font-semibold text-ink-800">
                        {u.name}
                      </div>
                      <div className="text-[11px] text-ink-400">{u.desc}</div>
                    </div>
                    <button
                      type="button"
                      className="shrink-0 rounded-full bg-brand-50 px-2.5 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-100"
                    >
                      关注
                    </button>
                  </li>
                ))}
              </ul>
            </PageCard>
          </div>
        </aside>
      </div>

      {/* 详情抽屉 —— 保留原逻辑 */}
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
              <Typography.Title level={4} className="!mb-1 serif">
                {detailQuery.data.title}
              </Typography.Title>
              <Typography.Text type="secondary">
                {detailQuery.data.author} ·{' '}
                {dayjs(detailQuery.data.created_at).format('YYYY-MM-DD HH:mm')}
              </Typography.Text>
            </div>
            <Space wrap>
              {detailQuery.data.tags.map((t) => (
                <Tag key={t} color="purple">
                  {t}
                </Tag>
              ))}
            </Space>
            <Typography.Paragraph className="!mb-0 whitespace-pre-wrap">
              {detailQuery.data.content}
            </Typography.Paragraph>
          </div>
        )}
      </Drawer>

      {/* 发帖弹窗 —— 保留原逻辑 */}
      <Modal
        title="发布帖子"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={createPost}
        confirmLoading={createMutation.isPending}
      >
        <Space direction="vertical" className="w-full" size={12}>
          <Input
            value={title}
            placeholder="标题"
            onChange={(e) => setTitle(e.target.value)}
          />
          <Input.TextArea
            rows={6}
            value={content}
            placeholder="正文内容"
            onChange={(e) => setContent(e.target.value)}
          />
          <Input
            value={tags}
            placeholder="标签，逗号分隔，例如:AI,复盘,策略"
            onChange={(e) => setTags(e.target.value)}
          />
        </Space>
      </Modal>
    </div>
  );
}
