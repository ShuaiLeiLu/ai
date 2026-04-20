import type { Metadata } from 'next';

import { TasksManager } from '@/features/tasks/components/TasksManager';

export const metadata: Metadata = {
  title: '任务编排'
};

export default function TasksPage() {
  return <TasksManager />;
}
