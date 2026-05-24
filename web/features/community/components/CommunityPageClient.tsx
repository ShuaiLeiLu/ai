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
  message,
} from 'antd';
import dayjs from 'dayjs';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import {
  useCommunityComments,
  useCommunityMentionConfig,
  useCommunityPostDetail,
  useCommunityPosts,
  useCreateCommunityComment,
  useCreateCommunityPost,
  useDeleteCommunityComment,
  useDeleteCommunityPost,
  useSetCommunityPostFeatured,
} from '@/features/community/hooks';
import type {
  CommunityComment,
  CommunityMentionResearcher,
  CommunityPost,
  CommunityPostScope,
  CommunityPostSort,
} from '@/types/community';

/** 帖子分类 Tab 枚举 */
type TabKey = CommunityPostScope;
type UploadPreview = {
  id: string;
  name: string;
  status: 'uploading' | 'done' | 'error';
  progress: number;
};
type DeleteTarget =
  | { type: 'post'; id: string; title: string }
  | { type: 'comment'; id: string; title: string }
  | undefined;

const TAB_OPTIONS: { key: TabKey; emoji: string; label: string }[] = [
  { key: 'all', emoji: '', label: '全部' },
  { key: 'mine', emoji: '', label: '我的' },
  { key: 'hot', emoji: '🔥', label: '热门' },
  { key: 'featured', emoji: '⭐', label: '精华' },
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
      <span className="tnum">👁 {item.views}</span>
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
            {item.author_type === 'ai_researcher' && <Badge tone="brand">AI研究员</Badge>}
            {vip && <Badge tone="gold">大V</Badge>}
            {item.author_type !== 'ai_researcher' && !vip && /研究员|分析师/.test(item.author) && (
              <Badge tone="brand">研究员</Badge>
            )}
            {item.is_featured && <Badge tone="gold">精华</Badge>}
            {item.is_vip_only && <Badge tone="gold">VIP</Badge>}
          </div>
          <div className="mt-0.5 text-[11px] text-ink-400">
            {dayjs(item.created_at).format('MM-DD HH:mm')} · {item.author_level ?? `${item.likes * 12} 关注`}
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

function MentionChip({
  researcher,
  selected,
  onToggle,
}: {
  researcher: CommunityMentionResearcher;
  selected: boolean;
  onToggle: (researcher: CommunityMentionResearcher) => void;
}) {
  const firstChar = researcher.name.charAt(0) || '研';
  return (
    <button
      type="button"
      onClick={() => onToggle(researcher)}
      className={[
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] transition',
        selected
          ? 'border-brand-300 bg-white text-brand-700'
          : 'border-dashed border-brand-200 bg-brand-50 text-brand-600 hover:bg-white',
      ].join(' ')}
    >
      <span
        className={[
          'flex h-[18px] w-[18px] items-center justify-center rounded-full text-[10px] font-bold text-white',
          avatarColor(researcher.name),
        ].join(' ')}
      >
        {firstChar}
      </span>
      {researcher.name}
      {selected && <span className="text-ink-400">×</span>}
    </button>
  );
}

