/**
 * 账户中心页面 —— 五 Tab 结构（中国金融审美重构）
 *
 * Tab 页签：
 *  1. 个人信息：头像/昵称/手机号/会员等级/算力余额
 *  2. 算力明细：余额统计卡片 + 流水表格
 *  3. 会员套餐：免费版 / 黄金会员 / 钻石会员 三列对比
 *  4. 安全设置：修改密码/更换手机入口
 *  5. 邀请好友：邀请链接 + 奖励规则 + 邀请记录
 *
 * 设计：顶部深绿渐变 Hero 卡 + 金色装饰光晕；卡片基元用 PageCard/StatCard/SectionHeading。
 * 数据流：保留所有 hooks（useUserSessionStore / useMembership / useBatteryLedger）。
 */
'use client';

import { useMemo, useState } from 'react';
import {
  Button,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Segmented,
  Skeleton,
  Table,
  Tag,
  message,
} from 'antd';
import {
  AlipayCircleFilled,
  CheckCircleFilled,
  CopyOutlined,
  CreditCardOutlined,
  GiftOutlined,
  LockOutlined,
  PhoneOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { PageCard } from '@/components/ui/page-card';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatCard } from '@/components/ui/stat-card';
import { useBatteryLedger, useBatteryPackages, useMembership } from '@/features/billing/hooks';
import { useUserSessionStore } from '@/stores/user-session.store';
import type { BatteryLedgerItem, BatteryPackage } from '@/types/billing';

/** Tab 枚举 */
type TabKey = 'profile' | 'battery' | 'plans' | 'security' | 'invite';

// ──────────── 算力明细表格列 ────────────
const ledgerColumns: ColumnsType<BatteryLedgerItem> = [
  {
    title: '时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 160,
    render: (v: string) => (
      <span className="tnum text-ink-600">{dayjs(v).format('YYYY-MM-DD HH:mm')}</span>
    ),
  },
  {
    title: '描述',
    dataIndex: 'reason',
    key: 'reason',
    render: (v: string) => <span className="text-ink-800">{v}</span>,
  },
  {
    title: '变动',
    dataIndex: 'change',
    key: 'change',
    width: 100,
    align: 'right' as const,
    render: (v: number) =>
      v >= 0 ? (
        <span className="tnum font-semibold text-up-600">+{v}</span>
      ) : (
        <span className="tnum font-semibold text-down-600">{v}</span>
      ),
  },
];

// ──────────── 会员套餐配置（3 列：免费 / 黄金 / 钻石） ────────────
interface PlanConfig {
  /** 套餐 ID */
  level: 'FREE' | 'GOLD' | 'DIAMOND';
  /** 顶部分类色标签 */
  category: string;
  /** 主名称 */
  name: string;
  /** 月价 */
  monthPrice: number;
  /** 年价 */
  yearPrice: number;
  /** 赠送算力数（>0 显示） */
  battery: number;
  /** 特性列表 */
  features: string[];
  /** 强调色：免费=ink / 黄金=gold / 钻石=brand */
  accent: 'ink' | 'gold' | 'brand';
}

const PLANS: PlanConfig[] = [
  {
    level: 'FREE',
    category: 'STARTER',
    name: '免费版',
    monthPrice: 0,
    yearPrice: 0,
    battery: 300,
    features: ['基础资讯浏览', '社区浏览', '1 个研究员', '300 体验算力'],
    accent: 'ink',
  },
  {
    level: 'GOLD',
    category: 'PREMIUM',
    name: '黄金会员',
    monthPrice: 79,
    yearPrice: 799,
    battery: 10000,
    features: ['全部功能解锁', '10 个研究员', '知识库 5 个', 'MCP 接入', '优先客服'],
    accent: 'gold',
  },
  {
    level: 'DIAMOND',
    category: 'FLAGSHIP',
    name: '钻石会员',
    monthPrice: 199,
    yearPrice: 1999,
    battery: 30000,
    features: ['全部功能', '无限研究员', '无限知识库', 'MCP 无限接入', '专属客服', '优先内测'],
    accent: 'brand',
  },
];

