import { Skeleton } from 'antd';

/** 工作台通用骨架屏 —— 适用于所有工作台子页面的路由级 loading
 *  原内容为 overview 专属且列宽写错（lg=15/9 ≠ 实际 12/12），已拆到 overview/loading.tsx
 */
export default function WorkstationLoading() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-100 bg-white p-5">
        <Skeleton active paragraph={{ rows: 6 }} />
      </div>
      <div className="rounded-xl border border-slate-100 bg-white p-5">
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
    </div>
  );
}