function CommentItem({
  comment,
  onReply,
  onDelete,
}: {
  comment: CommunityComment;
  onReply: (comment: CommunityComment) => void;
  onDelete: (comment: CommunityComment) => void;
}) {
  const isAi = comment.author_type === 'ai_researcher';
  return (
    <div className="flex gap-3">
      <div
        className={[
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold text-white',
          isAi ? 'bg-gradient-to-br from-gold-500 to-gold-600' : avatarColor(comment.author),
        ].join(' ')}
      >
        {comment.author.charAt(0) || '评'}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <b className="text-[13.5px] text-ink-800">{comment.author}</b>
          {isAi && <Badge tone="gold">AI研究员</Badge>}
          <span className="ml-auto text-[11px] text-ink-400">
            {dayjs(comment.created_at).format('MM-DD HH:mm')}
          </span>
        </div>
        <div
          className={[
            'mt-1.5 rounded-lg px-3 py-2 text-[13px] leading-relaxed text-ink-700',
            isAi ? 'border border-brand-100 bg-brand-50' : 'bg-ink-25',
          ].join(' ')}
        >
          {comment.reply_to_author && (
            <div className="mb-1 rounded bg-white/70 px-2 py-1 text-[11px] text-brand-700">
              回复 @{comment.reply_to_author}
            </div>
          )}
          {comment.content}
        </div>
        <div className="mt-1.5 flex gap-4 text-[11px] text-ink-400">
          <span className="cursor-pointer">👍 {comment.likes}</span>
          <button
            type="button"
            onClick={() => onReply(comment)}
            className="text-ink-400 hover:text-brand-600"
          >
            💬 回复
          </button>
          <button
            type="button"
            onClick={() => onDelete(comment)}
            className="text-ink-400 hover:text-up-600"
          >
            删除
          </button>
        </div>
      </div>
    </div>
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
  const [tab, setTab] = useState<TabKey>('all');
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');

  // ── 详情 & 发帖 ──
  const [detailId, setDetailId] = useState<string>();
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const [commentText, setCommentText] = useState('');
  const [replyTo, setReplyTo] = useState<CommunityComment | null>(null);
  const [selectedResearcherIds, setSelectedResearcherIds] = useState<string[]>([]);
  const [draftImages, setDraftImages] = useState<UploadPreview[]>([]);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget>();
  const [deleteReason, setDeleteReason] = useState('违反社区规范');
  const [deleteNote, setDeleteNote] = useState('');

  const postSort: CommunityPostSort = tab === 'hot' ? 'hot' : tab === 'all' && keyword.trim() ? 'hot' : 'latest';
  const postsQuery = useCommunityPosts({
    q: keyword.trim() || undefined,
    scope: tab,
    sort: postSort,
  });
  const detailQuery = useCommunityPostDetail(detailId);
  const commentsQuery = useCommunityComments(detailId);
  const mentionQuery = useCommunityMentionConfig(Boolean(detailId || createOpen));
  const createMutation = useCreateCommunityPost();
  const createCommentMutation = useCreateCommunityComment();
  const featureMutation = useSetCommunityPostFeatured();
  const deletePostMutation = useDeleteCommunityPost();
  const deleteCommentMutation = useDeleteCommunityComment();

  // 后端已经完成 scope/search/sort，前端只保留战绩晒单的视觉顺序补偿。
  const filteredPosts = useMemo(() => {
    let posts = postsQuery.data ?? [];
    posts = [...posts].sort((a, b) => Number(isTrackRecord(b)) - Number(isTrackRecord(a)));
    return posts;
  }, [postsQuery.data]);

  const selectedResearchers = useMemo(() => {
    const researchers = mentionQuery.data?.researchers ?? [];
    return researchers.filter((item) => selectedResearcherIds.includes(item.researcher_id));
  }, [mentionQuery.data?.researchers, selectedResearcherIds]);

  const comments = commentsQuery.data ?? detailQuery.data?.comment_list ?? [];
  const hasDraft = Boolean(title.trim() || content.trim() || tags.trim() || draftImages.length > 0);

  const toggleMention = (researcher: CommunityMentionResearcher) => {
    setSelectedResearcherIds((ids) => {
      const selected = ids.includes(researcher.researcher_id);
      return selected ? ids.filter((id) => id !== researcher.researcher_id) : [...ids, researcher.researcher_id];
    });
    if (!commentText.includes(`@${researcher.name}`)) {
      setCommentText((text) => `${text}${text.trim() ? ' ' : ''}@${researcher.name} `);
    }
  };

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
      setDraftImages([]);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '发帖失败');
    }
  };

  const closeCreateModal = () => {
    if (hasDraft) {
      setDiscardOpen(true);
      return;
    }
    setCreateOpen(false);
  };

  const discardDraft = () => {
    setCreateOpen(false);
    setDiscardOpen(false);
    setTitle('');
    setContent('');
    setTags('');
    setDraftImages([]);
  };

  const addDraftImages = (files: FileList | null) => {
    if (!files?.length) return;
    const allowed = ['image/jpeg', 'image/png', 'image/gif'];
    const nextFiles = Array.from(files).slice(0, Math.max(0, 9 - draftImages.length));
    if (draftImages.length + files.length > 9) {
      messageApi.warning('图片最多上传 9 张');
    }

    const previews: UploadPreview[] = nextFiles.map((file) => {
      const validType = allowed.includes(file.type);
      const validSize = file.size <= 2 * 1024 * 1024;
      return {
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        name: file.name,
        status: validType && validSize ? 'uploading' : 'error',
        progress: validType && validSize ? 68 : 100,
      };
    });

    setDraftImages((items) => [...items, ...previews]);
    window.setTimeout(() => {
      setDraftImages((items) =>
        items.map((item) =>
          previews.some((preview) => preview.id === item.id && preview.status === 'uploading')
            ? { ...item, status: 'done', progress: 100 }
            : item,
        ),
      );
    }, 900);
  };

  const createComment = async () => {
    if (!detailId || !commentText.trim()) {
      messageApi.warning('评论内容不能为空');
      return;
    }
    try {
      await createCommentMutation.mutateAsync({
        post_id: detailId,
        content: commentText.trim(),
        reply_to_id: replyTo?.comment_id ?? null,
      });
      messageApi.success('评论成功');
      setCommentText('');
      setReplyTo(null);
      setSelectedResearcherIds([]);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '评论失败');
    }
  };

  const toggleFeatured = async () => {
    if (!detailQuery.data || !detailId) return;
    try {
      await featureMutation.mutateAsync({
        postId: detailId,
        isFeatured: !detailQuery.data.is_featured,
      });
      messageApi.success(detailQuery.data.is_featured ? '已取消精华' : '已设为精华');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '无权执行精华操作');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      const payload = { reason: deleteReason, note: deleteNote.trim() || null };
      if (deleteTarget.type === 'post') {
        await deletePostMutation.mutateAsync({ postId: deleteTarget.id, payload });
        messageApi.success('删除成功');
        setDetailId(undefined);
      } else {
        await deleteCommentMutation.mutateAsync({ commentId: deleteTarget.id, payload });
        messageApi.success('删除成功');
      }
      setDeleteTarget(undefined);
      setDeleteNote('');
      setDeleteReason('违反社区规范');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '删除失败');
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
          <div className="mb-4 rounded-xl border border-ink-50 bg-white p-3 shadow-card">
            <div className="flex flex-wrap items-center gap-3">
              <div className="inline-flex rounded-[10px] bg-ink-25 p-1">
              {TAB_OPTIONS.map((opt) => {
                const active = tab === opt.key;
                return (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => setTab(opt.key)}
                    className={[
                      'rounded-lg px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
                      active
                        ? 'bg-brand-600 text-white'
                        : 'text-ink-600 hover:bg-white hover:text-brand-600',
                    ].join(' ')}
                  >
                    {opt.emoji && <span className="mr-1">{opt.emoji}</span>}
                    {opt.label}
                    {opt.key === 'mine' && (
                      <span className={active ? 'ml-1 text-white/70' : 'ml-1 text-ink-400'}>
                        {tab === 'mine' ? filteredPosts.length : ''}
                      </span>
                    )}
                  </button>
                );
              })}
              </div>
              <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-[10px] bg-ink-25 px-3 py-1.5">
                <span className="text-[13px] text-ink-400">🔍</span>
                <input
                  value={searchInput}
                  placeholder="搜索帖子、用户..."
                  onChange={(event) => setSearchInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') setKeyword(searchInput.trim());
                  }}
                  className="min-w-0 flex-1 bg-transparent text-[12.5px] text-ink-700 outline-none placeholder:text-ink-400"
                />
                {searchInput && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchInput('');
                      setKeyword('');
                    }}
                    className="text-[13px] text-ink-400 hover:text-ink-700"
                  >
                    ×
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={() => setKeyword(searchInput.trim())}
                className="rounded-full border border-brand-100 bg-brand-50 px-3.5 py-1.5 text-[12px] font-semibold text-brand-700 hover:bg-brand-100"
              >
                搜索
              </button>
              <button
                type="button"
                onClick={() => setCreateOpen(true)}
                className="ml-auto rounded-full bg-gold-500 px-4 py-1.5 text-[12.5px] font-semibold text-white shadow-sm hover:bg-gold-600"
              >
                ✍️ 发帖
              </button>
            </div>
            {keyword && (
              <div className="mt-3 rounded-r-lg border-l-[3px] border-brand-600 bg-brand-50 px-4 py-3 text-[12px] text-brand-700">
                <b>搜索结果筛选：</b>关键词「{keyword}」 · 类型 {TAB_OPTIONS.find((item) => item.key === tab)?.label ?? '全部'} · 排序 {postSort === 'hot' ? '相关度' : '最新'} · 为你找到 <b>{filteredPosts.length}</b> 条相关帖子
              </div>
            )}
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

      {/* 详情抽屉 */}
      <Drawer
        title={null}
        open={Boolean(detailId)}
        onClose={() => {
          setDetailId(undefined);
          setCommentText('');
          setSelectedResearcherIds([]);
        }}
        styles={{ wrapper: { width: 'min(860px, 100vw)' }, body: { padding: 0 } }}
        destroyOnHidden
      >
        {detailQuery.isLoading && (
          <div className="p-6">
            <Skeleton active paragraph={{ rows: 10 }} />
          </div>
        )}
        {!detailQuery.isLoading && detailQuery.isError && (
          <div className="p-10">
            <Empty description="加载帖子失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
        )}
        {!detailQuery.isLoading && detailQuery.data && (
          <div className="bg-ink-0">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-ink-50 bg-white/95 px-5 py-3 backdrop-blur">
              <button
                type="button"
                onClick={() => setDetailId(undefined)}
                className="text-[13px] font-medium text-brand-600 hover:text-brand-700"
              >
                ‹ 返回社区
              </button>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard?.writeText(
                      `${window.location.origin}/workstation/ai-community/post/${detailQuery.data.post_id}`,
                    );
                    messageApi.success('分享链接复制成功');
                  }}
                  className="rounded-full border border-ink-50 bg-white px-3 py-1 text-[11.5px] text-ink-600 hover:border-brand-200 hover:text-brand-600"
                >
                  📤 分享
                </button>
                <button
                  type="button"
                  onClick={toggleFeatured}
                  disabled={featureMutation.isPending}
                  className="rounded-full border border-ink-50 bg-white px-3 py-1 text-[11.5px] text-ink-600 hover:border-gold-200 hover:text-gold-600"
                >
                  ⭐ {detailQuery.data.is_featured ? '取消精华' : '设为精华'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setDeleteTarget({
                      type: 'post',
                      id: detailQuery.data.post_id,
                      title: detailQuery.data.title,
                    })
                  }
                  className="rounded-full border border-up-100 bg-white px-3 py-1 text-[11.5px] text-up-600 hover:bg-up-50"
                >
                  🗑 删除
                </button>
              </div>
            </div>

            <article className="mx-auto max-w-[800px] px-5 py-5 sm:px-7">
              <h1 className="serif text-[24px] font-bold leading-snug text-ink-900">
                {detailQuery.data.title}
              </h1>

              <div className="mt-4 flex items-center gap-3 border-b border-ink-50 pb-4">
                <div
                  className={[
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[14px] font-bold text-white',
                    avatarColor(detailQuery.data.author),
                  ].join(' ')}
                >
                  {detailQuery.data.author.charAt(0) || '用'}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <b className="text-[13.5px] text-ink-800">{detailQuery.data.author}</b>
                    {detailQuery.data.author_type === 'ai_researcher' && <Badge tone="gold">AI研究员</Badge>}
                    {detailQuery.data.author_level && <Badge tone="brand">{detailQuery.data.author_level}</Badge>}
                    {detailQuery.data.is_vip_only && <Badge tone="gold">VIP专属</Badge>}
                  </div>
                  <div className="mt-0.5 text-[11px] text-ink-400">
                    {dayjs(detailQuery.data.created_at).format('YYYY-MM-DD HH:mm')} · 👁 {detailQuery.data.views} 浏览 · 💬 {detailQuery.data.comments} 评论
                  </div>
                </div>
              </div>

              <div className="mt-4 whitespace-pre-wrap text-[14px] leading-[1.95] text-ink-800">
                {detailQuery.data.content}
              </div>

              <Space wrap className="mt-4">
                {detailQuery.data.tags.map((t) => (
                  <Tag key={t} color="green">
                    #{t}
                  </Tag>
                ))}
              </Space>

              <div className="mt-5 flex flex-wrap items-center gap-5 border-y border-dashed border-ink-50 py-3 text-[13px] text-ink-500">
                <span className="cursor-pointer">👍 {detailQuery.data.likes}</span>
                <span className="cursor-pointer">💬 {detailQuery.data.comments}</span>
                <span className="cursor-pointer">🔁 {Math.max(1, Math.round(detailQuery.data.comments / 3))}</span>
                <span className="ml-auto cursor-pointer text-brand-600">🧠 AI 提炼要点</span>
              </div>

              <section className="mt-6">
                <div className="serif text-[17px] font-bold text-ink-900">全部评论（{comments.length}）</div>

                <div className="mt-3 rounded-xl bg-ink-25 p-3">
                  <Input.TextArea
                    rows={3}
                    value={commentText}
                    placeholder="留下你的评论 · 输入 @ 可强制召唤研究员回复"
                    onChange={(e) => setCommentText(e.target.value)}
                    className="!border-0 !bg-transparent !shadow-none"
                  />
                  {replyTo && (
                    <div className="mt-2 flex items-center justify-between rounded-lg bg-white px-3 py-2 text-[12px] text-ink-500">
                      <span className="min-w-0 truncate">正在回复 @{replyTo.author}</span>
                      <button
                        type="button"
                        onClick={() => setReplyTo(null)}
                        className="ml-2 shrink-0 text-ink-400 hover:text-ink-700"
                      >
                        取消
                      </button>
                    </div>
                  )}

                  {(mentionQuery.data?.researchers.length ?? 0) > 0 && (
                    <div className="mt-2 rounded-lg border border-brand-100 bg-brand-50 p-2.5">
                      <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-brand-700">
                        🤖 @ 召唤研究员
                        {selectedResearchers.length > 0 && (
                          <span className="font-normal text-ink-500">
                            已选择 {selectedResearchers.length} 位
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {(mentionQuery.data?.researchers ?? []).slice(0, 6).map((researcher) => (
                          <MentionChip
                            key={researcher.researcher_id}
                            researcher={researcher}
                            selected={selectedResearcherIds.includes(researcher.researcher_id)}
                            onToggle={toggleMention}
                          />
                        ))}
                      </div>
                      <div className="mt-2 text-[11px] text-ink-500">
                        被 @ 的研究员可参与回复，提交前请确认问题清晰。
                      </div>
                    </div>
                  )}

                  <div className="mt-2 flex items-center justify-between">
                    <div className="flex gap-4 text-[11px] text-ink-400">
                      <span className="cursor-pointer">📷 图片</span>
                      <span className="cursor-pointer">🤖 @ 召唤研究员</span>
                    </div>
                    <button
                      type="button"
                      onClick={createComment}
                      disabled={createCommentMutation.isPending}
                      className="rounded-full bg-brand-600 px-4 py-1.5 text-[12px] font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {createCommentMutation.isPending ? '发布中...' : '发表评论'}
                    </button>
                  </div>
                </div>

                <div className="mt-5 space-y-5">
                  {commentsQuery.isLoading && <Skeleton active paragraph={{ rows: 5 }} />}
                  {commentsQuery.isError && (
                    <Empty description="加载评论失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  )}
                  {!commentsQuery.isLoading && !commentsQuery.isError && comments.length === 0 && (
                    <Empty description="暂无评论" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  )}
                  {!commentsQuery.isLoading &&
                    !commentsQuery.isError &&
                    comments.map((comment) => (
                      <CommentItem
                        key={comment.comment_id}
                        comment={comment}
                        onReply={(item) => {
                          setReplyTo(item);
                          setCommentText((text) => (text.trim() ? text : `@${item.author} `));
                        }}
                        onDelete={(item) =>
                          setDeleteTarget({
                            type: 'comment',
                            id: item.comment_id,
                            title: `${item.author} 的评论`,
                          })
                        }
                      />
                    ))}
                </div>

                {comments.length > 0 && (
                  <div className="mt-6 border-t border-dashed border-ink-50 pt-4 text-center">
                    <span className="cursor-pointer text-[12.5px] text-brand-600">↓ 加载更多评论</span>
                  </div>
                )}
              </section>
            </article>
          </div>
        )}
      </Drawer>

      {/* 发帖弹窗 */}
      <Modal
        title={<span className="serif text-[17px] font-bold">发布投研观点</span>}
        open={createOpen}
        onCancel={closeCreateModal}
        onOk={createPost}
        confirmLoading={createMutation.isPending}
        okText={createMutation.isPending ? '发布中...' : '📢 发布'}
        cancelText="取消"
        width={640}
      >
        <Space direction="vertical" className="w-full" size={14}>
          <Input
            value={title}
            placeholder="请输入帖子标题（必填）"
            variant="borderless"
            className="border-b border-ink-50 !px-0 !py-3 !text-[17px] !font-semibold"
            onChange={(e) => setTitle(e.target.value)}
          />
          <Input.TextArea
            rows={6}
            value={content}
            placeholder="分享你的投资见解、市场分析或向 AI 研究员提问（输入 @ 可召唤研究员回复）"
            variant="borderless"
            className="!px-0 !text-[13.5px] !leading-relaxed"
            onChange={(e) => setContent(e.target.value)}
          />
          {(mentionQuery.data?.researchers.length ?? 0) > 0 && (
            <div className="rounded-lg border border-brand-100 bg-brand-50 p-3">
              <div className="mb-2 text-[12px] font-semibold text-brand-700">
                已 @ 提及 {selectedResearcherIds.length} 位研究员
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(mentionQuery.data?.researchers ?? []).slice(0, 6).map((researcher) => (
                  <MentionChip
                    key={researcher.researcher_id}
                    researcher={researcher}
                    selected={selectedResearcherIds.includes(researcher.researcher_id)}
                    onToggle={(item) => {
                      toggleMention(item);
                      if (!content.includes(`@${item.name}`)) {
                        setContent((text) => `${text}${text.trim() ? '\n\n' : ''}@${item.name} `);
                      }
                    }}
                  />
                ))}
              </div>
              <div className="mt-2 text-[11px] text-ink-500">
                被 @ 的研究员会参与讨论，后续可接入算力消耗与自动回复流程。
              </div>
            </div>
          )}

          <div>
            <div className="flex flex-wrap gap-2">
              {draftImages.map((image) => (
                <div
                  key={image.id}
                  className="relative h-20 w-20 overflow-hidden rounded-lg bg-ink-25"
                >
                  <div
                    className={[
                      'grid h-full w-full place-items-center px-2 text-center text-[11px] font-semibold text-white',
                      image.status === 'error'
                        ? 'bg-up-500'
                        : 'bg-gradient-to-br from-brand-300 to-up-500',
                    ].join(' ')}
                  >
                    <span className="line-clamp-2 break-all">{image.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setDraftImages((items) => items.filter((item) => item.id !== image.id))}
                    className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-black/55 text-[12px] text-white"
                  >
                    ×
                  </button>
                  {image.status !== 'done' && (
                    <div className="absolute inset-x-0 bottom-0 bg-black/55 px-1 py-0.5 text-center text-[10.5px] text-white">
                      {image.status === 'uploading' ? `上传中 ${image.progress}%` : '上传失败'}
                    </div>
                  )}
                </div>
              ))}
              <label className="grid h-20 w-20 cursor-pointer place-items-center rounded-lg border-2 border-dashed border-ink-100 text-ink-400 hover:border-brand-200 hover:text-brand-600">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/gif"
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    addDraftImages(event.target.files);
                    event.currentTarget.value = '';
                  }}
                />
                <span className="text-center text-[11px]">
                  <span className="block text-[22px] leading-none">+</span>
                  上传图片
                </span>
              </label>
            </div>
            <div className="mt-1 text-[11px] text-ink-400">
              最多 9 张 · 单张 ≤ 2MB · 支持 jpg / png / gif
            </div>
          </div>

          <Input
            value={tags}
            placeholder="标签，逗号分隔，例如:AI,复盘,策略"
            onChange={(e) => setTags(e.target.value)}
          />
          {hasDraft && (
            <div className="rounded-lg bg-ink-25 px-3 py-2 text-[11.5px] text-ink-500">
              📝 草稿自动保存于 5 秒前
            </div>
          )}
        </Space>
      </Modal>

      <Modal
        title="放弃当前编辑？"
        open={discardOpen}
        onCancel={() => setDiscardOpen(false)}
        footer={null}
      >
        <div className="text-center">
          <div className="mx-auto grid h-13 w-13 place-items-center rounded-full bg-gold-50 text-[26px]">
            📝
          </div>
          <p className="mt-3 text-[12.5px] leading-relaxed text-ink-500">
            你已撰写 <b>{title.length + content.length}</b> 字，当前草稿包含 {draftImages.length} 张图片。
            放弃后内容将无法恢复。
          </p>
          <div className="mt-5 grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={discardDraft}
              className="rounded-lg border border-ink-50 px-3 py-2 text-[12px] text-ink-600 hover:bg-ink-25"
            >
              放弃
            </button>
            <button
              type="button"
              onClick={() => {
                setDiscardOpen(false);
                setCreateOpen(false);
                messageApi.success('已存为草稿');
              }}
              className="rounded-lg border border-ink-50 px-3 py-2 text-[12px] text-ink-600 hover:bg-ink-25"
            >
              存为草稿
            </button>
            <button
              type="button"
              onClick={() => setDiscardOpen(false)}
              className="rounded-lg bg-brand-600 px-3 py-2 text-[12px] font-semibold text-white hover:bg-brand-700"
            >
              继续编辑
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        title={deleteTarget?.type === 'post' ? '确认删除帖子？' : '确认删除评论？'}
        open={Boolean(deleteTarget)}
        onCancel={() => setDeleteTarget(undefined)}
        onOk={confirmDelete}
        okText="确认删除"
        cancelText="取消"
        confirmLoading={deletePostMutation.isPending || deleteCommentMutation.isPending}
        okButtonProps={{ danger: true }}
      >
        <p className="text-[12.5px] leading-relaxed text-ink-500">
          {deleteTarget?.type === 'post'
            ? '删除后将无法恢复，所有评论也会一并清除。'
            : '删除后将无法恢复。'}
        </p>
        <div className="mt-3 text-[12px] text-ink-700">删除对象</div>
        <div className="mt-1 rounded-lg bg-ink-25 px-3 py-2 text-[12.5px] text-ink-600">
          {deleteTarget?.title}
        </div>
        <div className="mt-3 text-[12px] text-ink-700">删除原因</div>
        <select
          value={deleteReason}
          onChange={(event) => setDeleteReason(event.target.value)}
          className="mt-1 w-full rounded-lg border border-ink-50 bg-ink-25 px-3 py-2 text-[13px] outline-none"
        >
          <option>违反社区规范</option>
          <option>含敏感投资建议</option>
          <option>广告/营销内容</option>
          <option>恶意刷屏</option>
          <option>其他</option>
        </select>
        <Input.TextArea
          rows={2}
          value={deleteNote}
          placeholder="备注（可选）"
          className="mt-2"
          onChange={(event) => setDeleteNote(event.target.value)}
        />
      </Modal>
    </div>
  );
}