// ──────────── Hero 卡 ──────────────────────────
/**
 * 顶部深绿渐变 Hero 卡：左侧金色头像 + 名字 + 黄金会员 chip，
 * 右侧三列大数字（算力余额 / 研究员配额 / 会员到期天数），右上角金色光晕。
 */
function BillingHero() {
  const user = useUserSessionStore((s) => s.user);
  const membershipQuery = useMembership();

  // 取昵称首字符做头像 fallback
  const initial = (user?.nickname ?? 'U').slice(0, 1).toUpperCase();
  const balance = user?.battery_balance ?? 0;
  const level = user?.membership_level ?? 'FREE';

  // 研究员配额 / 到期天数：membershipQuery 暂未必提供，给出占位
  const researcherQuota = membershipQuery.data?.unlocked_features?.length ?? 0;
  const expireDays = 30; // 占位（hook 未提供）

  return (
    <section
      className="relative overflow-hidden rounded-2xl shadow-card"
      style={{ background: 'linear-gradient(135deg, #1d4a34 0%, #143929 100%)' }}
    >
      {/* 右上角金色光晕装饰 */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-16 h-64 w-64"
        style={{
          background:
            'radial-gradient(circle, rgba(200,154,58,.18), transparent 70%)',
        }}
      />

      <div className="relative flex flex-col gap-6 px-6 py-7 sm:flex-row sm:items-center sm:justify-between sm:px-8 sm:py-8">
        {/* 左：头像 + 名字 + chip */}
        <div className="flex items-center gap-4">
          <div
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full text-2xl font-bold text-white shadow-gold"
            style={{
              background:
                'linear-gradient(135deg, var(--gold-500, #c89a3a), var(--gold-600, #9f7a2a))',
            }}
          >
            {initial}
          </div>
          <div className="min-w-0">
            <div className="serif truncate text-[26px] font-bold leading-tight text-white">
              {user?.nickname ?? '未登录'}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-gold-500/20 px-2.5 py-0.5 text-[11px] font-semibold tracking-[0.1em] text-gold-300 ring-1 ring-gold-500/30">
                {level === 'FREE' ? 'STARTER' : level} 会员
              </span>
              {user?.phone && (
                <span className="text-[12px] text-white/55">
                  {user.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 右：三列大数字 */}
        <div className="grid grid-cols-3 gap-6 sm:gap-10">
          <HeroStat label="算力余额" value={balance.toLocaleString()} />
          <HeroStat label="研究员配额" value={researcherQuota || '—'} />
          <HeroStat label="到期天数" value={`${expireDays}`} suffix="天" />
        </div>
      </div>
    </section>
  );
}

function HeroStat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string | number;
  suffix?: string;
}) {
  return (
    <div className="text-right sm:text-center">
      <div className="text-[11px] uppercase tracking-[0.16em] text-white/55">{label}</div>
      <div className="serif mt-1 text-[26px] font-bold leading-tight text-gold-300 tnum">
        {value}
        {suffix && <span className="ml-0.5 text-sm font-medium text-gold-300/70">{suffix}</span>}
      </div>
    </div>
  );
}

// ──────────── Tab 1: 个人信息 ────────────
function ProfileTab() {
  const user = useUserSessionStore((s) => s.user);
  const membershipQuery = useMembership();

  if (!user) {
    return (
      <PageCard>
        <Empty description="请先登录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </PageCard>
    );
  }

  return (
    <PageCard title="账户信息" subtitle="基础资料与会员权益" accent="brand">
      <Descriptions
        column={{ xs: 1, sm: 2 }}
        size="small"
        labelStyle={{ color: 'var(--ink-400, #7a7264)' }}
        contentStyle={{ color: 'var(--ink-800, #2a2620)' }}
      >
        <Descriptions.Item label="昵称">{user.nickname}</Descriptions.Item>
        <Descriptions.Item label="手机号">{user.phone}</Descriptions.Item>
        <Descriptions.Item label="会员等级">{user.membership_level}</Descriptions.Item>
        <Descriptions.Item label="算力余额">
          <span className="tnum font-semibold text-gold-600">{user.battery_balance}</span>
        </Descriptions.Item>
        {membershipQuery.data && (
          <>
            <Descriptions.Item label="算力折扣">
              {(membershipQuery.data.battery_discount * 100).toFixed(0)}%
            </Descriptions.Item>
            <Descriptions.Item label="已解锁权益">
              <div className="flex flex-wrap gap-1">
                {membershipQuery.data.unlocked_features.map((f) => (
                  <Tag key={f} color="purple" className="!text-xs">
                    {f}
                  </Tag>
                ))}
              </div>
            </Descriptions.Item>
          </>
        )}
      </Descriptions>
    </PageCard>
  );
}

// ──────────── Tab 2: 算力明细 ────────────
function BatteryTab() {
  const user = useUserSessionStore((s) => s.user);
  const ledgerQuery = useBatteryLedger(50);

  const balance = user?.battery_balance ?? 0;
  // 进度条容量假设：以 10000 为标杆显示当前进度
  const capacity = 10000;
  const ratio = Math.min(100, Math.round((balance / capacity) * 100));

  return (
    <div className="space-y-4">
      {/* 余额 + 流水：左大数字进度条，右流水 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,360px)_1fr]">
        {/* 左：当前余额大数字 + 进度条 */}
        <PageCard title="算力余额" subtitle="当前可用算力" accent="gold">
          <div className="flex items-baseline gap-2">
            <span className="serif text-[40px] font-bold leading-none text-gold-600 tnum">
              {balance.toLocaleString()}
            </span>
            <span className="text-sm font-medium text-ink-400">算力</span>
          </div>
          <div className="mt-4">
            <div className="flex items-center justify-between text-[11px] text-ink-400">
              <span>容量配额</span>
              <span className="tnum">
                {balance.toLocaleString()} / {capacity.toLocaleString()}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-ink-25">
              <div
                className="h-full rounded-full bg-gradient-to-r from-gold-400 to-gold-600 transition-all"
                style={{ width: `${ratio}%` }}
              />
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <StatCard label="本月消耗" value={0} embedded />
            <StatCard label="累计获取" value={balance} embedded />
          </div>
        </PageCard>

        {/* 右：流水明细 */}
        <PageCard title="流水明细" subtitle="最近 50 条变动" accent="brand">
          {ledgerQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 6 }} />
          ) : (
            <Table
              rowKey="item_id"
              columns={ledgerColumns}
              dataSource={ledgerQuery.data ?? []}
              pagination={{ pageSize: 8, size: 'small' }}
              scroll={{ x: 400 }}
              size="small"
            />
          )}
        </PageCard>
      </div>
    </div>
  );
}

