'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Skeleton } from 'antd';

interface LazyCardProps {
  children: ReactNode;
  /** 距离视口多少 px 时开始加载，默认 200 */
  rootMargin?: string;
  /** 骨架屏行数 */
  skeletonRows?: number;
  /** 最小高度（占位） */
  minHeight?: number;
}

/**
 * 懒加载容器 —— 卡片进入视口附近时才渲染 children。
 * 用于折叠以下的卡片，减少首屏渲染量。
 */
export function LazyCard({
  children,
  rootMargin = '200px',
  skeletonRows = 4,
  minHeight = 120,
}: LazyCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [rootMargin]);

  if (visible) return <>{children}</>;

  return (
    <div ref={ref} style={{ minHeight }}>
      <div className="rounded-xl border border-slate-100 bg-white p-4">
        <Skeleton active paragraph={{ rows: skeletonRows }} />
      </div>
    </div>
  );
}
