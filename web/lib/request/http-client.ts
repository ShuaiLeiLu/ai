import { env } from '@/lib/env';
import { useUserSessionStore } from '@/stores/user-session.store';

export class HttpError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly payload?: unknown
  ) {
    super(message);
  }
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * 处理 401 未授权响应：清除 session 并跳转登录页。
 * 使用防抖避免多个并发请求同时触发多次跳转。
 */
let isRedirectingToLogin = false;

function handleUnauthorized(): void {
  if (typeof window === 'undefined' || isRedirectingToLogin) return;
  isRedirectingToLogin = true;

  // 清除 Zustand store 和 localStorage
  useUserSessionStore.getState().logout();

  // 跳转到登录页，携带当前路径以便登录后回跳
  const currentPath = window.location.pathname + window.location.search;
  const loginUrl = `/login${currentPath !== '/' ? `?redirect=${encodeURIComponent(currentPath)}` : ''}`;
  window.location.href = loginUrl;

  // 延迟重置标志，防止极短时间内重复触发
  setTimeout(() => {
    isRedirectingToLogin = false;
  }, 3000);
}

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(init?.headers ?? {})
    },
    cache: 'default'
  });

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    // ── 401 自动登出 ──
    if (response.status === 401) {
      handleUnauthorized();
    }

    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : `Request failed with status ${response.status}`;
    throw new HttpError(detail, response.status, payload);
  }

  return payload as T;
}
