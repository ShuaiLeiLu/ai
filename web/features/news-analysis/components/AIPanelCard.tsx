/**
 * AI 分析卡片 —— 带彩色渐变背景的卡片组件
 *
 * 支持 4 种颜色主题：blue / orange / red / green，
 * 对应目标站上的 市场总结 / 热点追踪 / 市场变盘 / 行业关注 四张卡片。
 * 加载态显示骨架屏，加载完成后显示摘要 + 要点列表。
 */
import { Skeleton, Typography } from 'antd';

interface AIPanelCardProps {
  title: string;
  summary?: string;
  highlights?: string[];
  loading: boolean;
  color?: 'blue' | 'orange' | 'red' | 'green';
  onClick?: () => void;
}

/** 卡片配色映射 (精致金融版) */
const colorMap = {
  blue: 'bg-blue-50/30 border-blue-100 text-blue-600',
  orange: 'bg-amber-50/30 border-amber-100 text-amber-600',
  red: 'bg-rose-50/30 border-rose-100 text-rose-600',
  green: 'bg-emerald-50/30 border-emerald-100 text-emerald-600',
};

export function AIPanelCard({ title, summary, highlights, loading, color = 'blue', onClick }: AIPanelCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || !summary}
      className={`group relative w-full overflow-hidden rounded-xl border bg-white p-4 text-left transition-all duration-300 hover:-translate-y-0.5 hover:shadow-fintech disabled:cursor-default disabled:hover:translate-y-0 disabled:hover:shadow-none ${colorMap[color]}`}
    >
      {/* 绚丽点缀：极细左侧强调线 */}
      <div className={`absolute left-0 top-0 h-full w-1 opacity-60 ${color === 'blue' ? 'bg-blue-500' : color === 'orange' ? 'bg-amber-500' : color === 'red' ? 'bg-rose-500' : 'bg-emerald-500'}`}></div>

      <div className="relative z-10">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[12px] font-bold uppercase tracking-wider opacity-80">{title}</span>
          <div className={`h-1.5 w-1.5 rounded-full ${color === 'blue' ? 'bg-blue-400' : color === 'orange' ? 'bg-amber-400' : color === 'red' ? 'bg-rose-400' : 'bg-emerald-400'}`}></div>
        </div>

        {loading ? (
          <Skeleton active paragraph={{ rows: 2, width: '100%' }} title={false} />
        ) : (
          <div className="space-y-2">
            <div className="text-[13px] leading-relaxed text-slate-600 font-medium line-clamp-2 group-hover:text-slate-900 transition-colors">
              {summary || '暂无分析数据'}
            </div>
            <div className="flex flex-wrap gap-1.5">
               {highlights?.slice(0, 2).map((point, index) => (
                  <span key={index} className="inline-block px-1.5 py-0.5 rounded bg-white/80 border border-slate-100 text-[10px] text-slate-500 font-medium">
                     {point}
                  </span>
               ))}
            </div>
          </div>
        )}
      </div>
    </button>
  );
}
