import React from 'react';

interface LogoProps {
  className?: string;
  size?: number;
}

/**
 * 极睿智投 品牌 Logo —— 松烟墨绿渐变方块 + 思源宋体「极」字
 *
 * 对照设计稿：圆角 9px、深绿渐变（brand-600 → brand-500）、阴影 brand
 * 用法：<Logo size={32} />
 */
export function Logo({ className = '', size = 32 }: LogoProps) {
  const fontSize = Math.round(size * 0.55);
  const radius = Math.round(size * 0.28);
  return (
    <div
      className={`group relative grid place-items-center bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand transition-transform duration-300 group-hover:scale-105 ${className}`}
      style={{ width: size, height: size, borderRadius: radius }}
      aria-label="极睿智投 Logo"
    >
      <span
        className="serif font-bold leading-none"
        style={{ fontSize, lineHeight: 1 }}
      >
        极
      </span>
      {/* 金色装饰光晕（hover 显形） */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity group-hover:opacity-100"
        style={{
          background:
            'radial-gradient(circle at 100% 0%, rgba(200,154,58,.30), transparent 60%)',
        }}
      />
    </div>
  );
}
