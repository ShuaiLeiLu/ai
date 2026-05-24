/**
 * 5A 金色问答 Hero —— 左侧 1.4fr 主区
 *
 * 对标设计稿：
 *  - gold 渐变底（#fdf4d8 → #f7eebd），右上角 radial halo
 *  - 顶部小字 "今日已生成研报 N 篇"
 *  - 思源宋体大字标题
 *  - 今日最热研究员卡（白色 60% 半透底）
 *  - 3 个推荐问题（白底金边）
 *  - 底部 "↻ 换一批"
 */
'use client';

import { useState } from 'react';
import { ResearcherAvatar } from './ResearcherAvatar';
import type { HiredResearcher } from '@/types/researcher-workbench';

/** 推荐问题候选池 —— 简易客户端轮换 */
const QUESTION_POOL: string[] = [
  '上周五 A 股情绪怎么走？下周超短该怎么布局？',
  '近期发酵的题材，哪个下周有启动机会？',
  '持仓个股该如何止盈止损？休市该做哪些准备？',
  '帮我分析下中国神华的投资价值。',
  '半导体板块下周走势怎么看？',
  '央行近期货币政策对 A 股的影响是什么？',
  '当前低估值蓝筹股有哪些值得跟踪？',
  'AI 行业未来 3 年趋势和产业链机会在哪里？',
  '当前政策风险里，哪些会影响我的持仓？',
  '帮我评估一下大盘系统性风险。',
  '如何构建一个低回撤的防守组合？',
  '行业轮动现在最需要警惕什么风险？',
  '用均线策略做一套简单的择时规则。',
  '如何用量化因子筛选低估成长股？',
  '给我回测一个简单的突破交易策略。',
  '因子投资里动量、质量、估值应该怎么搭配？',
  '当前市场环境更适合进攻还是防守？',
  '今天热点机会里哪些有持续性？',
  '给我的模拟盘做一份风险管理建议。',
  '北向资金近期流向是否有结构性变化？',
  '主流 AI 算力板块当前估值是否已透支？',
  '科创板与创业板谁更值得超额配置？',
  '低位国产替代板块还有哪些标的可以挖掘？',
  '今日热点持续性如何？是否值得追高？',
  '当前市场是否进入泡沫期？该如何防御？',
];

interface Props {
  /** 今日生成研报数 */
  todayCount: number;
  /** 今日最热研究员（若无则隐藏卡片） */
  hotResearcher?: HiredResearcher | null;
  /** 推荐问题点击回调 */
  onAskQuestion?: (question: string) => void;
}

export function AskHero({ todayCount, hotResearcher, onAskQuestion }: Props) {
  const [seed, setSeed] = useState(0);

  // 根据 seed 从池里取 3 个问题
  const questions = (() => {
    const start = (seed * 3) % QUESTION_POOL.length;
    const list: string[] = [];
    for (let i = 0; i < 3; i++) {
      list.push(QUESTION_POOL[(start + i) % QUESTION_POOL.length]);
    }
    return list;
  })();

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-gold-300 px-6 py-6"
      style={{ background: 'linear-gradient(135deg, #fdf4d8 0%, #f7eebd 100%)' }}
    >
      {/* 右上 radial 装饰 */}
      <div
        className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(200,154,58,.22), transparent 70%)',
        }}
      />

      <div className="relative">
        <div className="text-[11.5px] font-semibold text-gold-600">
          今日已生成研报 <b className="text-sm">{todayCount}</b> 篇
        </div>
        <h2 className="serif mt-2 text-[24px] font-bold leading-[1.3] text-ink-900">
          有投资疑问？让 AI 研究员帮你深度分析
        </h2>
        <div className="mt-1 text-[12.5px] text-ink-600">
          AI 研究员可结合行情、研报与市场资讯，为你提供机构级分析报告
        </div>

        {/* 今日最热研究员卡 */}
        {hotResearcher && (
          <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-gold-200 bg-white/60 px-3.5 py-3">
            <ResearcherAvatar name={hotResearcher.name} size="md" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-[13px] font-semibold text-ink-900">
                <span className="truncate">{hotResearcher.name}</span>
                <span className="rounded bg-up-500 px-1.5 py-px text-[11px] font-semibold text-white">
                  今日最热
                </span>
              </div>
              <div className="line-clamp-2 mt-0.5 text-[11px] text-ink-500">
                {hotResearcher.summary || '专注垂直领域分析，可结合行情数据生成深度研报'}
              </div>
            </div>
          </div>
        )}

        {/* 3 个推荐问题 */}
        <div className="mt-3 flex flex-col gap-1.5">
          {questions.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onAskQuestion?.(q)}
              className="flex items-center justify-between gap-2 rounded-xl border border-gold-200 bg-white px-3.5 py-2.5 text-left text-[13px] text-ink-700 hover:border-gold-300 hover:shadow-sm transition-all"
            >
              <span className="truncate">💬 {q}</span>
              <span className="shrink-0 text-gold-600">›</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setSeed((s) => s + 1)}
          className="mt-3 w-full text-center text-[11.5px] text-gold-600 hover:text-gold-700 transition-colors"
        >
          ↻ 换一批
        </button>
      </div>
    </div>
  );
}
