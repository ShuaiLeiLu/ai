/**
 * MCP市场页面
 *
 * 属于“赛博实验室”子页面之一，路由：/workstation/mcp-market
 * - 筛选栏：搜索框 + Segmented（全部/已授权/未授权）
 * - 热门推荐区：已授权 MCP 服务卡片
 * - 全部 MCP 服务器：网格卡片列表
 *
 * 数据流：useMcpServers() hook 拉取后端接口
 */
'use client';

import { useState } from 'react';
import { Avatar, Button, Input, Segmented, Spin, Tag, Typography } from 'antd';
import { ApiOutlined, SearchOutlined } from '@ant-design/icons';

import { useMcpServers } from '@/features/ecosystem/hooks';
import type { McpServerItem } from '@/types/ecosystem';

/** 授权状态筛选枚举 */
type McpFilter = 'all' | 'connected' | 'disconnected';

/** 单个 MCP 服务卡片：图标 + 名称 + 授权状态 + 描述 + 操作按钮 */
function McpCard({ item }: { item: McpServerItem }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-center gap-3">
        <Avatar
          size={40}
          icon={<ApiOutlined />}
          className="shrink-0"
          style={{ backgroundColor: item.connected ? '#f3f0ff' : '#f1f5f9', color: item.connected ? '#7c3aed' : '#94a3b8' }}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold">{item.name}</span>
            {item.connected ? (
              <Tag color="green" className="!text-xs">已授权</Tag>
            ) : (
              <Tag className="!text-xs">未授权</Tag>
            )}
          </div>
          <div className="text-xs text-slate-400">{item.category}</div>
        </div>
      </div>
      <Typography.Paragraph className="!mb-3 !text-sm !text-slate-500" ellipsis={{ rows: 2 }}>
        {item.category === 'market-data'
          ? '提供实时行情数据、K线、Level2等市场数据接入能力'
          : '提供公告全文检索、关键词订阅等信息检索能力'}
      </Typography.Paragraph>
      {item.connected ? (
        <Tag color="green" className="!text-xs">授权使用</Tag>
      ) : (
        <Button size="small" type="primary">授权接入</Button>
      )}
    </div>
  );
}

/** MCP市场主组件 */
export function McpMarketPageClient() {
  const [filter, setFilter] = useState<McpFilter>('all'); // 授权状态筛选
  const [search, setSearch] = useState('');                // 搜索关键词
  const { data, isLoading } = useMcpServers();

  // 按授权状态 + 关键词过滤
  const filtered = (data ?? [])
    .filter((item) => {
      if (filter === 'connected') return item.connected;
      if (filter === 'disconnected') return !item.connected;
      return true;
    })
    .filter((item) => (search ? item.name.includes(search) || item.category.includes(search) : true));

  const hotItems = (data ?? []).filter((s) => s.connected); // 热门推荐 = 已授权

  return (
    <div>
      {/* Header —— 移动端上下堆叠 */}
      <div className="mb-6 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Typography.Title level={4} className="!mb-1">
              MCP市场
            </Typography.Title>
            <Typography.Text type="secondary">
              发现和管理MCP服务器，让AI研究员获取实时数据能力
            </Typography.Text>
          </div>
          <Button type="primary">接入MCP</Button>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <Input
            prefix={<SearchOutlined className="text-slate-400" />}
            placeholder="搜索MCP服务器..."
            className="w-full sm:!w-56"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
          <div className="overflow-x-auto">
            <Segmented
              value={filter}
              options={[
                { label: '全部', value: 'all' },
                { label: `已授权 (${(data ?? []).filter((s) => s.connected).length})`, value: 'connected' },
                { label: `未授权 (${(data ?? []).filter((s) => !s.connected).length})`, value: 'disconnected' },
              ]}
              onChange={(v) => setFilter(v as McpFilter)}
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
          {filter === 'all' && hotItems.length > 0 && (
            <div>
              <Typography.Title level={5} className="!mb-3">
                🔥 热门推荐
              </Typography.Title>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {hotItems.map((item) => (
                  <McpCard key={item.server_id} item={item} />
                ))}
              </div>
            </div>
          )}

          {/* All */}
          <div>
            <Typography.Title level={5} className="!mb-3">
              全部MCP服务器 ({filtered.length})
            </Typography.Title>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((item) => (
                <McpCard key={item.server_id} item={item} />
              ))}
            </div>
            {filtered.length === 0 && (
              <div className="py-16 text-center text-slate-400">暂无匹配的MCP服务</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
