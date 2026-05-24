/**
 * 研究员头像 —— 圆形渐变背景 + 取名字最后一个字
 *
 * 视觉规则（对标 5A 设计稿）：
 *  - 阿发（情绪超短）→ up 渐变
 *  - 阿龙（技术派）→ brand 实色 / brand 渐变
 *  - 阿平（基本面）→ brand-300 → brand-500 渐变（青绿）
 *  - 桃桃（宏观）→ up 实色 / 红
 *  - 狸/价值 → gold 渐变
 *  - 兜底：根据 level 决定渐变深浅
 */
import type { CSSProperties } from 'react';

type Size = 'xs' | 'sm' | 'md' | 'lg';

const SIZE_CLASS: Record<Size, string> = {
  xs: 'h-[18px] w-[18px] text-[10px]',
  sm: 'h-6 w-6 text-[11px]',
  md: 'h-8 w-8 text-xs',
  lg: 'h-16 w-16 text-[28px]',
};

interface BackgroundDescriptor {
  className?: string;
  style?: CSSProperties;
}

/** 根据名称返回背景样式（取最后一个字判定流派） */
export function getResearcherBg(name: string): BackgroundDescriptor {
  if (name.includes('发')) {
    return { style: { background: 'linear-gradient(135deg, #2f9e60, #175f37)' } };
  }
  if (name.includes('平')) {
    return { style: { background: 'linear-gradient(135deg, #6e9d83, #2e6e51)' } };
  }
  if (name.includes('龙')) {
    return { style: { background: 'linear-gradient(135deg, #2e6e51, #143929)' } };
  }
  if (name.includes('桃')) {
    return { style: { background: 'linear-gradient(135deg, #d8453a, #c0362c)' } };
  }
  if (name.includes('狸')) {
    return { style: { background: 'linear-gradient(135deg, #c89a3a, #9f7a2a)' } };
  }
  if (name.includes('韭') || name.includes('小')) {
    return { style: { background: 'linear-gradient(135deg, #6e9d83, #2e6e51)' } };
  }
  return { className: 'bg-brand-500' };
}

/** 取研究员名字最后一个汉字作为头像字 */
export function getResearcherInitial(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '?';
  // 优先取"·"后第一个字，否则取最后一字
  const parts = trimmed.split('·');
  const tail = parts.length > 1 ? parts[1] : trimmed;
  return Array.from(tail)[0] ?? '?';
}

interface ResearcherAvatarProps {
  name: string;
  size?: Size;
  className?: string;
  /** 自定义形状 —— 默认圆，传 'rounded-xl' 等可覆盖 */
  shape?: string;
}

export function ResearcherAvatar({
  name,
  size = 'md',
  className = '',
  shape = 'rounded-full',
}: ResearcherAvatarProps) {
  const bg = getResearcherBg(name);
  return (
    <span
      className={[
        'inline-grid place-items-center font-bold text-white shrink-0',
        SIZE_CLASS[size],
        shape,
        bg.className ?? '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={bg.style}
    >
      {getResearcherInitial(name)}
    </span>
  );
}
