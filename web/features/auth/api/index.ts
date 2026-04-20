/**
 * 认证模块 API 层
 *
 * 对接后端 /auth 接口：
 *  - login()       手机号+密码登录，返回 token + 用户信息
 *  - register()    手机号+密码+昵称注册
 *  - getProfile()  获取当前用户资料（需 Bearer token）
 */
import { http } from '@/lib/request/http-client';
import type { ApiResponse } from '@/types/api';

/** 登录响应 */
export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

/** 用户资料 */
export interface UserProfile {
  user_id: string;
  phone: string;
  nickname: string;
  membership_level: string;
  battery_balance: number;
}

/** 登录请求参数 */
export interface LoginParams {
  phone: string;
  password: string;
}

/** 注册请求参数 */
export interface RegisterParams {
  phone: string;
  password: string;
  nickname: string;
}

/** 手机号+密码登录 */
export async function login(params: LoginParams): Promise<AuthToken> {
  const res = await http<ApiResponse<AuthToken>>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(params),
  });
  return res.data;
}

/** 手机号+密码+昵称注册 */
export async function register(params: RegisterParams): Promise<UserProfile> {
  const res = await http<ApiResponse<UserProfile>>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(params),
  });
  return res.data;
}

/** 获取当前登录用户的资料 */
export async function getProfile(): Promise<UserProfile> {
  const res = await http<ApiResponse<UserProfile>>('/auth/me');
  return res.data;
}
