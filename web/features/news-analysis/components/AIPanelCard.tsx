/**
 * AI 分析卡片 —— 带彩色渐变背景的卡片组件 (1:1 还原设计稿 11B 增强视图)
 *
 * 支持 4 种颜色主题：blue / green / orange / emerald
 * 采用高保真深底实色渐变背景（linear-gradient）和亮白文字与要点高亮展现。
 */
'use client';

interface AIPanelCardProps {
  title: string;
  description: string;
  icon: string;
  summary?: string;
  highlights?: string[];
  loading: boolean;
  color?: 'blue' | 'green' | 'orange' | 'emerald';
  onClick?: () => void;
}

const gradientMap = {
  blue: 'linear-gradient(135deg, #2196f3, #1565c0)',
  green: 'linear-gradient(135deg, #6e9d83, #2e6e51)',
  orange: 'linear-gradient(135deg, #f5a623, #e07e1a)',
  emerald: 'linear-gradient(135deg, #2f9e60, #1f7f4a)',
};

export function AIPanelCard({
  title,
  description,
  icon,
  summary,
  highlights,
  loading,
  color = 'blue',
  onClick,
}: AIPanelCardProps) {
  const gradient = gradientMap[color];

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || !summary}
      style={{ background: gradient }}
      className="group relative w-full overflow-hidden rounded-[14px] p-[14px] text-left text-white transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-default disabled:hover:translate-y-0 disabled:hover:shadow-none border-0"
    >
      <div className="relative z-10 flex flex-col h-full justify-between">
        {/* Header */}
        <div>
          <div className="flex items-center gap-1.5 opacity-95">
            <span className="text-[16px]">{icon}</span>
            <span className="text-[12px] font-semibold">{title}</span>
          </div>
          
          {/* Main Title/Description */}
          <div className="serif text-[14px] font-bold mt-2.5 leading-snug">
            {description}
          </div>
        </div>

        {/* Content Section */}
        {loading ? (
          <div className="mt-3 opacity-60">
            <div className="animate-pulse space-y-2">
              <div className="h-3 bg-white/20 rounded w-11/12"></div>
              <div className="h-3 bg-white/25 rounded w-3/4"></div>
            </div>
          </div>
        ) : (
          summary && (
            <div className="mt-2.5 space-y-2 border-t border-white/15 pt-2 bg-transparent">
              <div className="text-[12px] leading-relaxed text-white/90 line-clamp-2 font-medium">
                {summary}
              </div>
              {highlights && highlights.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {highlights.slice(0, 2).map((point, index) => (
                    <span
                      key={index}
                      className="inline-block px-1.5 py-0.5 rounded bg-white/15 border border-white/5 text-[10px] text-white/95 font-medium max-w-full truncate"
                    >
                      {point}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        )}
      </div>
    </button>
  );
}

