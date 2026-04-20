import { http } from '@/lib/request/http-client';
import type { HealthResponse } from '@/types/api';

export function getHealth() {
  return http<HealthResponse>('/health');
}
