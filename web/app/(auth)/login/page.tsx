/**
 * 登录 / 注册页面
 *
 * 功能：
 *  - Segmented 切换「登录」和「注册」表单
 *  - 登录：手机号 + 密码 → 调用 /auth/login → 存 token 跳转工作台
 *  - 注册：手机号 + 密码 + 昵称 → 调用 /auth/register → 自动切换到登录
 *  - 全局 message 提示成功/错误
 *  - 响应式移动端适配（全屏居中，卡片宽度自适应）
 */
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Button, Form, Input, Segmented, Spin, Typography, message } from 'antd';
import { LockOutlined, PhoneOutlined, UserOutlined } from '@ant-design/icons';

import { login as loginApi, register as registerApi } from '@/features/auth/api';
import { useUserSessionStore } from '@/stores/user-session.store';
import { Logo } from '@/components/ui/logo';
import { routes } from '@/lib/constants/routes';

type AuthMode = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const sessionLogin = useUserSessionStore((s) => s.login);
  const [messageApi, messageCtx] = message.useMessage();
  const [mode, setMode] = useState<AuthMode>('login');    // 当前模式：登录/注册
  const [loading, setLoading] = useState(false);           // 提交中
  const [error, setError] = useState<string | null>(null); // 错误提示
  const [mounted, setMounted] = useState(false);           // 客户端挂载完成标志

  // 防止 SSR hydration 闪烁 + 已登录用户自动跳转工作台
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      router.replace(routes.workstation);
      return;
    }
    setMounted(true);
  }, [router]);

  // ── 登录表单 ──
  const [loginForm] = Form.useForm();
  // ── 注册表单 ──
  const [registerForm] = Form.useForm();

  /** 提交登录 */
  const handleLogin = async (values: { phone: string; password: string }) => {
    setLoading(true);
    setError(null);
    try {
      const data = await loginApi(values);
      // 保存 token 和用户信息到全局 store + localStorage
      sessionLogin(data.access_token, data.user);
      messageApi.success(`欢迎回来，${data.user.nickname}`);
      // 跳转工作台
      router.push(routes.workstation);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '登录失败';
      setError(msg);
      messageApi.error(msg);
    } finally {
      setLoading(false);
    }
  };

  /** 提交注册（剥离 confirmPassword，只发 phone/password/nickname） */
  const handleRegister = async (values: { phone: string; password: string; nickname: string; confirmPassword?: string }) => {
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

  /** 切换模式时清除错误 */
  const handleModeChange = (v: string) => {
    setMode(v as AuthMode);
    setError(null);
  };

  // 未挂载时显示加载片屏，避免 Ant Design 组件无样式闪烁
  if (!mounted) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-brand-50/30 to-slate-100">
        <Spin size="large" />
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-brand-50/30 to-slate-100 px-4 py-8 sm:px-6">
      {messageCtx}

      <div className="w-full max-w-[420px] rounded-2xl border border-slate-200 bg-white p-6 shadow-xl sm:p-8">
        {/* Logo + 标题 */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center">
            <Logo size={56} />
          </div>
          <Typography.Title level={3} className="!mb-1">
            极睿智投
          </Typography.Title>
          <Typography.Text type="secondary" className="text-sm">
            AI 驱动的下一代投研平台
          </Typography.Text>
        </div>

        {/* Tab 切换 */}
        <div className="mb-6 flex justify-center">
          <Segmented
            block
            value={mode}
            options={[
              { label: '登录', value: 'login' },
              { label: '注册', value: 'register' },
            ]}
            onChange={handleModeChange}
            className="w-full"
          />
        </div>

        {/* ── 登录表单 ── */}
        {mode === 'login' && (
          <Form
            form={loginForm}
            layout="vertical"
            onFinish={handleLogin}
            requiredMark={false}
            size="large"
          >
            {error && (
              <Alert message={error} type="error" showIcon closable className="!mb-4" onClose={() => setError(null)} />
            )}
            <Form.Item
              name="phone"
              rules={[
                { required: true, message: '请输入手机号' },
                { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
              ]}
            >
              <Input
                prefix={<PhoneOutlined className="text-slate-400" />}
                placeholder="手机号"
                maxLength={11}
              />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6位' },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined className="text-slate-400" />}
                placeholder="密码"
              />
            </Form.Item>
            <Form.Item className="!mb-2">
              <Button type="primary" htmlType="submit" block loading={loading}>
                登录
              </Button>
            </Form.Item>
            <div className="text-center text-xs text-slate-400">
              还没有账号？
              <button
                type="button"
                className="ml-1 text-brand-500 hover:text-brand-600"
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
          >
            {error && (
              <Alert message={error} type="error" showIcon closable className="!mb-4" onClose={() => setError(null)} />
            )}
            <Form.Item
              name="phone"
              rules={[
                { required: true, message: '请输入手机号' },
                { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
              ]}
            >
              <Input
                prefix={<PhoneOutlined className="text-slate-400" />}
                placeholder="手机号"
                maxLength={11}
              />
            </Form.Item>
            <Form.Item
              name="nickname"
              rules={[
                { required: true, message: '请输入昵称' },
                { max: 32, message: '昵称最长32个字符' },
              ]}
            >
              <Input
                prefix={<UserOutlined className="text-slate-400" />}
                placeholder="昵称"
              />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6位' },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined className="text-slate-400" />}
                placeholder="密码（至少6位）"
              />
            </Form.Item>
            <Form.Item
              name="confirmPassword"
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
                prefix={<LockOutlined className="text-slate-400" />}
                placeholder="确认密码"
              />
            </Form.Item>
            <Form.Item className="!mb-2">
              <Button type="primary" htmlType="submit" block loading={loading}>
                注册
              </Button>
            </Form.Item>
            <div className="text-center text-xs text-slate-400">
              已有账号？
              <button
                type="button"
                className="ml-1 text-brand-500 hover:text-brand-600"
                onClick={() => setMode('login')}
              >
                去登录
              </button>
            </div>
          </Form>
        )}
      </div>
    </main>
  );
}
