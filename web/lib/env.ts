import { z } from 'zod';

const envSchema = z.object({
  NEXT_PUBLIC_APP_NAME: z.string().default('赛博投研'),
  NEXT_PUBLIC_API_BASE_URL: z.string().default('/api/v1')
});

export const env = envSchema.parse({
  NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL
});
