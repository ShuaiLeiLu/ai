import React from 'react';

interface LogoProps {
  className?: string;
  size?: number;
}

export function Logo({ className, size = 32 }: LogoProps) {
  return (
    <div 
      className={`relative flex items-center justify-center ${className} group`}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full transition-transform duration-500 group-hover:scale-110"
      >
        {/* X 的上升路径 (趋势) */}
        <path
          d="M6 26L26 6M26 6H18M26 6V14"
          stroke="url(#x_gradient_1)"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="drop-shadow-[0_0_4px_rgba(124,58,237,0.3)]"
        />
        
        {/* X 的交叉路径 (深度) */}
        <path
          d="M26 26L6 6"
          stroke="url(#x_gradient_2)"
          strokeWidth="3.5"
          strokeLinecap="round"
          opacity="0.8"
        />

        {/* 核心智投之眼 (睿) */}
        <rect
          x="13"
          y="13"
          width="6"
          height="6"
          rx="1"
          transform="rotate(45 16 16)"
          fill="white"
          className="animate-pulse"
        />
        <rect
          x="14.5"
          y="14.5"
          width="3"
          height="3"
          rx="0.5"
          transform="rotate(45 16 16)"
          fill="#7c3aed"
        />

        <defs>
          <linearGradient id="x_gradient_1" x1="6" y1="26" x2="26" y2="6" gradientUnits="userSpaceOnUse">
            <stop stopColor="#7c3aed" />
            <stop offset="1" stopColor="#a78bfa" />
          </linearGradient>
          <linearGradient id="x_gradient_2" x1="26" y1="26" x2="6" y2="6" gradientUnits="userSpaceOnUse">
            <stop stopColor="#c4b5fd" />
            <stop offset="1" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
      </svg>
      
      {/* 背景晕染效果 */}
      <div className="absolute inset-0 -z-10 rounded-full bg-brand-500/10 blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}
