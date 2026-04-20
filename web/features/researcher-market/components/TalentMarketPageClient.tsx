/**
 * 人才市场页面
 *
 * 属于“赛博实验室”子页面之一，路由：/workstation/talent-market
 * 展示市场上公开的研究员卡片网格，支持搜索、雇佣操作。
 * 每张卡片显示：头像 + 名称 + 等级标签 + 风格标签 + 简介 + 雇佣量 + 操作按钮
 *
 * 数据流：
 *  - useMarketResearchers()  市场研究员列表（支持关键词搜索）
 *  - useHireResearcher()    雇佣操作 mutation
 */
'use client';

import { useState } from 'react';
import { Avatar, Button, Input, Spin, Tag, Typography } from 'antd';
import { CopyOutlined, EyeOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons';

import { useMarketResearchers, useHireResearcher } from '@/features/researcher-market/hooks';
import type { ResearcherMarketCard } from '@/types/researcher';

/** 根据等级名称返回 Tag 颜色（L3 紫 / L2 蓝 / 其他灰） */
function levelColor(level: string) {
  if (level.includes('3')) return 'purple';
  if (level.includes('2')) return 'blue';
  return 'default';
}

/**
 * 单个研究员卡片
 * 包含：头像 + 名称 + 等级 + 风格标签 + 简介 + 统计 + 雇佣/查看按钮
 */
function ResearcherCard({ item }: { item: ResearcherMarketCard }) {
  const hire = useHireResearcher();

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md">
      {/* Header */}
      <div className="mb-3 flex items-center gap-3">
        <Avatar size={44} icon={<UserOutlined />} className="bg-brand-400 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold">{item.name}</span>
            <Tag color={levelColor(item.level)} className="!text-xs">{item.level}</Tag>
          </div>
          {item.tags.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {item.tags.map((tag) => (
                <Tag key={tag} className="!text-xs !m-0" color="purple">{tag}</Tag>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Description */}
      <Typography.Paragraph className="!mb-3 !text-sm !text-slate-500" ellipsis={{ rows: 2 }}>
        {item.introduction}
      </Typography.Paragraph>

      {/* Stats */}
      <div className="mb-3 flex items-center gap-4 text-xs text-slate-400">
        <span>盈 {item.hire_count}+编辑</span>
        <span>{item.version}</span>
      </div>

      {/* Action */}
      {item.is_hired ? (
        <Button block type="primary" ghost icon={<EyeOutlined />}>
          查看
        </Button>
      ) : (
        <Button
          block
          type="primary"
          loading={hire.isPending}
          onClick={() => hire.mutate(item.id)}
        >
          雇用
        </Button>
      )}

      {/* Bottom icons */}
      <div className="mt-2 flex justify-end gap-2 text-slate-400">
        {item.template_visible && <EyeOutlined className="cursor-pointer hover:text-brand-500" />}
        <CopyOutlined className="cursor-pointer hover:text-brand-500" />
      </div>
    </div>
  );
}

/** 人才市场主组件 */
export function TalentMarketPageClient() {
  const [search, setSearch] = useState(''); // 搜索关键词
  const { data, isLoading } = useMarketResearchers({ q: search || undefined });

  return (
    <div>
      {/* Header —— 移动端上下堆叠 */}
      <div className="mb-6 space-y-3">
        <div>
          <Typography.Title level={4} className="!mb-1">
            人才市场
          </Typography.Title>
          <Typography.Text type="secondary">
            探索市场专业研究员，雇佣适合自己策略风格的AI助手
          </Typography.Text>
        </div>
        <Input
          prefix={<SearchOutlined className="text-slate-400" />}
          placeholder="搜索研究员名称或关键词..."
          className="w-full sm:!w-64"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.items.map((item) => (
            <ResearcherCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {!isLoading && data && data.items.length === 0 && (
        <div className="py-24 text-center text-slate-400">暂无匹配的研究员</div>
      )}
    </div>
  );
}
