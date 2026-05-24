/**
 * 题材掘金 · API 客户端
 *
 * 后端 5 个接口：
 *   GET  /event-driven/access-status
 *   GET  /event-driven/themes
 *   GET  /event-driven/themes/{id}
 *   GET  /event-driven/they-say
 *   POST /event-driven/unlock
 */
import { http } from '@/lib/request/http-client';
import type { ApiResponse, ListResponse } from '@/types/api';
import type {
  AccessStatus,
  TheySayBoard,
  ThemeDetail,
  ThemeListItem,
  UnlockResult,
} from '@/features/event-driven/types';

const BASE = '/event-driven';

export const getAccessStatus = (): Promise<AccessStatus> =>
  http<ApiResponse<AccessStatus>>(`${BASE}/access-status`).then((r) => r.data);

export const getThemes = (): Promise<ThemeListItem[]> =>
  http<ApiResponse<ListResponse<ThemeListItem>>>(`${BASE}/themes`).then((r) => r.data.items);

export const getThemeDetail = (themeId: string): Promise<ThemeDetail> =>
  http<ApiResponse<ThemeDetail>>(`${BASE}/themes/${encodeURIComponent(themeId)}`).then(
    (r) => r.data,
  );

export const getTheySay = (): Promise<TheySayBoard> =>
  http<ApiResponse<TheySayBoard>>(`${BASE}/they-say`).then((r) => r.data);

export const unlockToday = (): Promise<UnlockResult> =>
  http<ApiResponse<UnlockResult>>(`${BASE}/unlock`, { method: 'POST' }).then((r) => r.data);
