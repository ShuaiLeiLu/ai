/**
 * 登录 / 注册页面 —— 双栏布局（对照设计稿）
 *
 * 左：深绿引导区，金色装饰、思源宋体大标语、平台数据
 * 右：极简登录/注册表单
 *
 * 响应式：< md 隐藏左栏，仅展示右侧表单
 */
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Button, Form, Input, Segmented, Spin, message } from 'antd';
import { LockOutlined, PhoneOutlined, UserOutlined } from '@ant-design/icons';

import { login as loginApi, register as registerApi } from '@/features/auth/api';
import { useUserSessionStore } from '@/stores/user-session.store';
import { routes } from '@/lib/constants/routes';

type AuthMode = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const sessionLogin = useUserSessionStore((s) => s.login);
  const [messageApi, messageCtx] = message.useMessage();
  const [mode, setMode] = useState<AuthMode>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      router.replace(routes.workstation);
      return;
    }
    setMounted(true);
  }, [router]);

  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();

  const handleLogin = async (values: { phone: string; password: string }) => {
    setLoading(true);
    setError(null);
    try {
      const data = await loginApi(values);
      sessionLogin(data.access_token, data.user);
      messageApi.success(`欢迎回来，${data.user.nickname}`);
      router.push(routes.workstation);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '登录失败';
      setError(msg);
      messageApi.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: {
    phone: string; password: string; nickname: string; confirmPassword?: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const { confirmPassword: _, ...params } = values;
      await registerApi(params);
      messageApi.success('注册成功，请登录');
      setError(null);
      setMode('login');
      loginForm.setFieldsValue({ phone: values.phone, password: '' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '注册失败';
      setError(msg);
      messageApi.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleModeChange = (v: string) => {
    setMode(v as AuthMode);
    setError(null);
  };

  if (!mounted) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-ink-0">
        <Spin size="large" />
      </main>
    );
  }

  return (
    <main className="grid min-h-screen grid-cols-1 bg-ink-0 md:grid-cols-[1.1fr_1fr]">
      {messageCtx}

      {/* ─── 左栏：品牌引导（仅 md+ 显示） ─── */}
      <section className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 to-brand-900 px-12 py-12 text-white md:flex md:flex-col md:justify-between lg:px-16">
        {/* 装饰光晕 */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-16 h-72 w-72 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(200,154,58,.20), transparent 70%)' }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-20 -left-20 h-80 w-80 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(200,154,58,.10), transparent 70%)' }}
        />

        {/* Logo + Brand */}
        <div className="relative flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-gold-500 to-gold-600 font-serif text-[22px] font-bold text-ink-900 shadow-gold">
            极
          </div>
          <div>
            <div className="serif text-[22px] font-bold leading-none">极睿智投</div>
            <div className="mt-1 text-[10px] tracking-[3px] text-white/55">JIRUI · AI</div>
          </div>
        </div>

        {/* 大标语 + 数据 */}
        <div className="relative">
          <div className="serif text-[34px] font-bold leading-[1.4] text-gold-300 lg:text-[38px]">
            运筹于帷幄之中
            <br />
            决胜于千里之外
          </div>
          <div className="mt-5 max-w-md text-[14px] leading-[1.85] text-white/70">
            AI 原生投研工作台 · 让 8 位自驱研究员为你 24 小时盯盘
            <br />
            夜间研判 · 盘前速览 · 盘中决策 · 盘后复盘
          </div>

          <div className="mt-7 flex gap-5">
            <div>
              <div className="serif text-[28px] font-bold text-gold-300">
                12<span className="ml-0.5 text-[14px]">+</span>
              </div>
              <div className="text-[11px] text-white/60">AI 研究员模板</div>
            </div>
            <div className="w-px bg-white/10" />
            <div>
              <div className="serif text-[28px] font-bold text-gold-300">47</div>
              <div className="text-[11px] text-white/60">每日研判任务</div>
            </div>
            <div className="w-px bg-white/10" />
            <div>
              <div className="serif text-[28px] font-bold text-gold-300">
                21<span className="ml-0.5 text-[14px]">源</span>
              </div>
              <div className="text-[11px] text-white/60">实时数据接入</div>
            </div>
          </div>
        </div>

        <div className="relative text-[11px] tracking-wide text-white/40">
          © 2026 JIRUI Capital. 投资有风险，入市需谨慎。
        </div>
      </section>

      {/* ─── 右栏：表单 ─── */}
      <section className="flex items-center justify-center px-6 py-12 sm:px-12 lg:px-20">
        <div className="w-full max-w-[400px]">
          {/* 移动端 Logo（左栏隐藏时） */}
          <div className="mb-8 flex items-center gap-2.5 md:hidden">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 font-serif text-[18px] font-bold text-white shadow-brand">
              极
            </div>
            <div>
              <div className="serif text-[18px] font-bold text-ink-900">极睿智投</div>
              <div className="text-[10px] tracking-[2px] text-ink-400">JIRUI · AI</div>
            </div>
          </div>

          <h1 className="serif text-[26px] font-bold text-ink-900">
            {mode === 'login' ? '欢迎回来' : '创建账号'}
          </h1>
          <p className="mt-1.5 text-[13px] text-ink-500">
            {mode === 'login'
              ? '使用账号密码登录极睿智投工作台'
              : '注册一个新账号，开启 AI 投研之旅'}
          </p>

          {/* 模式切换 */}
          <div className="mt-6">
            <Segmented
              block
              value={mode}
              options={[
                { label: '登录', value: 'login' },
                { label: '注册', value: 'register' },
              ]}
              onChange={handleModeChange}
            />
          </div>

          {/* 错误提示 */}
          {error && (
            <Alert
              message={error}
              type="error"
              showIcon
              closable
              className="!mt-4 !rounded-xl"
              onClose={() => setError(null)}
            />
          )}

          {/* ── 登录表单 ── */}
          {mode === 'login' && (
            <Form
              form={loginForm}
              layout="vertical"
              onFinish={handleLogin}
              requiredMark={false}
              size="large"
              className="!mt-5"
            >
              <Form.Item
                name="phone"
                label={<span className="text-[12.5px] text-ink-600">手机号</span>}
                rules={[
                  { required: true, message: '请输入手机号' },
                  { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
                ]}
              >
                <Input
                  prefix={<PhoneOutlined className="text-ink-400" />}
                  placeholder="请输入 11 位手机号"
                  maxLength={11}
                  className="!rounded-xl !bg-ink-25"
                />
              </Form.Item>
              <Form.Item
                name="password"
                label={
                  <div className="flex w-full items-center justify-between">
                    <span className="text-[12.5px] text-ink-600">密码</span>
                    <a
                      href="#"
                      className="text-[11.5px] font-medium text-brand-600 hover:text-brand-700"
                      onClick={(e) => e.preventDefault()}
                    >
                      忘记密码？
                    </a>
                  </div>
                }
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码至少 6 位' },
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined className="text-ink-400" />}
                  placeholder="请输入密码"
                  className="!rounded-xl !bg-ink-25"
                />
              </Form.Item>
              <Form.Item className="!mb-3">
                <Button
                  type="primary"
                  htmlType="submit"
                  block
                  loading={loading}
                  className="!h-11 !rounded-xl !text-[14px] !font-semibold"
                >
                  登录工作台
                </Button>
              </Form.Item>

              <div className="my-5 flex items-center gap-3 text-[11px] text-ink-300">
                <div className="h-px flex-1 bg-ink-50" />
                <span>其他登录方式</span>
                <div className="h-px flex-1 bg-ink-50" />
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <Button className="!h-10 !rounded-xl" disabled>微信</Button>
                <Button className="!h-10 !rounded-xl" disabled>短信验证码</Button>
              </div>

              <div className="mt-6 text-center text-[12.5px] text-ink-400">
                还没有账号？
                <button
                  type="button"
                  className="ml-1 font-semibold text-brand-600 hover:text-brand-700"
                  onClick={() => setMode('register')}
                >
                  立即注册
                </button>
              </div>
            </Form>
          )}

          {/* ── 注册表单 ── */}
          {mode === 'register' && (
            <Form
              form={registerForm}
              layout="vertical"
              onFinish={handleRegister}
              requiredMark={false}
              size="large"
              className="!mt-5"
            >
              <Form.Item
                name="phone"
                label={<span className="text-[12.5px] text-ink-600">手机号</span>}
                rules={[
                  { required: true, message: '请输入手机号' },
                  { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
                ]}
              >
                <Input
                  prefix={<PhoneOutlined className="text-ink-400" />}
                  placeholder="请输入 11 位手机号"
                  maxLength={11}
                  className="!rounded-xl !bg-ink-25"
                />
              </Form.Item>
              <Form.Item
                name="nickname"
                label={<span className="text-[12.5px] text-ink-600">昵称</span>}
                rules={[
                  { required: true, message: '请输入昵称' },
                  { max: 32, message: '昵称最长 32 个字符' },
                ]}
              >
                <Input
                  prefix={<UserOutlined className="text-ink-400" />}
                  placeholder="为自己取个昵称"
                  className="!rounded-xl !bg-ink-25"
                />
              </Form.Item>
              <Form.Item
                name="password"
                label={<span className="text-[12.5px] text-ink-600">密码</span>}
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码至少 6 位' },
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined className="text-ink-400" />}
                  placeholder="至少 6 位"
                  className="!rounded-xl !bg-ink-25"
                />
              </Form.Item>
              <Form.Item
                name="confirmPassword"
                label={<span className="text-[12.5px] text-ink-600">确认密码</span>}
                dependencies={['password']}
                rules={[
                  { required: true, message: '请确认密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) return Promise.resolve();
                      return Promise.reject(new Error('两次密码不一致'));
                    },
                  }),
                ]}
              >
                <Input.Password
                  prefix={<LockOutlined className="text-ink-400" />}
                  placeholder="再次输入密码"
                  className="!rounded-xl !bg-ink-25"
                />
              </Form.Item>
              <Form.Item className="!mb-3">
                <Button
                  type="primary"
                  htmlType="submit"
                  block
                  loading={loading}
                  className="!h-11 !rounded-xl !text-[14px] !font-semibold"
                >
                  创建账号
                </Button>
              </Form.Item>
              <div className="text-center text-[12.5px] text-ink-400">
                已有账号？
                <button
                  type="button"
                  className="ml-1 font-semibold text-brand-600 hover:text-brand-700"
                  onClick={() => setMode('login')}
                >
                  去登录
                </button>
              </div>
            </Form>
          )}
        </div>
      </section>
    </main>
  );
}
