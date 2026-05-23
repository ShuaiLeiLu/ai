'use client';

/**
 * 顶栏左侧的「日期 + 开盘倒计时」组件
 *
 * 显示：
 *   - 当前日期（含周几）
 *   - 距离下一个 A 股开/收盘的倒计时（带心跳脉冲）
 *
 * A 股交易时段（北京时间）：
 *   09:30 ~ 11:30
 *   13:00 ~ 15:00
 */
import { useEffect, useState } from 'react';

const WEEK = ['日', '一', '二', '三', '四', '五', '六'];

type ClockState = {
  date: string;
  status: 'pre-open' | 'in-session' | 'lunch' | 'post-close' | 'weekend';
  countdown: string;
};

/** 把秒数转为 HH:MM:SS */
function toClock(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const h = String(Math.floor(s / 3600)).padStart(2, '0');
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${h}:${m}:${ss}`;
}

/** 计算下次状态切换的倒计时 */
function compute(): ClockState {
  const now = new Date();
  const y = now.getFullYear();
  const mo = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  const w = WEEK[now.getDay()];
  const date = `${y}年${mo}月${d}日（周${w}）`;

  // 当日各时间节点
  const open = new Date(now); open.setHours(9, 30, 0, 0);
  const lunchStart = new Date(now); lunchStart.setHours(11, 30, 0, 0);
  const lunchEnd = new Date(now); lunchEnd.setHours(13, 0, 0, 0);
  const close = new Date(now); close.setHours(15, 0, 0, 0);

  const day = now.getDay();
  const isWeekend = day === 0 || day === 6;

  if (isWeekend) {
    // 周末：到下周一 09:30 的倒计时
    const next = new Date(now);
    const addDays = day === 6 ? 2 : 1;
    next.setDate(next.getDate() + addDays);
    next.setHours(9, 30, 0, 0);
    return { date, status: 'weekend', countdown: toClock((next.getTime() - now.getTime()) / 1000) };
  }
  if (now < open) {
    return { date, status: 'pre-open', countdown: toClock((open.getTime() - now.getTime()) / 1000) };
  }
  if (now < lunchStart) {
    return { date, status: 'in-session', countdown: toClock((lunchStart.getTime() - now.getTime()) / 1000) };
  }
  if (now < lunchEnd) {
    return { date, status: 'lunch', countdown: toClock((lunchEnd.getTime() - now.getTime()) / 1000) };
  }
  if (now < close) {
    return { date, status: 'in-session', countdown: toClock((close.getTime() - now.getTime()) / 1000) };
  }
  // 收盘后：到次日 09:30
  const next = new Date(now);
  next.setDate(next.getDate() + 1);
  next.setHours(9, 30, 0, 0);
  return { date, status: 'post-close', countdown: toClock((next.getTime() - now.getTime()) / 1000) };
}

const statusLabel: Record<ClockState['status'], { text: string; cls: string }> = {
  'pre-open':   { text: '开盘倒计时', cls: 'text-down-600' },
  'in-session': { text: '盘中',       cls: 'text-up-600' },
  'lunch':      { text: '午休',       cls: 'text-ink-400' },
  'post-close': { text: '已收盘 · 距明日开盘', cls: 'text-ink-400' },
  'weekend':    { text: '休市 · 距下周开盘',   cls: 'text-ink-400' },
};

export function TradingClock() {
  const [state, setState] = useState<ClockState | null>(null);

  useEffect(() => {
    setState(compute());
    const id = setInterval(() => setState(compute()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!state) return null;
  const meta = statusLabel[state.status];

  return (
    <div className="hidden items-center gap-2 text-[12.5px] md:flex">
      <span className="text-ink-400">盘前速览</span>
      <span className="text-ink-200">·</span>
      <span className="font-semibold text-ink-800">{state.date}</span>
      <span className="mx-1 hidden h-3.5 w-px bg-ink-50 lg:block" />
      <span className="hidden items-center gap-1.5 lg:flex">
        <span className="pulse-dot" />
        <span className={`font-semibold tabular-nums ${meta.cls}`}>
          {meta.text} {state.countdown}
        </span>
      </span>
    </div>
  );
}