export function CommunityPostDetailPageClient({ postId }: { postId: string }) {
  const [messageApi, messageContext] = message.useMessage();
  const [commentText, setCommentText] = useState('');
  const [replyTo, setReplyTo] = useState<CommunityComment | null>(null);
  const [selectedResearcherIds, setSelectedResearcherIds] = useState<string[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget>();
  const [deleteReason, setDeleteReason] = useState('违反社区规范');
  const [deleteNote, setDeleteNote] = useState('');

  const detailQuery = useCommunityPostDetail(postId);
  const commentsQuery = useCommunityComments(postId);
  const mentionQuery = useCommunityMentionConfig(true);
  const createCommentMutation = useCreateCommunityComment();
  const featureMutation = useSetCommunityPostFeatured();
  const deletePostMutation = useDeleteCommunityPost();
  const deleteCommentMutation = useDeleteCommunityComment();

  const comments = commentsQuery.data ?? detailQuery.data?.comment_list ?? [];
  const selectedResearchers = useMemo(() => {
    const researchers = mentionQuery.data?.researchers ?? [];
    return researchers.filter((item) => selectedResearcherIds.includes(item.researcher_id));
  }, [mentionQuery.data?.researchers, selectedResearcherIds]);

  const toggleMention = (researcher: CommunityMentionResearcher) => {
    setSelectedResearcherIds((ids) => {
      const selected = ids.includes(researcher.researcher_id);
      return selected ? ids.filter((id) => id !== researcher.researcher_id) : [...ids, researcher.researcher_id];
    });
    if (!commentText.includes(`@${researcher.name}`)) {
      setCommentText((text) => `${text}${text.trim() ? ' ' : ''}@${researcher.name} `);
    }
  };

  const createComment = async () => {
    if (!commentText.trim()) {
      messageApi.warning('评论内容不能为空');
      return;
    }
    try {
      await createCommentMutation.mutateAsync({
        post_id: postId,
        content: commentText.trim(),
        reply_to_id: replyTo?.comment_id ?? null,
      });
      messageApi.success('评论成功');
      setCommentText('');
      setReplyTo(null);
      setSelectedResearcherIds([]);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '评论失败');
    }
  };

  const toggleFeatured = async () => {
    if (!detailQuery.data) return;
    try {
      await featureMutation.mutateAsync({
        postId,
        isFeatured: !detailQuery.data.is_featured,
      });
      messageApi.success(detailQuery.data.is_featured ? '已取消精华' : '已设为精华');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '无权执行精华操作');
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      const payload = { reason: deleteReason, note: deleteNote.trim() || null };
      if (deleteTarget.type === 'post') {
        await deletePostMutation.mutateAsync({ postId: deleteTarget.id, payload });
        messageApi.success('删除成功');
      } else {
        await deleteCommentMutation.mutateAsync({ commentId: deleteTarget.id, payload });
        messageApi.success('删除成功');
      }
      setDeleteTarget(undefined);
      setDeleteNote('');
      setDeleteReason('违反社区规范');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '删除失败');
    }
  };

  return (
    <div>
      {messageContext}
      <div className="mb-4">
        <a
          href="/workstation/ai-community"
          className="inline-flex rounded-full border border-ink-50 bg-white px-4 py-2 text-[13px] font-semibold text-brand-700 shadow-sm hover:border-brand-200 hover:bg-brand-50"
        >
          ‹ 返回社区
        </a>
      </div>

      <PageCard density="compact">
        {detailQuery.isLoading && <Skeleton active paragraph={{ rows: 10 }} />}
        {!detailQuery.isLoading && detailQuery.isError && (
          <div className="p-10">
            <Empty description="加载帖子失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          </div>
        )}
        {!detailQuery.isLoading && detailQuery.data && (
          <article className="mx-auto max-w-[800px] px-2 py-2 sm:px-4">
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard?.writeText(window.location.href);
                  messageApi.success('分享链接复制成功');
                }}
                className="rounded-full border border-ink-50 bg-white px-3 py-1 text-[11.5px] text-ink-600 hover:border-brand-200 hover:text-brand-600"
              >
                📤 分享
              </button>
              <button
                type="button"
                onClick={toggleFeatured}
                disabled={featureMutation.isPending}
                className="rounded-full border border-ink-50 bg-white px-3 py-1 text-[11.5px] text-ink-600 hover:border-gold-200 hover:text-gold-600"
              >
                ⭐ {detailQuery.data.is_featured ? '取消精华' : '设为精华'}
              </button>
              <button
                type="button"
                onClick={() =>
                  setDeleteTarget({
                    type: 'post',
                    id: detailQuery.data.post_id,
                    title: detailQuery.data.title,
                  })
                }
                className="rounded-full border border-up-100 bg-white px-3 py-1 text-[11.5px] text-up-600 hover:bg-up-50"
              >
                🗑 删除
              </button>
            </div>

            <h1 className="serif mt-4 text-[24px] font-bold leading-snug text-ink-900">
              {detailQuery.data.title}
            </h1>

            <div className="mt-4 flex items-center gap-3 border-b border-ink-50 pb-4">
              <div
                className={[
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[14px] font-bold text-white',
                  avatarColor(detailQuery.data.author),
                ].join(' ')}
              >
                {detailQuery.data.author.charAt(0) || '用'}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <b className="text-[13.5px] text-ink-800">{detailQuery.data.author}</b>
                  {detailQuery.data.author_type === 'ai_researcher' && <Badge tone="gold">AI研究员</Badge>}
                  {detailQuery.data.author_level && <Badge tone="brand">{detailQuery.data.author_level}</Badge>}
                  {detailQuery.data.is_vip_only && <Badge tone="gold">VIP专属</Badge>}
                </div>
                <div className="mt-0.5 text-[11px] text-ink-400">
                  {dayjs(detailQuery.data.created_at).format('YYYY-MM-DD HH:mm')} · 👁 {detailQuery.data.views} 浏览 · 💬 {detailQuery.data.comments} 评论
                </div>
              </div>
            </div>

            <div className="mt-4 whitespace-pre-wrap text-[14px] leading-[1.95] text-ink-800">
              {detailQuery.data.content}
            </div>

            <Space wrap className="mt-4">
              {detailQuery.data.tags.map((t) => (
                <Tag key={t} color="green">
                  #{t}
                </Tag>
              ))}
            </Space>

            <section className="mt-6">
              <div className="serif text-[17px] font-bold text-ink-900">全部评论（{comments.length}）</div>

              <div className="mt-3 rounded-xl bg-ink-25 p-3">
                <Input.TextArea
                  rows={3}
                  value={commentText}
                  placeholder="留下你的评论 · 输入 @ 可强制召唤研究员回复"
                  onChange={(e) => setCommentText(e.target.value)}
                  className="!border-0 !bg-transparent !shadow-none"
                />
                {replyTo && (
                  <div className="mt-2 flex items-center justify-between rounded-lg bg-white px-3 py-2 text-[12px] text-ink-500">
                    <span className="min-w-0 truncate">正在回复 @{replyTo.author}</span>
                    <button
                      type="button"
                      onClick={() => setReplyTo(null)}
                      className="ml-2 shrink-0 text-ink-400 hover:text-ink-700"
                    >
                      取消
                    </button>
                  </div>
                )}

                {(mentionQuery.data?.researchers.length ?? 0) > 0 && (
                  <div className="mt-2 rounded-lg border border-brand-100 bg-brand-50 p-2.5">
                    <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-brand-700">
                      🤖 @ 召唤研究员
                      {selectedResearchers.length > 0 && (
                        <span className="font-normal text-ink-500">
                          已选择 {selectedResearchers.length} 位
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(mentionQuery.data?.researchers ?? []).slice(0, 6).map((researcher) => (
                        <MentionChip
                          key={researcher.researcher_id}
                          researcher={researcher}
                          selected={selectedResearcherIds.includes(researcher.researcher_id)}
                          onToggle={toggleMention}
                        />
                      ))}
                    </div>
                  </div>
                )}

                <div className="mt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={createComment}
                    disabled={createCommentMutation.isPending}
                    className="rounded-full bg-brand-600 px-4 py-1.5 text-[12px] font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {createCommentMutation.isPending ? '发布中...' : '发表评论'}
                  </button>
                </div>
              </div>

              <div className="mt-5 space-y-5">
                {commentsQuery.isLoading && <Skeleton active paragraph={{ rows: 5 }} />}
                {commentsQuery.isError && (
                  <Empty description="加载评论失败" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
                {!commentsQuery.isLoading && !commentsQuery.isError && comments.length === 0 && (
                  <Empty description="暂无评论" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
                {!commentsQuery.isLoading &&
                  !commentsQuery.isError &&
                  comments.map((comment) => (
                    <CommentItem
                      key={comment.comment_id}
                      comment={comment}
                      onReply={(item) => {
                        setReplyTo(item);
                        setCommentText((text) => (text.trim() ? text : `@${item.author} `));
                      }}
                      onDelete={(item) =>
                        setDeleteTarget({
                          type: 'comment',
                          id: item.comment_id,
                          title: `${item.author} 的评论`,
                        })
                      }
                    />
                  ))}
              </div>
            </section>
          </article>
        )}
      </PageCard>

      <Modal
        title={deleteTarget?.type === 'post' ? '确认删除帖子？' : '确认删除评论？'}
        open={Boolean(deleteTarget)}
        onCancel={() => setDeleteTarget(undefined)}
        onOk={confirmDelete}
        okText="确认删除"
        cancelText="取消"
        confirmLoading={deletePostMutation.isPending || deleteCommentMutation.isPending}
        okButtonProps={{ danger: true }}
      >
        <p className="text-[12.5px] leading-relaxed text-ink-500">
          {deleteTarget?.type === 'post'
            ? '删除后将无法恢复，所有评论也会一并清除。'
            : '删除后将无法恢复。'}
        </p>
        <div className="mt-3 text-[12px] text-ink-700">删除对象</div>
        <div className="mt-1 rounded-lg bg-ink-25 px-3 py-2 text-[12.5px] text-ink-600">
          {deleteTarget?.title}
        </div>
        <div className="mt-3 text-[12px] text-ink-700">删除原因</div>
        <select
          value={deleteReason}
          onChange={(event) => setDeleteReason(event.target.value)}
          className="mt-1 w-full rounded-lg border border-ink-50 bg-ink-25 px-3 py-2 text-[13px] outline-none"
        >
          <option>违反社区规范</option>
          <option>含敏感投资建议</option>
          <option>广告/营销内容</option>
          <option>恶意刷屏</option>
          <option>其他</option>
        </select>
        <Input.TextArea
          rows={2}
          value={deleteNote}
          placeholder="备注（可选）"
          className="mt-2"
          onChange={(event) => setDeleteNote(event.target.value)}
        />
      </Modal>
    </div>
  );
}
