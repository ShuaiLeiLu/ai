/**
 * 账户中心页面 —— 五 Tab 结构
 *
 * Tab 页签：
 *  1. 个人信息：头像/昵称/手机号/会员等级/电池余额
 *  2. 电池明细：余额统计卡片 + 流水表格
 *  3. 会员套餐：注册版/基础版/大师版/旗舰版定价卡片
 *  4. 安全设置：修改密码/更换手机入口
 *  5. 邀请好友：邀请链接 + 奖励规则 + 邀请记录
 *
 * 移动端：Tab 自动滚动，卡片栈式布局
 */
'use client';

import { useMemo, useState } from 'react';
import {
  Avatar,
  Button,
  Descriptions,
  Empty,
  Form,
  Input,
  Segmented,
  Skeleton,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  CopyOutlined,
  CrownOutlined,
  GiftOutlined,
  LockOutlined,
  PhoneOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { useBatteryLedger, useMembership } from '@/features/billing/hooks';
import { useUserSessionStore } from '@/stores/user-session.store';
import type { BatteryLedgerItem } from '@/types/billing';

/** Tab 枚举 */
type TabKey = 'profile' | 'battery' | 'plans' | 'security' | 'invite';

// ──────────── 电池明细表格列 ────────────
const ledgerColumns: ColumnsType<BatteryLedgerItem> = [
  {
    title: '时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 160,
    render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
  },
  { title: '描述', dataIndex: 'reason', key: 'reason' },
  {
    title: '变动',
    dataIndex: 'change',
    key: 'change',
    width: 100,
    render: (v: number) =>
      v >= 0 ? <Tag color="green">+{v}</Tag> : <Tag color="red">{v}</Tag>,
  },
];

// ──────────── 会员套餐配置 ────────────
interface PlanConfig {
  name: string;
  level: string;
  monthPrice: number;
  yearPrice: number;
  battery: number;
  features: string[];
  recommended?: boolean;
  color: string;
}

const plans: PlanConfig[] = [
  {
    name: '注册版',
    level: 'FREE',
    monthPrice: 0,
    yearPrice: 0,
    battery: 300,
    features: ['基础资讯浏览', '社区浏览', '1个研究员'],
    color: 'border-slate-200',
  },
  {
    name: '基础版',
    level: 'VIP1',
    monthPrice: 29,
    yearPrice: 299,
    battery: 3000,
    features: ['全部资讯分析', '社区发帖', '3个研究员', '知识库 1 个'],
    color: 'border-blue-300',
  },
  {
    name: '大师版',
    level: 'VIP2',
    monthPrice: 79,
    yearPrice: 799,
    battery: 10000,
    features: ['全部功能', '10个研究员', '知识库 5 个', 'MCP 接入', '优先客服'],
    recommended: true,
    color: 'border-brand-400',
  },
  {
    name: '旗舰版',
    level: 'VIP3',
    monthPrice: 199,
    yearPrice: 1999,
    battery: 30000,
    features: ['全部功能', '无限研究员', '无限知识库', 'MCP 无限接入', '专属客服', '优先内测'],
    color: 'border-amber-400',
  },
];

// ──────────── Tab 1: 个人信息 ────────────
function ProfileTab() {
  const user = useUserSessionStore((s) => s.user);
  const membershipQuery = useMembership();

  if (!user) {
    return <Empty description="请先登录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div className="space-y-4">
      {/* 用户信息卡片 */}
      <div className="rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 p-5 text-white sm:p-6">
        <div className="flex flex-col items-center gap-4 sm:flex-row">
          <Avatar size={64} icon={<UserOutlined />} className="!bg-white/20 shrink-0" />
          <div className="flex-1 text-center sm:text-left">
            <div className="text-xl font-bold">{user.nickname}</div>
            <div className="mt-1 text-sm text-white/70">{user.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')}</div>
            <div className="mt-2 flex flex-wrap justify-center gap-2 sm:justify-start">
              <Tag color="gold" className="!border-0">
                <CrownOutlined className="mr-1" />
                {user.membership_level}
              </Tag>
              <Tag className="!border-0 !bg-white/20 !text-white">
                <ThunderboltOutlined className="mr-1" />
                电池：{user.battery_balance}
              </Tag>
            </div>
          </div>
        </div>
      </div>

      {/* 详细信息 */}
      <div className="rounded-lg bg-white p-4 sm:p-6">
        <Typography.Title level={5} className="!mb-4">账户信息</Typography.Title>
        <Descriptions
          column={{ xs: 1, sm: 2 }}
          size="small"
          labelStyle={{ color: '#64748b' }}
        >
          <Descriptions.Item label="昵称">{user.nickname}</Descriptions.Item>
          <Descriptions.Item label="手机号">{user.phone}</Descriptions.Item>
          <Descriptions.Item label="会员等级">{user.membership_level}</Descriptions.Item>
          <Descriptions.Item label="电池余额">{user.battery_balance}</Descriptions.Item>
          {membershipQuery.data && (
            <>
              <Descriptions.Item label="电池折扣">{(membershipQuery.data.battery_discount * 100).toFixed(0)}%</Descriptions.Item>
              <Descriptions.Item label="已解锁权益">
                <div className="flex flex-wrap gap-1">
                  {membershipQuery.data.unlocked_features.map((f) => (
                    <Tag key={f} color="purple" className="!text-xs">{f}</Tag>
                  ))}
                </div>
              </Descriptions.Item>
            </>
          )}
        </Descriptions>
      </div>
    </div>
  );
}

// ──────────── Tab 2: 电池明细 ────────────
function BatteryTab() {
  const user = useUserSessionStore((s) => s.user);
  const ledgerQuery = useBatteryLedger(50);

  return (
    <div className="space-y-4">
      {/* 余额统计 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-white p-4 text-center">
          <Statistic
            title="当前余额"
            value={user?.battery_balance ?? 0}
            prefix={<ThunderboltOutlined className="text-amber-500" />}
          />
        </div>
        <div className="rounded-lg bg-white p-4 text-center">
          <Statistic title="永久电池" value={user?.battery_balance ?? 0} valueStyle={{ color: '#7c3aed' }} />
        </div>
        <div className="rounded-lg bg-white p-4 text-center">
          <Statistic title="本月消耗" value={0} valueStyle={{ color: '#ef4444' }} />
        </div>
      </div>

      {/* 流水表格 */}
      <div className="rounded-lg bg-white p-4">
        <Typography.Title level={5} className="!mb-3">流水明细</Typography.Title>
        {ledgerQuery.isLoading && <Skeleton active paragraph={{ rows: 6 }} />}
        {!ledgerQuery.isLoading && (
          <Table
            rowKey="item_id"
            columns={ledgerColumns}
            dataSource={ledgerQuery.data ?? []}
            pagination={{ pageSize: 10, size: 'small' }}
            scroll={{ x: 400 }}
            size="small"
          />
        )}
      </div>
    </div>
  );
}

// ──────────── Tab 3: 会员套餐 ────────────
function PlansTab() {
  const [cycle, setCycle] = useState<'month' | 'year'>('month'); // 月付/年付切换

  return (
    <div className="space-y-4">
      {/* 月付/年付切换 */}
      <div className="flex justify-center">
        <Segmented
          value={cycle}
          options={[
            { label: '月付', value: 'month' },
            { label: '年付（省20%）', value: 'year' },
          ]}
          onChange={(v) => setCycle(v as typeof cycle)}
        />
      </div>

      {/* 套餐卡片 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => (
          <div
            key={plan.level}
            className={`relative rounded-xl border-2 bg-white p-5 transition-shadow hover:shadow-lg ${plan.color} ${
              plan.recommended ? 'ring-2 ring-brand-400 ring-offset-2' : ''
            }`}
          >
            {plan.recommended && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-500 px-3 py-0.5 text-xs font-bold text-white">
                推荐
              </div>
            )}
            <div className="mb-3 text-center">
              <div className="text-lg font-bold">{plan.name}</div>
              <div className="mt-2">
                <span className="text-3xl font-extrabold text-brand-600">
                  ¥{cycle === 'month' ? plan.monthPrice : plan.yearPrice}
                </span>
                <span className="text-sm text-slate-400">/{cycle === 'month' ? '月' : '年'}</span>
              </div>
              {plan.battery > 0 && (
                <div className="mt-1 text-xs text-amber-600">
                  <ThunderboltOutlined /> 赠送 {plan.battery} 电池
                </div>
              )}
            </div>
            <div className="mb-4 space-y-2">
              {plan.features.map((f) => (
                <div key={f} className="flex items-center gap-2 text-sm text-slate-600">
                  <span className="text-green-500">✓</span>
                  {f}
                </div>
              ))}
            </div>
            <Button
              type={plan.recommended ? 'primary' : 'default'}
              block
              disabled={plan.monthPrice === 0}
            >
              {plan.monthPrice === 0 ? '当前方案' : '立即购买'}
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ──────────── Tab 4: 安全设置 ────────────
function SecurityTab() {
  const [msgApi, msgCtx] = message.useMessage();

  return (
    <div className="space-y-4">
      {msgCtx}
      {/* 修改密码 */}
      <div className="rounded-lg bg-white p-5 sm:p-6">
        <div className="mb-4 flex items-center gap-2">
          <LockOutlined className="text-lg text-brand-500" />
          <Typography.Title level={5} className="!mb-0">修改密码</Typography.Title>
        </div>
        <Form layout="vertical" requiredMark={false} className="max-w-md"
          onFinish={() => msgApi.info('修改密码功能开发中')}
        >
          <Form.Item label="当前密码" name="oldPassword" rules={[{ required: true }]}>
            <Input.Password placeholder="请输入当前密码" />
          </Form.Item>
          <Form.Item label="新密码" name="newPassword" rules={[{ required: true }, { min: 6, message: '至少6位' }]}>
            <Input.Password placeholder="请输入新密码（至少6位）" />
          </Form.Item>
          <Form.Item label="确认新密码" name="confirmPassword" dependencies={['newPassword']}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) return Promise.resolve();
                  return Promise.reject(new Error('两次密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit">确认修改</Button>
        </Form>
      </div>

      {/* 更换手机 */}
      <div className="rounded-lg bg-white p-5 sm:p-6">
        <div className="mb-4 flex items-center gap-2">
          <PhoneOutlined className="text-lg text-brand-500" />
          <Typography.Title level={5} className="!mb-0">更换绑定手机</Typography.Title>
        </div>
        <Form layout="vertical" requiredMark={false} className="max-w-md"
          onFinish={() => msgApi.info('更换手机功能开发中')}
        >
          <Form.Item label="新手机号" name="newPhone" rules={[{ required: true }, { pattern: /^1\d{10}$/, message: '请输入正确手机号' }]}>
            <Input placeholder="请输入新手机号" maxLength={11} />
          </Form.Item>
          <Button type="primary" htmlType="submit">确认更换</Button>
        </Form>
      </div>

      {/* 其他安全能力 */}
      <div className="rounded-lg bg-white p-5 sm:p-6">
        <div className="mb-3 flex items-center gap-2">
          <SafetyOutlined className="text-lg text-brand-500" />
          <Typography.Title level={5} className="!mb-0">更多安全能力</Typography.Title>
        </div>
        <div className="text-sm text-slate-400">设备管理、登录记录等功能开发中...</div>
      </div>
    </div>
  );
}

// ──────────── Tab 5: 邀请好友 ────────────
function InviteTab() {
  const [msgApi, msgCtx] = message.useMessage();
  const user = useUserSessionStore((s) => s.user);

  /** 生成邀请链接 */
  const inviteLink = useMemo(() => {
    if (typeof window === 'undefined') return '';
    return `${window.location.origin}/login?ref=${user?.user_id ?? ''}`;
  }, [user?.user_id]);

  /** 复制邀请链接 */
  const copyLink = () => {
    navigator.clipboard.writeText(inviteLink).then(
      () => msgApi.success('邀请链接已复制'),
      () => msgApi.error('复制失败，请手动复制'),
    );
  };

  return (
    <div className="space-y-4">
      {msgCtx}

      {/* 邀请链接卡片 */}
      <div className="rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 p-5 text-white sm:p-6">
        <div className="mb-3 flex items-center gap-2 text-lg font-bold">
          <GiftOutlined /> 邀请好友赢电池
        </div>
        <div className="mb-4 text-sm text-white/80">
          邀请好友注册极睿智投，双方各得 100 电池；好友开通 VIP 后额外奖励 500 电池！
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={inviteLink}
            readOnly
            className="!bg-white/20 !text-white !border-white/30 flex-1"
          />
          <Button icon={<CopyOutlined />} onClick={copyLink} className="!bg-white !text-brand-600 shrink-0">
            复制链接
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-white p-4 text-center">
          <Statistic title="已邀请人数" value={0} />
        </div>
        <div className="rounded-lg bg-white p-4 text-center">
          <Statistic title="开通VIP人数" value={0} />
        </div>
        <div className="rounded-lg bg-white p-4 text-center">
          <Statistic title="已获奖励电池" value={0} prefix={<ThunderboltOutlined className="text-amber-500" />} />
        </div>
      </div>

      {/* 奖励规则 */}
      <div className="rounded-lg bg-white p-5">
        <Typography.Title level={5} className="!mb-3">奖励规则</Typography.Title>
        <div className="space-y-2 text-sm text-slate-600">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 shrink-0 text-brand-500">①</span>
            <span>好友通过你的链接注册成功，你和好友各获得 <strong>100 电池</strong></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="mt-0.5 shrink-0 text-brand-500">②</span>
            <span>好友开通任意 VIP 套餐，你额外获得 <strong>500 电池</strong></span>
          </div>
          <div className="flex items-start gap-2">
            <span className="mt-0.5 shrink-0 text-brand-500">③</span>
            <span>每位好友仅计奖一次，奖励实时到账</span>
          </div>
        </div>
      </div>

      {/* 邀请记录（暂无数据） */}
      <div className="rounded-lg bg-white p-5">
        <Typography.Title level={5} className="!mb-3">邀请记录</Typography.Title>
        <Empty description="暂无邀请记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    </div>
  );
}

// ──────────── 主组件 ────────────

export function BillingPageClient() {
  const [tab, setTab] = useState<TabKey>('profile');

  /** Tab 配置 */
  const tabOptions = [
    { label: '个人信息', value: 'profile' },
    { label: '电池明细', value: 'battery' },
    { label: '会员套餐', value: 'plans' },
    { label: '安全设置', value: 'security' },
    { label: '邀请好友', value: 'invite' },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      {/* Tab 导航 —— 移动端自动滚动 */}
      <div className="overflow-x-auto rounded-lg bg-white p-3">
        <Segmented
          block
          value={tab}
          options={tabOptions}
          onChange={(v) => setTab(v as TabKey)}
          className="min-w-[400px]"
        />
      </div>

      {/* Tab 内容 */}
      {tab === 'profile' && <ProfileTab />}
      {tab === 'battery' && <BatteryTab />}
      {tab === 'plans' && <PlansTab />}
      {tab === 'security' && <SecurityTab />}
      {tab === 'invite' && <InviteTab />}
    </div>
  );
}
