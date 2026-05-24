'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from 'react';
import { createPortal } from 'react-dom';

export type ToastType = 'success' | 'info' | 'warning' | 'error';

export interface ToastOptions {
  /** 持续毫秒数；不传则按类型默认（success=2s, info=3s, warning=4s, error=5s） */
  duration?: number;
  /** 自定义图标，覆盖默认 emoji */
  icon?: ReactNode;
}

export interface ToastItem {
  id: string;
  type: ToastType;
  content: ReactNode;
  duration: number;
  icon?: ReactNode;
}

interface ToastContextValue {
  /** 显示一条 toast，返回 id；可手动 dismiss */
  show: (type: ToastType, content: ReactNode, options?: ToastOptions) => string;
  dismiss: (id: string) => void;
  success: (content: ReactNode, options?: ToastOptions) => string;
  info: (content: ReactNode, options?: ToastOptions) => string;
  warning: (content: ReactNode, options?: ToastOptions) => string;
  error: (content: ReactNode, options?: ToastOptions) => string;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION: Record<ToastType, number> = {
  success: 2000,
  info: 3000,
  warning: 4000,
  error: 5000
};

const DEFAULT_ICON: Record<ToastType, string> = {
  success: '✓',
  info: 'ℹ',
  warning: '⚠',
  error: '✕'
};

const BAR_COLOR: Record<ToastType, string> = {
  success: '#2f9e60', // down-500 (A 股「跌」即绿色，此处用于成功语义中的绿色色条)
  info: '#2e6e51', // brand-500
  warning: '#c89a3a', // gold-500
  error: '#d8453a' // up-500
};

const ICON_COLOR: Record<ToastType, string> = {
  success: '#62af80',
  info: '#a4c9b1',
  warning: '#ecd58a',
  error: '#ec7f74'
};

let toastCounter = 0;

function nextId(): string {
  toastCounter += 1;
  return `toast-${Date.now()}-${toastCounter}`;
}

export interface ToastProviderProps {
  children: ReactNode;
  /** 同时显示的最大 toast 数量，默认 5 */
  max?: number;
}

export function ToastProvider({ children, max = 5 }: ToastProviderProps) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
    const handle = timers.current[id];
    if (handle) {
      clearTimeout(handle);
      delete timers.current[id];
    }
  }, []);

  const show = useCallback(
    (type: ToastType, content: ReactNode, options: ToastOptions = {}) => {
      const id = nextId();
      const duration = options.duration ?? DEFAULT_DURATION[type];
      const item: ToastItem = {
        id,
        type,
        content,
        duration,
        icon: options.icon
      };
      setItems((prev) => {
        const next = [...prev, item];
        if (next.length > max) next.shift();
        return next;
      });
      if (duration > 0) {
        timers.current[id] = setTimeout(() => dismiss(id), duration);
      }
      return id;
    },
    [dismiss, max]
  );

  useEffect(() => {
    const handles = timers.current;
    return () => {
      Object.values(handles).forEach((h) => clearTimeout(h));
    };
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({
      show,
      dismiss,
      success: (content, options) => show('success', content, options),
      info: (content, options) => show('info', content, options),
      warning: (content, options) => show('warning', content, options),
      error: (content, options) => show('error', content, options)
    }),
    [show, dismiss]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport items={items} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

interface ViewportProps {
  items: ToastItem[];
  onDismiss: (id: string) => void;
}

function ToastViewport({ items, onDismiss }: ViewportProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || typeof window === 'undefined') return null;
  if (items.length === 0) return null;

  return createPortal(
    <div
      aria-live="polite"
      role="region"
      className="pointer-events-none fixed inset-x-0 top-4 z-[1100] flex flex-col items-center gap-2 px-3 sm:inset-x-auto sm:right-6 sm:top-6 sm:items-end"
    >
      {items.map((item) => (
        <ToastItemView key={item.id} item={item} onDismiss={onDismiss} />
      ))}
    </div>,
    document.body
  );
}

interface ItemViewProps {
  item: ToastItem;
  onDismiss: (id: string) => void;
}

function ToastItemView({ item, onDismiss }: ItemViewProps) {
  return (
    <div
      role="status"
      className="pointer-events-auto flex w-full max-w-[360px] items-start gap-2.5 overflow-hidden rounded-lg bg-[#171410]/95 py-2.5 pl-3 pr-3.5 text-[12.5px] text-white shadow-card-lg backdrop-blur"
      style={{ borderLeft: `3px solid ${BAR_COLOR[item.type]}` }}
    >
      <span
        aria-hidden
        className="mt-[1px] inline-flex h-4 w-4 flex-shrink-0 items-center justify-center text-[13px] font-bold"
        style={{ color: ICON_COLOR[item.type] }}
      >
        {item.icon ?? DEFAULT_ICON[item.type]}
      </span>
      <div className="flex-1 leading-[1.55] text-white/90">{item.content}</div>
      <button
        type="button"
        aria-label="关闭"
        onClick={() => onDismiss(item.id)}
        className="-mr-1 cursor-pointer border-0 bg-transparent px-1 text-[14px] leading-none text-white/40 transition hover:text-white/70"
      >
        ×
      </button>
    </div>
  );
}

/**
 * useToast —— 必须在 <ToastProvider> 内使用。
 *
 * 使用示例：
 *   const toast = useToast();
 *   toast.success('保存成功');
 *   toast.error('操作失败', { duration: 6000 });
 */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast 必须在 <ToastProvider> 内调用');
  }
  return ctx;
}

export default ToastProvider;
