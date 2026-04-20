/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // standalone 仅用于生产部署；开发模式开启会导致 dev chunk 清单异常
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  experimental: {
    typedRoutes: true
  },
  /**
   * 使用可配置的内部 API 地址，开发环境默认走本机 8000，
   * 容器环境可改成 http://api:8000。
   */
  async rewrites() {
    const internalApiBaseUrl = process.env.INTERNAL_API_BASE_URL ?? 'http://localhost:8000/api/v1';

    return [
      {
        source: '/api/v1/:path*',
        destination: `${internalApiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
