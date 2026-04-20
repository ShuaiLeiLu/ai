'use client';

import { Button, Result } from 'antd';

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="zh-CN">
      <body>
        <Result
          status="error"
          title="页面渲染失败"
          subTitle="请稍后重试，或联系开发同学排查全局异常。"
          extra={
            <Button type="primary" onClick={reset}>
              重新加载
            </Button>
          }
        />
      </body>
    </html>
  );
}