// ──────────── Tab 3: 会员套餐（3 列对比卡） ────────────
function PlansTab() {
  const [cycle, setCycle] = useState<'month' | 'year'>('month');
  const user = useUserSessionStore((s) => s.user);
  const packagesQuery = useBatteryPackages();
  const balance = user?.battery_balance ?? 0;

  // 当前用户会员（FREE 默认；其他映射 GOLD）—— 用于卡片高亮
  const currentLevel: PlanConfig['level'] = useMemo(() => {
    const lvl = user?.membership_level ?? 'FREE';
    if (lvl === 'FREE') return 'FREE';
    if (lvl === 'VIP3') return 'DIAMOND';
    return 'GOLD';
  }, [user?.membership_level]);

  return (
    <div className="space-y-4">
      <PowerPackagePanel balance={balance} packages={packagesQuery.data ?? []} loading={packagesQuery.isLoading} />

      {/* 月付/年付切换 */}
      <div className="flex justify-center">
        <Segmented
          value={cycle}
          options={[
            { label: '月付', value: 'month' },
            { label: '年付（省 20%）', value: 'year' },
          ]}
          onChange={(v) => setCycle(v as typeof cycle)}
        />
      </div>

      {/* 3 列对比卡 */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {PLANS.map((plan) => {
          const isCurrent = plan.level === currentLevel;
          const isGold = plan.accent === 'gold';
          const isBrand = plan.accent === 'brand';

          // 卡片边框与背景：当前/黄金 -> 金色边框；钻石 -> brand 边框
          const ringClass = isCurrent
            ? isGold
              ? 'ring-2 ring-gold-500/60 shadow-gold'
              : 'ring-2 ring-brand-500/60'
            : '';

          const price = cycle === 'month' ? plan.monthPrice : plan.yearPrice;
          const cycleLabel = cycle === 'month' ? '/月' : '/年';

          return (
            <div
              key={plan.level}
              className={[
                'relative overflow-hidden rounded-2xl border bg-white p-6 shadow-card transition-shadow hover:shadow-card-lg',
                isGold ? 'border-gold-300' : isBrand ? 'border-brand-200' : 'border-ink-50',
                ringClass,
              ].join(' ')}
            >
              {/* 当前徽章 */}
              {isCurrent && (
                <div className="absolute -top-px left-1/2 -translate-x-1/2 rounded-b-md bg-gold-500 px-3 py-0.5 text-[11px] font-semibold tracking-[0.1em] text-white shadow-gold">
                  ⭐ 当前
                </div>
              )}

              {/* 分类色标签 */}
              <div
                className={[
                  'text-[11px] font-semibold uppercase',
                  isGold ? 'text-gold-600' : isBrand ? 'text-brand-600' : 'text-ink-400',
                ].join(' ')}
                style={{ letterSpacing: '2px' }}
              >
                {plan.category}
              </div>

              {/* 名称 */}
              <div className="serif mt-2 text-[22px] font-bold text-ink-900">{plan.name}</div>

              {/* 价格 */}
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-base font-medium text-ink-400">¥</span>
                <span
                  className={[
                    'serif text-[36px] font-bold leading-none tnum',
                    isGold ? 'text-gold-600' : isBrand ? 'text-brand-600' : 'text-ink-900',
                  ].join(' ')}
                >
                  {price}
                </span>
                <span className="text-sm text-ink-400">{cycleLabel}</span>
              </div>

              {/* 赠送算力 */}
              {plan.battery > 0 && (
                <div className="mt-1 text-[12px] text-gold-600">
                  <ThunderboltOutlined className="mr-1" />
                  赠送 {plan.battery.toLocaleString()} 算力
                </div>
              )}

              {/* 特性列表 */}
              <div className="my-5 h-px bg-ink-25" />
              <ul className="space-y-2.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-[13px] text-ink-600">
                    <span
                      className={[
                        'mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold',
                        isGold
                          ? 'bg-gold-500/15 text-gold-600'
                          : isBrand
                            ? 'bg-brand-500/10 text-brand-600'
                            : 'bg-ink-50 text-ink-500',
                      ].join(' ')}
                    >
                      ✓
                    </span>
                    {f}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <Button
                type={isGold || isBrand ? 'primary' : 'default'}
                block
                disabled={isCurrent}
                className={[
                  'mt-6 !h-10 !font-semibold',
                  isGold && !isCurrent ? '!bg-gold-500 hover:!bg-gold-600 !border-gold-500' : '',
                ].join(' ')}
              >
                {isCurrent ? '当前方案' : plan.level === 'FREE' ? '免费使用' : '立即升级'}
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PowerPackagePanel({
  balance,
  packages,
  loading,
}: {
  balance: number;
  packages: BatteryPackage[];
  loading: boolean;
}) {
  const fallbackPackages: BatteryPackage[] = [
    { package_id: 'power_1000', name: '1,000 算力', battery_count: 1_000, price: 9.9 },
    { package_id: 'power_5000', name: '5,000 算力', battery_count: 5_000, price: 39 },
    { package_id: 'power_15000', name: '15,000 算力', battery_count: 15_000, price: 99 },
    { package_id: 'power_50000', name: '50,000 算力', battery_count: 50_000, price: 299 },
  ];
  const items = packages.length > 0 ? packages : fallbackPackages;
  const [selectedPackageId, setSelectedPackageId] = useState('power_5000');
  const [paymentMethod, setPaymentMethod] = useState<'wechat' | 'alipay' | 'bank'>('wechat');
  const [successOpen, setSuccessOpen] = useState(false);
  const selectedPackage = items.find((item) => item.package_id === selectedPackageId) ?? items[1] ?? items[0];
  const paymentOptions = [
    { key: 'wechat' as const, label: '微信支付', icon: <span className="text-[20px]">💚</span> },
    { key: 'alipay' as const, label: '支付宝', icon: <AlipayCircleFilled className="text-[20px] text-brand-600" /> },
    { key: 'bank' as const, label: '银行卡', icon: <CreditCardOutlined className="text-[20px] text-ink-500" /> },
  ];

  return (
    <>
      <PageCard title="算力充值" subtitle="充值算力包 · 支持后续 AI 对话、研报生成与题材解锁" accent="gold">
        <div className="mb-4 flex flex-col gap-2 rounded-xl border border-gold-200 bg-gold-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-[11.5px] text-ink-500">当前算力余额</div>
            <div className="serif text-[26px] font-bold text-gold-700 tnum">{balance.toLocaleString()}</div>
          </div>
          <div className="text-[11.5px] text-ink-500">普通对话约 1-5 算力 · 深度任务约 20-50 算力</div>
        </div>

        {loading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              {items.map((item) => {
                const hot = item.battery_count === 5_000;
                const selected = item.package_id === selectedPackage?.package_id;
                return (
                  <button
                    key={item.package_id}
                    type="button"
                    onClick={() => setSelectedPackageId(item.package_id)}
                    className={[
                      'relative rounded-[14px] border bg-white p-4 text-left transition hover:-translate-y-0.5 hover:shadow-card',
                      selected ? 'border-gold-500 bg-gradient-to-br from-gold-50 to-white shadow-gold' : 'border-ink-50',
                    ].join(' ')}
                  >
                    {hot && (
                      <span className="absolute -top-2 right-3 rounded-full bg-gold-500 px-2 py-0.5 text-[10.5px] font-bold text-white">
                        热销
                      </span>
                    )}
                    <div className={`serif text-[17px] font-bold ${selected ? 'text-gold-700' : 'text-ink-900'}`}>
                      {item.name}
                    </div>
                    <div className="mt-1 text-[11.5px] text-ink-400">
                      约 {Math.round(item.battery_count / 5).toLocaleString()} 次普通对话
                    </div>
                    <div className="mt-3 text-[22px] font-bold text-ink-900 tnum">¥ {item.price}</div>
                  </button>
                );
              })}
            </div>

            <div className="mt-4 border-t border-ink-50 pt-4">
              <div className="mb-2 text-[11px] tracking-[2px] text-ink-400">支付方式</div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                {paymentOptions.map((option) => {
                  const selected = paymentMethod === option.key;
                  return (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => setPaymentMethod(option.key)}
                      className={[
                        'flex items-center gap-2 rounded-[10px] border px-3 py-2 text-left text-[13px] font-semibold',
                        selected ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-ink-50 bg-white text-ink-700',
                      ].join(' ')}
                    >
                      {option.icon}
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-3 rounded-xl bg-ink-25 px-4 py-3 md:flex-row md:items-center">
              <span className="text-[12.5px] text-ink-500">应付金额</span>
              <span className="serif text-[24px] font-bold text-up-600 tnum">¥ {selectedPackage?.price ?? 0}</span>
              <span className="text-[11.5px] text-ink-400">
                充值后余额约 {((selectedPackage?.battery_count ?? 0) + balance).toLocaleString()} 算力
              </span>
              <Button type="primary" className="md:!ml-auto" onClick={() => setSuccessOpen(true)}>
                立即支付
              </Button>
            </div>
          </>
        )}
      </PageCard>

      <Modal open={successOpen} footer={null} onCancel={() => setSuccessOpen(false)} width={420}>
        <div className="py-5 text-center">
          <div className="mx-auto grid h-[72px] w-[72px] place-items-center rounded-full bg-up-50">
            <CheckCircleFilled className="text-[42px] text-up-600" />
          </div>
          <div className="serif mt-4 text-[22px] font-bold text-ink-900">支付成功</div>
          <p className="mt-1 text-[12.5px] text-ink-500">
            {selectedPackage?.name ?? '算力包'} 已加入账户，当前为模拟支付状态。
          </p>
          <div className="mt-4 rounded-[10px] border border-ink-50 bg-ink-25 px-4 py-3 text-left text-[12.5px]">
            <div className="flex justify-between">
              <span className="text-ink-400">订单内容</span>
              <b className="text-ink-800">{selectedPackage?.name ?? '-'}</b>
            </div>
            <div className="mt-1 flex justify-between">
              <span className="text-ink-400">支付金额</span>
              <b className="tnum text-up-600">¥ {selectedPackage?.price ?? 0}</b>
            </div>
            <div className="mt-1 flex justify-between">
              <span className="text-ink-400">支付方式</span>
              <span>{paymentOptions.find((option) => option.key === paymentMethod)?.label}</span>
            </div>
          </div>
          <Button type="primary" block className="!mt-4" onClick={() => setSuccessOpen(false)}>
            完成
          </Button>
        </div>
      </Modal>
    </>
  );
}

// ──────────── Tab 4: 安全设置 ────────────
function SecurityTab() {
  const [msgApi, msgCtx] = message.useMessage();

  return (
    <div className="space-y-4">
      {msgCtx}

      {/* 修改密码 */}
      <PageCard
        title={
          <span className="flex items-center gap-2">
            <LockOutlined className="text-brand-600" />
            修改密码
          </span>
        }
        accent="brand"
      >
        <Form
          layout="vertical"
          requiredMark={false}
          className="max-w-md"
          onFinish={() => msgApi.info('修改密码功能开发中')}
        >
          <Form.Item label="当前密码" name="oldPassword" rules={[{ required: true }]}>
            <Input.Password placeholder="请输入当前密码" />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="newPassword"
            rules={[{ required: true }, { min: 6, message: '至少 6 位' }]}
          >
            <Input.Password placeholder="请输入新密码（至少 6 位）" />
          </Form.Item>
          <Form.Item
            label="确认新密码"
            name="confirmPassword"
            dependencies={['newPassword']}
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
          <Button type="primary" htmlType="submit">
            确认修改
          </Button>
        </Form>
      </PageCard>

      {/* 更换手机 */}
      <PageCard
        title={
          <span className="flex items-center gap-2">
            <PhoneOutlined className="text-brand-600" />
            更换绑定手机
          </span>
        }
        accent="brand"
      >
        <Form
          layout="vertical"
          requiredMark={false}
          className="max-w-md"
          onFinish={() => msgApi.info('更换手机功能开发中')}
        >
          <Form.Item
            label="新手机号"
            name="newPhone"
            rules={[
              { required: true },
              { pattern: /^1\d{10}$/, message: '请输入正确手机号' },
            ]}
          >
            <Input placeholder="请输入新手机号" maxLength={11} />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            确认更换
          </Button>
        </Form>
      </PageCard>

      {/* 其他安全能力 */}
      <PageCard
        title={
          <span className="flex items-center gap-2">
            <SafetyOutlined className="text-brand-600" />
            更多安全能力
          </span>
        }
        accent="brand"
      >
        <div className="text-sm text-ink-400">设备管理、登录记录等功能开发中…</div>
      </PageCard>
    </div>
  );
}

// ──────────── Tab 5: 邀请好友 ────────────
function InviteTab() {
  const [msgApi, msgCtx] = message.useMessage();
  const user = useUserSessionStore((s) => s.user);

  const inviteLink = useMemo(() => {
    if (typeof window === 'undefined') return '';
    return `${window.location.origin}/login?ref=${user?.user_id ?? ''}`;
  }, [user?.user_id]);

  const copyLink = () => {
    navigator.clipboard.writeText(inviteLink).then(
      () => msgApi.success('邀请链接已复制'),
      () => msgApi.error('复制失败，请手动复制'),
    );
  };

  return (
    <div className="space-y-4">
      {msgCtx}

      {/* 邀请主卡 —— 深绿渐变 */}
      <PageCard tone="dark" title="邀请好友 · 赢取算力" subtitle="双方得 100 算力 / VIP 额外 500" accent="gold">
        <div className="mb-3 flex items-center gap-2 text-[13px] text-ink-0/70">
          <GiftOutlined className="text-gold-400" />
          邀请好友注册极睿智投，双方各得 100 算力；好友开通 VIP 后额外奖励 500 算力！
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={inviteLink}
            readOnly
            className="!flex-1 !border-white/20 !bg-white/10 !text-white placeholder:!text-white/40"
          />
          <Button
            icon={<CopyOutlined />}
            onClick={copyLink}
            className="!shrink-0 !border-gold-500 !bg-gold-500 !text-white hover:!bg-gold-600"
          >
            复制链接
          </Button>
        </div>
      </PageCard>

      {/* 统计卡 */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="已邀请人数" value={0} />
        <StatCard label="开通 VIP 人数" value={0} />
        <StatCard label="已获奖励算力" value={0} hint="累计金额" />
      </div>

      {/* 奖励规则 */}
      <PageCard title="奖励规则" accent="brand">
        <div className="space-y-2.5 text-[13px] text-ink-600">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-[11px] font-bold text-brand-600">
              1
            </span>
            <span>
              好友通过你的链接注册成功，你和好友各获得{' '}
              <strong className="text-gold-600">100 算力</strong>
            </span>
          </div>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-[11px] font-bold text-brand-600">
              2
            </span>
            <span>
              好友开通任意 VIP 套餐，你额外获得{' '}
              <strong className="text-gold-600">500 算力</strong>
            </span>
          </div>
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-500/10 text-[11px] font-bold text-brand-600">
              3
            </span>
            <span>每位好友仅计奖一次，奖励实时到账</span>
          </div>
        </div>
      </PageCard>

      {/* 邀请记录（暂无） */}
      <PageCard title="邀请记录" accent="brand">
        <Empty description="暂无邀请记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </PageCard>
    </div>
  );
}

// ──────────── 主组件 ────────────
export function BillingPageClient() {
  const [tab, setTab] = useState<TabKey>('profile');

  const tabOptions = [
    { label: '个人信息', value: 'profile' },
    { label: '算力明细', value: 'battery' },
    { label: '会员套餐', value: 'plans' },
    { label: '安全设置', value: 'security' },
    { label: '邀请好友', value: 'invite' },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      {/* 页面标题 */}
      <SectionHeading title="账户中心" subtitle="算力 · 会员 · 安全 · 邀请" />

      {/* 顶部 Hero 卡 */}
      <BillingHero />

      {/* Tab 导航 —— segmented 风 */}
      <div className="overflow-x-auto rounded-2xl border border-ink-50 bg-white p-2 shadow-card">
        <Segmented
          block
          value={tab}
          options={tabOptions}
          onChange={(v) => setTab(v as TabKey)}
          className="min-w-[460px]"
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
