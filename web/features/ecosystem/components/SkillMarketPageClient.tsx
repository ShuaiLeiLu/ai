/**
 * 技能市场页面
 *
 * 属于“赛博实验室”子页面之一，路由：/workstation/skill-market
 * - 顶部：标题 + 搜索框 + Segmented 筛选（全部/已安装/未安装）
 * - 热门推荐区：已安装的技能包卡片
 * - 全部技能包：网格卡片列表
 *
 * 数据流：useSkills() hook 拉取后端接口，支持 installed 参数筛选
 */
'use client';

import { useState } from 'react';
import { Avatar, Button, Input, Segmented, Spin, Tag, Typography } from 'antd';
import { SearchOutlined, ThunderboltOutlined } from '@ant-design/icons';

import { useSkills } from '@/features/ecosystem/hooks';
import type { SkillItem } from '@/types/ecosystem';

/** 单个技能包卡片：图标 + 名称 + 状态标签 + 描述 + 安装按钮 */
function SkillCard({ item }: { item: SkillItem }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-center gap-3">
        <Avatar size={40} icon={<ThunderboltOutlined />} className="bg-brand-100 !text-brand-600 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold">{item.name}</span>
            {item.installed ? (
              <Tag color="green" className="!text-xs">已安装</Tag>
            ) : (
              <Tag className="!text-xs">未安装</Tag>
            )}
          </div>
          <div className="text-xs text-slate-400">技能包</div>
        </div>
      </div>
      <Typography.Paragraph className="!mb-3 !text-sm !text-slate-500" ellipsis={{ rows: 2 }}>
        {item.description}
      </Typography.Paragraph>
      {item.installed ? (
        <Button block type="text" className="!text-green-600">已安装</Button>
      ) : (
        <Button block type="primary">安装</Button>
      )}
    </div>
  );
}

/** 技能市场主组件 */
export function SkillMarketPageClient() {
  const [filter, setFilter] = useState<'all' | 'installed' | 'uninstalled'>('all'); // 筛选状态
  const [search, setSearch] = useState(''); // 搜索关键词

  // 根据筛选状态转换为 API 参数
  const installed = filter === 'all' ? undefined : filter === 'installed';
  const { data, isLoading } = useSkills(installed);

  // 前端关键词过滤
  const filtered = (data ?? []).filter((item) =>
    search ? item.name.includes(search) || item.description.includes(search) : true
  );

  const hotItems = (data ?? []).filter((s) => s.installed);  // 热门推荐 = 已安装
  const allItems = filtered;

  return (
    <div>
      {/* Header —— 移动端上下堆叠 */}
      <div className="mb-6 space-y-3">
        <div>
          <Typography.Title level={4} className="!mb-1">
            技能市场
          </Typography.Title>
          <Typography.Text type="secondary">
            发现和安装技能包，增强AI研究员的分析能力
          </Typography.Text>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <Input
            prefix={<SearchOutlined className="text-slate-400" />}
            placeholder="搜索技能..."
            className="w-full sm:!w-48"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
          <div className="overflow-x-auto">
            <Segmented
              value={filter}
              options={[
                { label: '全部', value: 'all' },
                { label: '已安装', value: 'installed' },
                { label: '未安装', value: 'uninstalled' },
              ]}
              onChange={(v) => setFilter(v as typeof filter)}
            />
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      )}

      {!isLoading && (
        <div className="space-y-6">
          {/* Hot Recommendations */}
          {hotItems.length > 0 && (
            <div>
              <Typography.Title level={5} className="!mb-3">
                🔥 热门推荐
              </Typography.Title>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {hotItems.map((item) => (
                  <SkillCard key={item.skill_id} item={item} />
                ))}
              </div>
            </div>
          )}

          {/* All skills */}
          <div>
            <Typography.Title level={5} className="!mb-3">
              全部技能包 ({allItems.length})
            </Typography.Title>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {allItems.map((item) => (
                <SkillCard key={item.skill_id} item={item} />
              ))}
            </div>
            {allItems.length === 0 && (
              <div className="py-16 text-center text-slate-400">暂无匹配的技能包</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
