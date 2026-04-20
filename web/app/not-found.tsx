'use client';

import Link from 'next/link';
import { Button, Result } from 'antd';

import { routes } from '@/lib/constants/routes';

export default function NotFound() {
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="当前路由尚未实现，后续会按模块逐步补齐。"
      extra={
        <Link href={routes.home}>
          <Button type="primary">返回首页</Button>
        </Link>
      }
    />
  );
}
