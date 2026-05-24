/** 它们说 · AI 研究员共识看板（深绿渐变 Hero） */
import type { TheySayBoard as TheySayBoardData } from '@/features/event-driven/types';

interface Props {
  data: TheySayBoardData;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return iso;
  }
}

export function TheySayBoard({ data }: Props) {
  const pct = Math.max(0, Math.min(100, (data.confidence / 10) * 100));
  return (
    <section className="relative mb-5 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-700 to-brand-900 px-6 py-6 text-white shadow-card">
      {/* 金色光晕装饰 */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(200,154,58,.16), transparent 70%)',
        }}
      />
      <div className="relative flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-[10px] bg-gradient-to-br from-gold-500 to-gold-600 text-xl">
          💡
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="serif text-[22px] font-bold">它们说 · AI 研究员共识看板</h2>
            <span className="rounded-full border border-gold-500/40 bg-gold-500/20 px-2 py-[2px] text-[11px] text-gold-300">
              {formatTimestamp(data.generated_at)} 生成
            </span>
          </div>
          <div className="mt-1 text-[12px] text-white/60">
            基于 {data.bullish_count + data.neutral_count + data.bearish_count} 位活跃研究员的盘后共识分析
          </div>
        </div>
      </div>

      <div className="relative mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-[1.2fr_1fr_1fr_1.4fr]">
        <div>
          <div className="text-[11px] tracking-[2px] text-white/55">市 场 情 绪 方 向</div>
          <div className="serif mt-1.5 text-[22px] font-bold text-gold-300">{data.sentiment_label}</div>
          <div className="mt-1 text-[11.5px] text-white/65">
            {data.bullish_count} 位偏多 · {data.neutral_count} 位中性 · {data.bearish_count} 位偏空
          </div>
        </div>
        <div>
          <div className="text-[11px] tracking-[2px] text-white/55">信 心 指 数</div>
          <div className="serif tnum mt-1.5 text-[26px] font-bold text-gold-300">
            {data.confidence.toFixed(1)}
            <span className="text-[14px] text-white/50">/10</span>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-gradient-to-r from-gold-500 to-up-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <div>
          <div className="text-[11px] tracking-[2px] text-white/55">情 绪 周 期</div>
          <div className="serif mt-1.5 text-[20px] font-bold text-gold-300">{data.cycle}</div>
          <div className="mt-1 text-[11.5px] text-white/65">{data.cycle_note}</div>
        </div>
        <div>
          <div className="text-[11px] tracking-[2px] text-white/55">情 绪 摘 要</div>
          <p className="serif mt-1.5 text-[13px] leading-[1.7] text-white/85">{data.summary}</p>
        </div>
      </div>
    </section>
  );
}
