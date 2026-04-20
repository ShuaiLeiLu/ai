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
}

/** 卡片背景渐变色 + 边框色映射 */
const colorMap = {
  blue: 'from-blue-50 to-blue-100/50 border-blue-200',
  orange: 'from-amber-50 to-amber-100/50 border-amber-200',
  red: 'from-rose-50 to-rose-100/50 border-rose-200',
  green: 'from-emerald-50 to-emerald-100/50 border-emerald-200',
};

/** 卡片标题文字色映射 */
const titleColorMap = {
  blue: 'text-blue-700',
  orange: 'text-amber-700',
  red: 'text-rose-700',
  green: 'text-emerald-700',
};

export function AIPanelCard({ title, summary, highlights, loading, color = 'blue' }: AIPanelCardProps) {
  return (
    <div className={`rounded-lg border bg-gradient-to-br p-4 ${colorMap[color]}`}>
      <div className={`mb-2 text-sm font-semibold ${titleColorMap[color]}`}>{title}</div>
      {loading ? (
        <Skeleton active paragraph={{ rows: 2 }} title={false} />
      ) : (
        <div className="space-y-1">
          <Typography.Paragraph className="!mb-1 !text-sm !text-slate-700">
            {summary || '暂无内容'}
          </Typography.Paragraph>
          {highlights?.map((point, index) => (
            <div key={`${title}-${index}`} className="text-xs text-slate-500">
              • {point}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
