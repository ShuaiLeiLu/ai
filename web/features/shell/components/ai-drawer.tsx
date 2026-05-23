'use client';

import { useState } from 'react';
import { Button, Drawer } from 'antd';
import { CloseOutlined, LoadingOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons';

interface AiDrawerProps {
  open: boolean;
  onClose: () => void;
}

interface ChatMsg {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  time: string;
}

const mockLogs = [
  { time: '10:42:15', type: 'info', content: '智投大模型研究员 #12 已启动自驱分析工作流' },
  { time: '10:42:18', type: 'success', content: '成功拉取并缓存 腾讯控股 (00700.HK) 最新财报数据' },
  { time: '10:42:30', type: 'process', content: '正在执行多维度财务指标相关性矩阵运算' },
  { time: '10:43:02', type: 'success', content: '自驱模型生成完毕，输出评估报告：超配 (Outperform)' },
  { time: '10:43:05', type: 'info', content: '任务已归档，已写入数据库，报告生成耗时 50s' },
  { time: '21:30:02', type: 'info', content: '系统自动唤醒全网宏观研究员，爬取最新美联储会议纪要' },
  { time: '21:30:15', type: 'success', content: '解析 8 份纪要文本，提炼核心关键词：降息路径、通胀粘性、缩表' },
  { time: '21:30:20', type: 'info', content: '生成《5月FOMC会议前瞻分析》，已推送到主控台概览' },
];

function nowTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

export function AiDrawer({ open, onClose }: AiDrawerProps) {
  const [activeTab, setActiveTab] = useState<'chat' | 'logs'>('chat');
  const [chatInput, setChatInput] = useState('');
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      id: 'init',
      sender: 'ai',
      text: '您好！我是您的智投 AI 助理。可咨询研究员配置、市场研判，或查阅自驱日志。',
      time: nowTime(),
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = () => {
    if (!chatInput.trim()) return;
    const userText = chatInput;
    setMessages((p) => [...p, { id: `${Date.now()}u`, sender: 'user', text: userText, time: nowTime() }]);
    setChatInput('');
    setLoading(true);
    setTimeout(() => {
      setMessages((p) => [
        ...p,
        {
          id: `${Date.now()}a`,
          sender: 'ai',
          text: '已收到您的消息。如需深度研判，请前往「AI 研究员」配置专属智能体。',
          time: nowTime(),
        },
      ]);
      setLoading(false);
    }, 800);
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      closable={false}
      width={Math.min(380, typeof window !== 'undefined' ? window.innerWidth : 380)}
      styles={{
        body: { padding: 0, display: 'flex', flexDirection: 'column', background: '#fbfaf7' },
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-ink-50 bg-white px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <RobotOutlined />
          </span>
          <div>
            <div className="text-[13.5px] font-semibold text-ink-900">极睿 AI 智囊</div>
            <div className="text-[10px] text-ink-400">7x24h 自驱投资管家</div>
          </div>
        </div>
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} className="!text-ink-400" />
      </div>

      {/* Tabs */}
      <div className="mx-4 my-3 flex rounded-lg border border-ink-50 bg-ink-25 p-1">
        {([
          ['chat', 'AI 助理'],
          ['logs', '自驱日志'],
        ] as const).map(([k, l]) => (
          <button
            key={k}
            type="button"
            onClick={() => setActiveTab(k)}
            className={[
              'flex-1 rounded-md py-1.5 text-xs font-medium transition',
              activeTab === k
                ? 'bg-white text-brand-700 shadow-card font-semibold'
                : 'text-ink-500 hover:text-ink-800',
            ].join(' ')}
          >
            {l}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {activeTab === 'chat' ? (
          <div className="flex flex-col gap-3.5">
            {messages.map((m) => (
              <div
                key={m.id}
                className={[
                  'flex max-w-[85%] flex-col',
                  m.sender === 'user' ? 'self-end items-end' : 'self-start items-start',
                ].join(' ')}
              >
                <div
                  className={[
                    'rounded-2xl px-3.5 py-2.5 text-[13.5px] shadow-card',
                    m.sender === 'user'
                      ? 'bg-brand-600 text-white rounded-tr-md'
                      : 'bg-white text-ink-800 border border-ink-50 rounded-tl-md',
                  ].join(' ')}
                >
                  {m.text}
                </div>
                <span className="mt-1 px-1 text-[10px] text-ink-400">{m.time}</span>
              </div>
            ))}
            {loading && (
              <div className="self-start flex items-center gap-2 rounded-2xl rounded-tl-md border border-ink-50 bg-white px-3.5 py-2.5 text-[13.5px] text-ink-500 shadow-card">
                <LoadingOutlined className="text-brand-600" />
                <span>AI 正在分析中...</span>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-ink-900/40 bg-[#161311] p-4 font-mono text-[11px] leading-relaxed text-ink-100 shadow-inner">
            <div className="mb-3 flex items-center gap-1.5 border-b border-ink-800 pb-2">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-down-500" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-ink-400">
                LIVE DAEMON
              </span>
            </div>
            <div className="space-y-2">
              {mockLogs.map((log, i) => (
                <div key={i} className="flex gap-2">
                  <span className="shrink-0 text-ink-500">[{log.time}]</span>
                  <span
                    className={
                      log.type === 'success'
                        ? 'text-down-300'
                        : log.type === 'process'
                          ? 'text-gold-300'
                          : 'text-ink-100'
                    }
                  >
                    {log.content}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      {activeTab === 'chat' && (
        <div className="flex items-center gap-2 border-t border-ink-50 bg-white px-4 py-3">
          <input
            type="text"
            placeholder="问问 AI 智囊..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1 rounded-xl border border-ink-50 bg-ink-25 px-3.5 py-2 text-[13.5px] text-ink-800 placeholder-ink-400 transition focus:border-brand-600 focus:bg-white focus:outline-none"
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} className="!h-9 !w-9 !rounded-xl" />
        </div>
      )}
    </Drawer>
  );
}
