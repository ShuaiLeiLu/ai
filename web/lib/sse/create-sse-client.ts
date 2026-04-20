import { env } from '@/lib/env';

export function createSseClient(path: string): EventSource {
  return new EventSource(`${env.NEXT_PUBLIC_SSE_BASE_URL}${path}`);
}
